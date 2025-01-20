import logging
from datetime import datetime
from math import ceil
from time import perf_counter
from typing import Callable, Any

from src.static.c_timezone import GetTimezone
from src.static.vars import MINUTE, YEAR, APP_NAME_UPPER, K10
from starlette.types import ASGIApp, Send, Receive, Message, Scope as StarletteScope
from starlette.exceptions import HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from starlette.datastructures import MutableHeaders
from asgiref.typing import ASGI3Application, ASGIReceiveCallable, ASGISendCallable, ASGISendEvent, Scope as ASGI3Scope

# ==============================================================================
_logger = logging.getLogger(APP_NAME_UPPER)


# Rate Limiting
class BaseMiddleware:
    def __init__(self, application: ASGIApp | ASGI3Application, accept_scope: str | list[str]  = 'http'):
        self._app: ASGIApp | ASGI3Application = application
        _accept = ['http', 'websocket', 'lifespan']
        msg: str = f"Invalid scope: {accept_scope}. Must be one or part of {', '.join(_accept)}, or None."
        if isinstance(accept_scope, str) and accept_scope not in _accept:
            logging.critical(msg)
            raise ValueError(msg)
        elif isinstance(accept_scope, list) and any(scope not in _accept for scope in accept_scope):
            logging.critical(msg)
            raise ValueError(msg)
        elif accept_scope is None:
            logging.critical(msg)
            raise ValueError(msg)
        self._scope: str = ';'.join(accept_scope)

    def _precheck(self, scope: StarletteScope | ASGI3Scope) -> bool:
        return scope['type'] not in self._scope

    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        raise NotImplementedError("You must implement this method in your subclass.")


# ==============================================================================
# Rate Limiting
class GlobalRateLimitMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp | ASGI3Application, max_requests: int, interval_by_second: int = MINUTE,
                 time_operator: Callable[[], int | float] = perf_counter, accept_scope: str | list[str] = 'http'):
        super(GlobalRateLimitMiddleware, self).__init__(app, accept_scope=accept_scope)
        self.max_requests: int = max_requests
        self.interval_by_second: int = interval_by_second
        self._operator: Callable = time_operator
        self._num_processed_requests: int = 0
        self._last_request_time: float = self._operator()

    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        if not super()._precheck(scope):
            await self._app(scope, receive, send)
            return None

        # Check how many requests has been processed
        current_time = self._operator()
        diff_time: float = current_time - self._last_request_time
        current_processed_requests = ceil(self.max_requests * diff_time) // self.interval_by_second
        self._num_processed_requests = max(0, self._num_processed_requests - current_processed_requests) + 1
        self._last_request_time = current_time

        # Rate Limiting Decision
        if self._num_processed_requests > self.max_requests:
            remaining_requests = self._num_processed_requests - self.max_requests
            est_time = remaining_requests * self.interval_by_second / self.max_requests
            message = (f'Rate limit exceeded ({remaining_requests} requests remaining). '
                       f'Try again in {est_time:.2f} seconds.')
            _logger.warning(message)
            raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail=message)

        # OK to process the request
        await self._app(scope, receive, send)


# ==============================================================================
# Header Hardening
class HeaderManageMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp | ASGI3Application, accept_scope: str | list[str] = 'http'):
        super(HeaderManageMiddleware, self).__init__(app, accept_scope=accept_scope)
        # Offload the headers
        # https://scotthelme.co.uk/hardening-your-http-response-headers
        # https://faun.pub/hardening-the-http-security-headers-with-aws-lambda-edge-and-cloudfront-2e2da1ae4d83
        # https://scotthelme.co.uk/content-security-policy-an-introduction/
        # https://scotthelme.co.uk/a-new-security-header-feature-policy/?ref=scotthelme.co.uk
        # https://scotthelme.co.uk/content-security-policy-an-introduction/

        _expose_headers = ['X-Request-Datetime', 'X-Response-Datetime', 'X-Response-DurationInMs',
                           'Content-Length', 'Content-Type', 'Transfer-Encoding', 'Content-Encoding']

        self._hard_headers: dict[str, Any] = {
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security
            'Strict-Transport-Security': f'max-age={YEAR}; includeSubDomains',

            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options
            'X-Content-Type-Options': "nosniff",
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-XSS-Protection
            'X-XSS-Protection': '1; mode=block',

            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Feature-Policy -> Replaced by
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy
            # TODO: Need to evaluate this settings
            # 'Feature-Policy': "geolocation none; midi none; notifications none; push none; sync-xhr none; "
            #                   "microphone none; camera none; magnetometer none; gyroscope none; speaker self; "
            #                   "vibrate none; fullscreen self; payment none;",

            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy
            # TODO: Need to evaluate this settings
            # 'Content-Security-Policy': r"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; ",
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy
            # TODO: Need to evaluate this settings
            # 'Referrer-Policy': 'strict-origin-when-cross-origin',
            # TODO: Need to evaluate this settings
            # 'Access-Control-Expose-Headers': ','.join(_expose_headers),
        }
        # FUTURE: Disable as in experimental in 2025
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy (Replaces Feature-Policy)
        # self._hard_headers['Permissions-Policy'] = self._hard_headers['Feature-Policy']

    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        if not super()._precheck(scope):
            await self._app(scope, receive, send)
            return None

        # Reset the timezone.
        _timezone = GetTimezone()[0]
        _request_time: datetime | None = None
        _request_time_in_str: str | None = None
        _response_timestamp: datetime | None = None

        # ASGI with Receive (Request) + Headers
        async def _receive_with_headers() -> Message:
            message = await receive()
            if message['type'] == 'http.request':
                # Timestamp for the request
                nonlocal _request_time_in_str, _request_time
                _request_time = datetime.now(tz=_timezone)
                _request_time_in_str = _request_time.isoformat()

                # headers = MutableHeaders(scope=message)
                # headers.append('X-Request-Datetime', _request_time_in_str.isoformat())
            return message

        # ASGI with Send (Response) + Headers
        async def _send_with_headers(message: Message | ASGISendEvent) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                for key, value in self._hard_headers.items():
                    headers.append(key, value)

                # Timestamp for the response
                nonlocal _request_time_in_str, _response_timestamp
                if _request_time_in_str is not None:
                    _response_timestamp = datetime.now(tz=_timezone)
                    headers.append('X-Response-Datetime',_response_timestamp.isoformat())
                    headers.append('X-Request-Datetime', _request_time_in_str)

                    _duration = (_response_timestamp - _request_time).microseconds / K10
                    headers.append('X-Response-DurationInMs', f'{_duration:.2f}')
                elif __debug__:
                    _logger.warning('P3: The request timestamp is not found in the current codebase to calculate the '
                                    'duration. Developers are urged to review the code.')

            await send(message)

        await self._app(scope, _receive_with_headers, _send_with_headers)
