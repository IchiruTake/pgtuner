import asyncio
import logging
import random
from contextlib import asynccontextmanager
import os
import gzip
import time
from typing import Annotated

from fastapi import FastAPI, Header
from fastapi import status
from fastapi.responses import ORJSONResponse, RedirectResponse, Response
from pydantic import ValidationError
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src import pgtuner
from src.static.vars import APP_NAME_UPPER, APP_NAME_LOWER, __version__ as backend_version, HOUR, MINUTE, \
    SECOND, DAY
from src.tuner.data.scope import PGTUNER_SCOPE
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE
from src.utils.env import OsGetEnvBool
from web.middlewares.compressor import CompressMiddleware
from web.middlewares.middlewares import GlobalRateLimitMiddleware, HeaderManageMiddleware, AutoCacheControlMiddleware
from web.data import PG_WEB_TUNE_USR_OPTIONS, PG_WEB_TUNE_REQUEST

# ==================================================================================================
__all__ = ['app']
_logger = logging.getLogger(APP_NAME_UPPER)


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
__version__ = '0.1.0'
app: FastAPI = FastAPI(
    debug=False,
    title=APP_NAME_UPPER,
    summary=f'{APP_NAME_UPPER}: The :project:`{APP_NAME_LOWER}` (or PostgreSQL: DBA & Tuner) is a SQL/Python-based '
            f'project designed to manage and optimize PostgreSQL parameters',
    description=f'''
{APP_NAME_UPPER}: The :project:`{APP_NAME_LOWER}` (or PostgreSQL: DBA & Tuner) is a SQL/Python-based project designed 
to manage and optimize kernel parameters and database settings, focusing on TCP networking (connection management, 
retries, timeouts, and **buffering**) and memory/VM management (swappiness, dirty ratios, over-commit memory, 
hugepages, and cache pressure); whilst maintaining high performance, stability, security, and concurrency for various 
system configurations. The tuning is inspired by many successful world-wide clusters (Notion, Cloudflare, ...) from OS 
part, and many DBA's experts at PostgreSQL community. This project is a combination of those experiences and designed 
to be a structured approach for various profiles and settings (easily customizable and extendable). 
''',
    version=__version__,
    openapi_url='/openapi.json',
    docs_url='/docs',
    redoc_url='/redoc',
    swagger_ui_oauth2_redirect_url='/docs/oauth2-redirect',
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
# 0: Development, 1: Production
_app_dev_mode: bool = OsGetEnvBool(f'{APP_NAME_UPPER}_DEV_MODE', True)
try:
    from starlette.middleware.sessions import SessionMiddleware # itsdangerous
    import string
    SECRET_KEY = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=HOUR, https_only=False)  # 1-hour session
    _logger.debug(f'The session middleware has been added to the application with secret key {SECRET_KEY}')
except (ImportError, ModuleNotFoundError) as e:
    _logger.warning('The session middleware has not been added to the application due to the missing dependencies. '
                    f'\nPlease install more dependencies: {e}')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True,
                   allow_methods=['GET', 'POST'], allow_headers=[], max_age=600)
app.add_middleware(HeaderManageMiddleware)

# Rate Limiting
_request_scale_factor: float = float(os.getenv(f'FASTAPI_REQUEST_LIMIT_FACTOR', '1'))
app.add_middleware(GlobalRateLimitMiddleware, max_requests=int(50 * _request_scale_factor), interval_by_second=1)

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

# Auto-Cache Middleware
_private_cache = 'private, must-revalidate'
_static_cache = (f'max-age={45 * SECOND if _app_dev_mode else 30 * MINUTE}, {_private_cache}, '
                 f'stale-while-revalidate={30 * SECOND if _app_dev_mode else 3 * MINUTE}')
_dynamic_cache = 'no-cache'
app.add_middleware(AutoCacheControlMiddleware, static_cache_control=_static_cache, dynamic_cache_control=_dynamic_cache)

_logger.info('The middlewares have been added to the application ...')
# ==================================================================================================
_logger.info('Mounting the static files to the application ...')

_logger.info(f'Application Developer Mode: {_app_dev_mode}')
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
if _app_dev_mode:
    @app.get('/min')
    async def root_min():
        return RedirectResponse(
            url='/static/index.min.html',
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                'Cache-Control': _static_cache,
            }
        )

    @app.get('/dev')
    async def root_dev():
        return RedirectResponse(
            url='/static/index.html',
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={
                'Cache-Control': _static_cache,
            }
        )

@app.get('/')
async def root():
    return RedirectResponse(
        url='/static/index.html',
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={
            'Cache-Control': _static_cache,
        }
    )

@app.get('/robots.txt', status_code=status.HTTP_200_OK)
async def robots():
    return PlainTextResponse(
        content=open(f'{_default_path}/robots.txt', 'r').read(),
        status_code=status.HTTP_200_OK,
        headers={
            'Cache-Control': _static_cache
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



@app.get('/_health', status_code=status.HTTP_200_OK)
async def health():
    return ORJSONResponse(
        content={'status': 'HEALTHY'},
        status_code=status.HTTP_200_OK,
        headers={
            'Cache-Control': f'max-age={45 * SECOND}, s-maxage={45 * SECOND}, {_private_cache}'
        }
    )


@app.get('/_version', status_code=status.HTTP_200_OK)
async def version():
    return ORJSONResponse(
        content={'frontend': __version__, 'backend': backend_version},
        status_code=status.HTTP_200_OK,
        headers={
            'Cache-Control': f'max-age={DAY}, s-maxage={DAY}, private, must-revalidate'
        }
    )

# ----------------------------------------------------------------------------------------------
# Backend API
@app.post('/tune', status_code=status.HTTP_200_OK, response_class=ORJSONResponse)
async def trigger_tune(request: PG_WEB_TUNE_REQUEST):
    # Main website
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
    exclude_names = {'archive_command', 'restore_command', 'archive_cleanup_command', 'recovery_end_command',
                     'log_directory',}
    response: PG_TUNE_RESPONSE = pgtuner.optimize(backend_request)
    content = response.generate_content(
        target=PGTUNER_SCOPE.DATABASE_CONFIG,
        request=backend_request,
        output_format=request.output_format,
        exclude_names=exclude_names,
        backup_settings=False, # request.backup_settings,
    )
    mem_report = response.mem_test(backend_request.options, request.analyze_with_full_connection_use,
                                   ignore_report=False, skip_logger=True)[0]
    response_header = {
        'Content-Type': 'application/json',
        'Cache-Control': f'max-age={30 * SECOND}, private, must-revalidate',
    }
    return ORJSONResponse(content={'mem_report': mem_report, 'config': content},
                          status_code=status.HTTP_200_OK, headers=response_header)
