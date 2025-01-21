import asyncio
import logging
import random
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi import status
from fastapi.responses import ORJSONResponse, PlainTextResponse, RedirectResponse
from pydantic import ValidationError
from starlette.types import ASGIApp
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src import pgtuner
from src.static.vars import APP_NAME_UPPER, APP_NAME_LOWER, __version__ as backend_version, HOUR, Ki
from src.tuner.data.scope import PGTUNER_SCOPE
from src.tuner.pg_dataclass import PG_TUNE_RESPONSE, PG_TUNE_REQUEST
from web.middlewares.compressor import CompressMiddleware
from web.middlewares.middlewares import GlobalRateLimitMiddleware, HeaderManageMiddleware
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
__version__ = '0.0.1'
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
try:
    from starlette.middleware.sessions import SessionMiddleware # itsdangerous
    import string
    SECRET_KEY = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=HOUR, https_only=False)  # 1-hour session
    if __debug__:
        _logger.debug(f'The session middleware has been added to the application with secret key {SECRET_KEY}')
except (ImportError, ModuleNotFoundError) as e:
    _logger.warning('The session middleware has not been added to the application due to the missing dependencies. '
                    f'\nPlease install more dependencies: {e}')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True,
                   allow_methods=['GET', 'POST'], allow_headers=[], max_age=600)
app.add_middleware(GlobalRateLimitMiddleware, max_requests=50, interval_by_second=1)
app.add_middleware(HeaderManageMiddleware)
app.add_middleware(CompressMiddleware, minimum_size=(Ki >> 1), compress_level=3)
_logger.info('The middlewares have been added to the application ...')

_logger.info('Mounting the static files to the application ...')
try:
    app.mount('/static', StaticFiles(directory='./web/ui/static'), name='static')
    _logger.info('The static files have been added to the application ...')
except (FileNotFoundError, RuntimeError) as e:
    _logger.warning(f'The static files have not been mounted: {e}')
    raise e



@app.get('/', status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def root():
    return RedirectResponse(url='/static/index.min.html', status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get('/min', status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def root_min():
    return RedirectResponse(url='/static/index.min.html', status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@app.get('/dev', status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def root_min():
    return RedirectResponse(url='/static/index.html', status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get('/_health', status_code=status.HTTP_200_OK)
async def health():
    return {'status': 'HEALTHY'}


@app.get('/_version', status_code=status.HTTP_200_OK)
async def version():
    return ORJSONResponse(content={'frontend': __version__, 'backend': backend_version}, status_code=status.HTTP_200_OK,
                          headers={'Cache-Control': 'max-age=360'})

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
    # pprint(backend_request.options)
    exclude_names = {'archive_command', 'restore_command', 'archive_cleanup_command', 'recovery_end_command'}
    response: PG_TUNE_RESPONSE = pgtuner.optimize(backend_request)
    content = response.generate_content(target=PGTUNER_SCOPE.DATABASE_CONFIG, request=backend_request,
                                        output_format=request.output_format, backup_settings=request.backup_settings,
                                        exclude_names=exclude_names)
    if isinstance(content, dict):
        mem_report = response.mem_test(backend_request.options, use_full_connection=False, ignore_report=True)[0]
        return ORJSONResponse(content={'mem_report': mem_report, 'config': content},
                              status_code=status.HTTP_200_OK, headers={'Cache-Control': 'max-age=30'})
    return PlainTextResponse(content=content, status_code=status.HTTP_200_OK, headers={'Cache-Control': 'max-age=30'})


