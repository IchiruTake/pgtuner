from typing import Literal

import uvicorn
import web
import os

from src.static.vars import YEAR
from src.utils.env import OsGetEnvBool

if __name__ == "__main__":
    if os.getenv(f'PORT') is not None:
        _port: int = int(os.getenv(f'PORT'))
    else:
        _port: int = int(os.getenv('UV_PORT', '8001'))
    _host: str = os.getenv('UV_HOST', '0.0.0.0')
    _workers: int = int(os.getenv('UV_WORKERS', '1'))
    _access_log: bool = OsGetEnvBool('UV_ACCESS_LOG', True)
    _http: Literal["auto", "h11", "httptools"] = os.getenv('UV_HTTP', 'auto')
    _loop: Literal["none", "auto", "asyncio", "uvloop"] = os.getenv('UV_LOOP', 'auto')
    _proxy_headers = OsGetEnvBool('UV_PROXY_HEADERS', False)
    _server_header = OsGetEnvBool('UV_SERVER_HEADER', False)
    _date_header = OsGetEnvBool('UV_DATE_HEADER', False)
    _use_colors = OsGetEnvBool('UV_USE_COLORS', False)
    _limit_concurrency = int(os.getenv('UV_LIMIT_CONCURRENCY', '1000'))

    # Fallback if not found
    try:
        if _loop == 'uvloop':
            # This is available only on Linux server only
            import uvloop
    except (ImportError, ModuleNotFoundError) as e:
        _loop = 'auto'

    # ==============================================================================
    # Offload the headers
    # https://scotthelme.co.uk/hardening-your-http-response-headers
    # https://faun.pub/hardening-the-http-security-headers-with-aws-lambda-edge-and-cloudfront-2e2da1ae4d83
    # https://scotthelme.co.uk/content-security-policy-an-introduction/
    # https://scotthelme.co.uk/a-new-security-header-feature-policy/?ref=scotthelme.co.uk
    # https://scotthelme.co.uk/content-security-policy-an-introduction/
    # https://www.keycdn.com/blog/http-security-headers <- Good one
    # https://www.invicti.com/blog/web-security/http-security-headers/
    _content_security = [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' ",
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' ",
        "img-src 'self' https://cdn.jsdelivr.net data: 'unsafe-inline'",
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com https://fonts.googleapis.com ",

        # Unused but can be enabled
        # "connect-src 'self'",
        # "object-src 'none'",
        # "media-src 'none'",
        # "frame-src 'none'",
        # "base-uri 'self'",
    ]

    _SecurityHeaders = [
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security
        ('Strict-Transport-Security', f'max-age={YEAR}; includeSubDomains; preload'),

        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options
        ('X-Content-Type-Options', "nosniff"),

        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-XSS-Protection
        ('X-XSS-Protection', '1; mode=block'),

        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options
        ('X-Frame-Options', 'DENY'),

        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy
        ('Content-Security-Policy', '; '.join(_content_security)),

        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy
        # TODO: Need to evaluate this settings
        # 'Permissions-Policy': "geolocation none; midi none; notifications none; push none; sync-xhr none; "
        #                   "microphone none; camera none; magnetometer none; gyroscope none; speaker self; "
        #                   "vibrate none; fullscreen self; payment none;",

        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy
        # https://scotthelme.co.uk/a-new-security-header-referrer-policy/
        ('Referrer-Policy', 'strict-origin-when-cross-origin'),

        # TODO: Need to evaluate this settings
        # 'Access-Control-Expose-Headers': ','.join(_expose_headers),

        # Others
        ('X-Powered-By', 'Uvicorn'),
        ('Server', 'Starlette'),
    ]

    uvicorn.run(web.app, host=_host, port=_port, access_log=_access_log, workers=_workers,
                http=_http, loop=_loop, limit_concurrency=_limit_concurrency,
                proxy_headers=_proxy_headers, server_header=_server_header, date_header=_date_header,
                use_colors=_use_colors, headers=_SecurityHeaders)