import asyncio
import logging
import random
import re
from contextlib import asynccontextmanager
import os
import gzip
import time
from datetime import datetime, timedelta
from time import perf_counter
from typing import Annotated, Mapping

from fastapi import FastAPI, Header, Request
from fastapi import status
from fastapi.templating import Jinja2Templates
from fastapi.responses import ORJSONResponse, RedirectResponse, Response
from fastapi.exceptions import RequestValidationError, HTTPException as FastapiHttpException

from starlette.exceptions import HTTPException as StarletteHTTPException

from pydantic import ValidationError
from starlette.responses import PlainTextResponse, HTMLResponse
from starlette.types import ASGIApp
from starlette.staticfiles import StaticFiles

from src import pgtuner
from src.static.c_timezone import GetTimezone
from src.static.vars import APP_NAME_UPPER, APP_NAME_LOWER, __version__ as backend_version, HOUR, MINUTE, \
    SECOND, DAY, K10
from src.tuner.data.scope import PGTUNER_SCOPE
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE
from src.utils.env import OsGetEnvBool
from web.middlewares.compressor import CompressMiddleware
from web.middlewares.middlewares import HeaderManageMiddleware, RateLimitMiddleware
from web.data import PG_WEB_TUNE_USR_OPTIONS, PG_WEB_TUNE_REQUEST

# ==================================================================================================
__all__ = ['app']
_logger = logging.getLogger(APP_NAME_UPPER)

# 0: Development, 1: Production
_app_dev_mode: bool = OsGetEnvBool(f'{APP_NAME_UPPER}_DEV_MODE', True)

@asynccontextmanager
async def app_lifespan(application: ASGIApp | FastAPI):
    # On-Startup
    _logger.info('Starting up the application ...')
    max_iterations: int = -1  # -1: infinite loop
    cur_iterations: int = 0

    async def _reload_dependency_resources():
        nonlocal max_iterations, cur_iterations
        if max_iterations < -1:
            raise ValueError('The maximum repetitions must be greater than or equal to -1')

        while max_iterations == -1 or cur_iterations < max_iterations:
            # Doing tasks
            # reload_authentication_for_router(application)
            _logger.info('The asynchronous background task is triggered ... ')
            next_trigger = int(300 * (1 + random.random()))

            if max_iterations != -1:
                cur_iterations += 1
            if cur_iterations != max_iterations and next_trigger > 0:
                _logger.info(f'The next reload will be triggered in the next {next_trigger} seconds ...')
                await asyncio.sleep(next_trigger)

    # Don't push await for daemon task
    # loop = asyncio.get_event_loop()
    # loop.create_task(_reload_dependency_resources(), name='Reload Dependency Resources') # pragma: no cover

    # Application Initialization
    _logger.info('Application is ready to serve user traffic ...')
    yield

    # Clean up and release the resources
    _logger.info('Safely shutting down the application. The HTTP(S) connection is cleanup ...')
    logging.shutdown()


# ==================================================================================================
__version__ = '0.1.4'
app: FastAPI = FastAPI(
    debug=False,
    title=APP_NAME_UPPER,
    summary=f'The :project:`{APP_NAME_LOWER}` (or PostgreSQL: DBA & Tuner) is a SQL/Python-based '
            f'project designed to manage and optimize kernel parameters and database settings',
    description=f'''
The :project:`{APP_NAME_LOWER}` (or PostgreSQL: Tuner as DBA) is a SQL/Python-based project designed 
to manage and optimize kernel parameters and database settings, focusing on TCP networking on kernel (connection 
management, retries, timeouts, and **buffering**), and database utilization (memory, disk, integrity); bringing the 
highest performance with stability, data integrity, and concurrency from various system configurations. The tuning is 
inspired by many successful world-wide clusters (Notion, Cloudflare, ...) from OS part, many DBA experts at PostgreSQL 
community (Azure, OnGres, PostgresPro, PostgreSQL core developers, real-world use cases, ...) and my own experience. 
''',
    version=__version__,
    openapi_url='/openapi.json' if _app_dev_mode else None,
    docs_url='/docs' if _app_dev_mode else None,
    redoc_url='/redoc' if _app_dev_mode else None,
    swagger_ui_oauth2_redirect_url='/docs/oauth2-redirect' if _app_dev_mode else None,
    lifespan=app_lifespan,
    terms_of_service=None,
    contact={
        'name': 'Ichiru Take',
        'url': 'https://github.com/IchiruTake',
        'email': 'P.Ichiru.HoangMinh@gmail.com',
    },
    license_info={
        # MIT License
        'name': 'MIT License',
        'url': 'https://opensource.org/license/mit/',
    },
)

# ==================================================================================================
_logger.info('The FastAPI application has been initialized. Adding the middlewares ...')
try:
    from starlette.middleware.sessions import SessionMiddleware # itsdangerous
    import string
    SECRET_KEY = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=HOUR, https_only=False)  # 1-hour session
    _logger.debug(f'The session middleware has been added to the application with secret key {SECRET_KEY}')
except (ImportError, ModuleNotFoundError) as e:
    _logger.warning('The session middleware has not been added to the application due to the missing dependencies. '
                    f'\nPlease install more dependencies: {e}')

# Rate Limiting
def _cost(p: str) -> int:
    # User-enhanced with regex
    if p.startswith('/tune'):
        return 3
    return 1
_request_scale_factor: float = float(os.getenv(f'FASTAPI_REQUEST_LIMIT_FACTOR', '0.90'))
_user_request_limit = int(os.getenv(f'FASTAPI_USER_REQUEST_LIMIT', '15'))
_user_request_window = int(os.getenv(f'FASTAPI_USER_REQUEST_WINDOW', '15'))
app.add_middleware(RateLimitMiddleware, max_requests=int(100 * MINUTE * _request_scale_factor), interval=MINUTE,
                   max_requests_per_window=_user_request_limit, window_length=_user_request_window,
                   cost_function=_cost)
_logger.debug('The rate limiting middleware has been added to the application ...')

# Compression Hardware
_gzip = OsGetEnvBool(f'FASTAPI_GZIP', True)
_gzip_min_size = int(os.getenv(f'FASTAPI_GZIP_MIN_SIZE', '512'))
_gzip_com_level = int(os.getenv(f'FASTAPI_GZIP_COMPRESSION_LEVEL', '6'))
_zstd = OsGetEnvBool(f'FASTAPI_ZSTD', True)
_zstd_min_size = int(os.getenv(f'FASTAPI_ZSTD_MIN_SIZE', '512'))
_zstd_com_level = int(os.getenv(f'FASTAPI_ZSTD_COMPRESSION_LEVEL', '3'))
if OsGetEnvBool(f'FASTAPI_COMPRESS_MIDDLEWARE', False):
    _base_min_size = int(os.getenv(f'FASTAPI_BASE_MIN_SIZE', '512'))  # 512 bytes or 512 length-unit
    _base_com_level = int(os.getenv(f'FASTAPI_BASE_COMPRESSION_LEVEL', '6'))  # 6: Default compression level
    app.add_middleware(CompressMiddleware, minimum_size=_base_min_size, compress_level=_base_com_level,
                       gzip_enabled=_gzip, gzip_minimum_size=_gzip_min_size, gzip_compress_level=_gzip_com_level,
                       zstd_enabled=_zstd, zstd_minimum_size=_zstd_min_size, zstd_compress_level=_zstd_com_level)
    _logger.debug('The compression middleware has been added to the application ...')


# Auto Cache-Control and Header Middleware
_private_cache = 'private, must-revalidate'
_static_cache = (f'max-age={45 * SECOND if _app_dev_mode else 30 * MINUTE}, {_private_cache}, '
                 f'stale-while-revalidate={30 * SECOND if _app_dev_mode else 3 * MINUTE}')
_dynamic_cache = 'no-cache'
app.add_middleware(HeaderManageMiddleware, static_cache_control=_static_cache, dynamic_cache_control=_dynamic_cache)
_logger.debug('The header middleware has been added to the application ...')

_logger.info('The middlewares have been added to the application ...')
# ----------------------------------------------------------------------------------------------
_logger.info('Mounting the static files to the application ...')
_logger.info(f'Developer Mode: {_app_dev_mode}')
_env_tag = 'dev' if _app_dev_mode else 'prd'
_default_path = f'./web/ui/{_env_tag}/static'
_static_mapper = {
    '/static': _default_path,
    '/resource': f'{_default_path}/resource',
    '/css': f'{_default_path}/css',
    # '/js': './web/ui/js',
}

try:
    for path, directory in _static_mapper.items():
        app.mount(path, StaticFiles(directory=directory), name=path.split('/')[-1])
except (FileNotFoundError, RuntimeError) as e:
    _logger.warning(f'The static files have not been mounted: {e}')
    raise e
_logger.info('The static files have been added to the application ...')


# ----------------------------------------------------------------------------------------------
# UI Directory
_templates = Jinja2Templates(directory=f'{_default_path}/jinja2')

# UI Exception Error
class UIException(StarletteHTTPException):

    _status_mapper = {
        400: ('Bad Request', 'The server could not understand the request due to invalid syntax.'),
        401: ('Unauthorized', 'The request has not been applied because it lacks valid authentication credentials for the target resource.'),
        403: ('Forbidden', 'The server understood the request, but is refusing to fulfill it.'),
        404: ('Page Not Found', 'The page you are looking for might have been removed, had its name changed, '
                                'or is temporarily unavailable.'),
        405: ('Method Not Allowed', 'The method is not allowed for the requested URL.'),
        500: ('Internal Server Error', "The server has encountered a situation it doesn't know how to handle."),
        501: ('Not Implemented', 'The server does not support the functionality required to fulfill the request.'),
        502: ('Bad Gateway', 'The server, while acting as a gateway or proxy, received an invalid response from the upstream server it accessed in attempting to fulfill the request.'),
        503: ('Service Unavailable', 'The server is currently unable to handle the request due to a temporary overloading or maintenance of the server.'),
        504: ('Gateway Timeout', 'The server, while acting as a gateway or proxy, did not receive a timely response from the upstream server specified by the URI.'),
        505: ('HTTP Version Not Supported', 'The server does not support, or refuses to support, the major version of HTTP that was used in the request.'),
    }

    def __init__(self, status_code: int, detail: str | None = None, headers: Mapping[str, str] | None = None,
                 heading: str = None, generic_message: str = None, incident_level: str = None):
        super(UIException, self).__init__(status_code=status_code, detail=detail, headers=headers)
        default_heading = self._status_mapper[status_code][0] if status_code in self._status_mapper else None
        default_generic = self._status_mapper[status_code][1] if status_code in self._status_mapper else None
        self.heading = heading or default_heading
        self.generic_message = generic_message or default_generic
        self.incident_level = incident_level


@app.exception_handler(UIException)
async def ui_exception_handler(request: Request, exc: UIException):
    ctx = {
        'status_code': exc.status_code,
        'heading': exc.heading,
        'generic_message': exc.generic_message,
        'detail_message': exc.detail,
    }
    if _app_dev_mode:
        ctx['incident_level'] = exc.incident_level

    return _templates.TemplateResponse(
        name=f'error/index.min.html',
        request=request,
        status_code=exc.status_code,
        headers={
            'Content-Type': 'text/html; charset=UTF-8',
            'Cache-Control': f'max-age={30 * SECOND}, {_private_cache}',
        },
        context=ctx
    )

@app.get('/error')
async def error(request: Request):
    raise UIException(status_code=404, detail='This is a test error page', heading='Test Error Page',)


@app.get('/', status_code=status.HTTP_200_OK)
async def root(request: Request):
    return _templates.TemplateResponse(
        name='/tuner.min.html',
        request=request,
        status_code=status.HTTP_200_OK,
        headers={
            'Content-Type': 'text/html; charset=UTF-8',
            'Cache-Control': _static_cache,
        }
    )

@app.get('/changelog', status_code=status.HTTP_200_OK)
async def changelog(request: Request):
    return _templates.TemplateResponse(
        name='/changelog.min.html',
        request=request,
        status_code=status.HTTP_200_OK,
        headers={
            'Content-Type': 'text/html; charset=UTF-8',
            'Cache-Control': _static_cache,
        }
    )


@app.get('/js/{javascript_path}')
async def js(
        javascript_path: str,
        accept_encoding: Annotated[str | None, Header()]
):
    _javascript_filepath = f'{_default_path}/js/{javascript_path}'
    if not os.path.exists(_javascript_filepath):
        return Response(
            status_code=status.HTTP_404_NOT_FOUND,
            headers={
                'Cache-Control': f'max-age={MINUTE}, private, must-revalidate',
            }
        )
    content = open(_javascript_filepath, 'r').read()
    mtime: str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(os.path.getmtime(_javascript_filepath)))

    response_header: dict[str, str] = {
        'Content-Type': 'application/javascript',
        'Last-Modified': mtime,
        'Etag': str(hash(content)),
        'Cache-Control': _static_cache,
    }
    if accept_encoding and 'gzip' in accept_encoding and len(content) > _gzip_min_size:
        content = gzip.compress(content.encode(), compresslevel=_gzip_com_level)
        response_header['Content-Encoding'] = 'gzip'
        response_header['Content-Length'] = f'{len(content)}'
    return Response(content, status_code=status.HTTP_200_OK, headers=response_header)


@app.get('/robots.txt', status_code=status.HTTP_200_OK)
async def robots():
    content = """User-agent: *
Disallow: /api/
Disallow: /docs/
Disallow: /redoc/
Allow: /
"""
    return PlainTextResponse(
        content=content,
        status_code=status.HTTP_200_OK,
        headers={
            'Cache-Control': _static_cache
        }
    )

# ----------------------------------------------------------------------------------------------
# Health Check API
_SERVICE_START_TIME = datetime.now(tz=GetTimezone()[0])
@app.get('/_health', status_code=status.HTTP_200_OK)
async def health():
    _service_uptime: timedelta = datetime.now(tz=GetTimezone()[0]) - _SERVICE_START_TIME
    return ORJSONResponse(
        content={
            'status': 'HEALTHY',
            'start_time': _SERVICE_START_TIME.isoformat(),
            'uptime': str(_service_uptime),
            'uptime_seconds': _service_uptime.total_seconds(),
            'frontend': __version__,
            'backend': backend_version
        },
        status_code=status.HTTP_200_OK,
        headers={
            'Cache-Control': f'max-age={2 * MINUTE}, s-maxage={45 * SECOND}, {_private_cache}'
        }
    )

# ----------------------------------------------------------------------------------------------
# Backend API
@app.post('/tune', status_code=status.HTTP_200_OK, response_class=ORJSONResponse)
async def trigger_tune(request: PG_WEB_TUNE_REQUEST):
    # Main website
    t0 = perf_counter()
    try:
        backend_request = request.to_backend()
    except ValidationError as err:
        return ORJSONResponse(
            content={'message': 'Invalid Request', 'detail': err.errors()},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except ValueError as err:
        return ORJSONResponse(
            content={'message': 'Invalid Request', 'detail': str(err)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # pprint(backend_request.options)
    response: PG_TUNE_RESPONSE = pgtuner.optimize(backend_request)

    # Display the content and perform memory testing validation
    exclude_names = ['archive_command', 'restore_command', 'archive_cleanup_command', 'recovery_end_command',
                     'log_directory']
    if request.ignore_non_performance_setting:
        exclude_names.extend(['statement_timeout', 'lock_timeout', 'deadlock_timeout', 'transaction_timeout',
                              'idle_session_timeout', 'log_line_prefix'])

    if backend_request.options.operating_system == 'windows':
        exclude_names.extend(['checkpoint_flush_after', 'bgwriter_flush_after', 'wal_writer_flush_after',
                              'backend_flush_after'])


    content = response.generate_content(
        target=PGTUNER_SCOPE.DATABASE_CONFIG,
        request=backend_request,
        output_format=request.output_format,
        exclude_names=set(exclude_names),
        backup_settings=False, # request.backup_settings,
    )
    mem_report = response.mem_test(backend_request.options, request.analyze_with_full_connection_use,
                                   ignore_report=False)[0]

    return ORJSONResponse(
        content={'mem_report': mem_report, 'config': content},
        status_code=status.HTTP_200_OK,
        headers={
            'Content-Type': 'application/json',
            'Cache-Control': f'max-age={30 * SECOND}, private, must-revalidate',
            'X-Response-BackendTime': f'{(perf_counter() - t0) * K10:.2f}ms'
        }
    )


