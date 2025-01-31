import uvicorn
import web
import os

from src.utils.env import OsGetEnvBool

if __name__ == "__main__":
    if os.getenv(f'PORT') is not None:
        _port: int = int(os.getenv(f'PORT'))
    else:
        _port: int = int(os.getenv('UV_PORT', '8001'))
    _host: str = os.getenv('UV_HOST', '0.0.0.0')
    _workers: int = int(os.getenv('UV_WORKERS', '1'))
    _access_log: bool = OsGetEnvBool('UV_ACCESS_LOG', True)
    _http = os.getenv('UV_HTTP', 'auto')
    _loop = os.getenv('UV_LOOP', 'auto')
    _proxy_headers = OsGetEnvBool('UV_PROXY_HEADERS', False)
    _server_header = OsGetEnvBool('UV_SERVER_HEADER', False)
    _date_header = OsGetEnvBool('UV_DATE_HEADER', False)
    _use_colors = OsGetEnvBool('UV_USE_COLORS', False)
    _limit_concurrency = int(os.getenv('UV_LIMIT_CONCURRENCY', '1000'))

    # Fallback if not found
    try:
        if _loop == 'uvloop':
            import uvloop
    except (ImportError, ModuleNotFoundError) as e:
        _loop = 'auto'

    uvicorn.run(web.app, host=_host, port=_port, access_log=_access_log, workers=_workers,
                http=_http, loop=_loop, limit_concurrency=_limit_concurrency,
                proxy_headers=_proxy_headers, server_header=_server_header, date_header=_date_header,
                use_colors=_use_colors)