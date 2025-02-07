import asyncio
import logging
import ipaddress
from datetime import datetime
from math import ceil
from time import perf_counter
from typing import Callable, Any
from collections import defaultdict, deque

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
        raise NotImplementedError('You must implement this method in your subclass.')


# ==============================================================================
# Rate Limiting
class GlobalRateLimitMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp | ASGI3Application, max_requests: int, interval_by_second: int = MINUTE,
                 time_operator: Callable[[], int | float] = perf_counter, accept_scope: str | list[str] = 'http'):
        """
        This is a token-bucket algorithm holding the rate limiting for the global requests. The maximum number of
        requests is determined by the `max_requests` and the `interval_by_second` is the time window to process the
        requests. The `time_operator` is a callable function to get the current time.

        Arguments:
        ---------

        max_requests: int
            The maximum number of requests to be processed in the given time window.

        interval_by_second: int
            The time window in seconds to process the requests.

        time_operator: Callable[[], int | float]
            The callable function to get the current time. The default is `perf_counter` from the `time` module.

        """
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

        # Ignore the rate-limit for private IPv4 & IPv6 addresses
        if ipaddress.ip_address(scope['client'][0]).is_private:
            await self._app(scope, receive, send)
            return None

        # Check how many requests has been processed
        current_time = self._operator()
        diff_time: float = current_time - self._last_request_time
        current_processed_requests = ceil(self.max_requests * diff_time / self.interval_by_second)
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


class UserRateLimitMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp | ASGI3Application, max_requests_per_window: int, window_length: int = 15,
                 time_operator: Callable[[], int | float] = perf_counter, accept_scope: str | list[str] = 'http',
                 cost_function: Callable[[str], int] = lambda x: 1):
        """
        This is a sliding-windows algorithm holding the rate limiting for the user requests. The maximum number of
        requests is determined by the `max_requests_per_user_per_second` and the `window_length` is the time window
        to check the requests. The `time_operator` is a callable function to get the current time.

        Arguments:
        ---------

        max_requests: int
            The maximum number of requests to be processed in the given time window.

        window_length: int
            The window length in seconds to process the requests.

        time_operator: Callable[[], int | float]
            The callable function to get the current time. The default is `perf_counter` from the `time` module.

        """
        super(UserRateLimitMiddleware, self).__init__(app, accept_scope=accept_scope)
        self._costs = cost_function or (lambda x: 1)
        self.max_requests: int = max_requests_per_window
        self.window_length: int = window_length
        self._operator: Callable = time_operator

        # Multiply by two to handle the burst requests
        self._request_storage = defaultdict(lambda : deque(maxlen=self.max_requests * 2))
        self._cleanup_lock = False  # This served as a lock

    async def _cleanup(self):
        if self._cleanup_lock:
            return None
        # Lock the cleanup
        _logger.debug(f'Acquire the object lock to cleanup the requests after {self.window_length * 2} seconds.')
        self._cleanup_lock = True

        # Twice the window_length to schedule
        await asyncio.sleep(self.window_length * 2)
        _logger.debug(f'Request cleanup is triggered.')
        pending_deletion = []
        for user_id_key, request_pool in self._request_storage.items():
            past_datetime = self._operator() - self.window_length
            while request_pool and request_pool[0] <= past_datetime:
                request_pool.popleft()
            if not request_pool:
                pending_deletion.append(user_id_key)

        for user_id_key in pending_deletion:
            del self._request_storage[user_id_key]

        self._cleanup_lock = False
        _logger.debug(f'Request cleanup is completed. Lock is released.')
        return None

    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        if not super()._precheck(scope):
            await self._app(scope, receive, send)
            return None

        # Ignore the rate-limit for private IPv4 & IPv6 addresses
        user, port = scope.get('client')
        user_location = ipaddress.IPv4Address(f'{user}')
        if user_location.is_private or user_location.is_loopback:
            await self._app(scope, receive, send)
            return None

        # Check how many requests has been processed. Get the window interval from its previous `window_length` seconds
        current_time = self._operator()
        past_datetime = current_time - self.window_length
        _request_pool = self._request_storage[f'{user}_{port}']
        while _request_pool and _request_pool[0] <= past_datetime:
            _request_pool.popleft()

        # The cost of the path, max() is to ensure the minimum cost is 1
        path_cost: int = max(1, ceil(self._costs(scope['path'])))
        assert path_cost <= self.max_requests, 'The path cost must be less than or equal to the max requests.'
        if len(_request_pool) > self.max_requests + path_cost:
            message = f'Rate limit exceeded. Try again in {self.window_length:.2f} seconds.'
            _logger.warning(message)
            raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail=message)

        # Minor optimization to reduce un-necessary Python instructions
        if path_cost == 1:
            _request_pool.append(current_time)
        else:
            _request_pool.extend([current_time] * path_cost)

        asyncio.create_task(self._cleanup())
        await self._app(scope, receive, send)

# ==============================================================================
# Header Hardening
class HeaderManageMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp | ASGI3Application, accept_scope: str | list[str] = 'http',
                 static_cache_control: str = 'max-age=600, private, must-revalidate, stale-while-revalidate=60',
                 dynamic_cache_control: str = 'no-cache'):
        super(HeaderManageMiddleware, self).__init__(app, accept_scope=accept_scope)
        # ==============================================================================
        # Auto Cache-Control
        # Static Types:
        _static_fonts = {
            'application/eot', 'application/font', 'application/font-sfnt', 'application/font-woff',
            'application/opentype', 'application/otf', 'application/truetype', 'application/ttf',
            'application/vnd.ms-fontobject', 'application/x-opentype', 'application/x-otf', 'application/x-ttf',
            'font/eot', 'font/otf', 'font/ttf', 'font/x-woff',
        }
        _static_images = {
            'image/bmp', 'image/gif', 'image/jpeg', 'image/jpg', 'image/png', 'image/svg+xml',
            'image/vnd.microsoft.icon', 'image/x-icon'
        }
        _static_docs = {
            'text/plain', 'text/cache-manifest', 'text/markdown', 'text/x-markdown', 'text/calendar',
            'text/richtext', 'text/vcard', 'text/vnd.rim.location.xloc', 'text/vtt',
            'application/xhtml+xml', 'application/x-web-app-manifest+json', 'application/vnd.ms-fontobject',
            'application/vnd.ms-opentype', 'application/vnd.ms-ttf', 'application/vnd.ms-excel',
            # 'text/html', 'text/xml', 'application/xml',
        } # 'text/html', 'text/xml', 'application/xml' if you are served pre-rendered HTML,
        _static_scripts = {
            'application/ecmascript', 'application/javascript', 'application/x-javascript',
            'text/css', 'application/css', 'text/javascript', 'text/x-javascript', 'text/x-json',
        }
        _static = _static_fonts.union(_static_images).union(_static_docs).union(_static_scripts)

        # Dynamic Types:
        # _dynamic_api = {
        #     'application/json', 'application/ld+json', 'application/vnd.api+json', 'application/geo+json',
        #     'application/graphql+json', 'application/manifest+json', 'application/rdf+xml',
        # }
        # _dynamic_scripts = {
        #     'application/x-httpd-cgi', 'application/x-perl', 'application/x-protobuf',
        # }
        # _dynamic_feeds = {
        #     'application/rss+xml', 'application/atom+xml', 'application/gpx+xml',
        # }
        # _dynamic_binary = {
        #     'application/wasm', 'application/vnd.mapbox-vector-tile',
        # }
        # _dynamic_multipart = {
        #     'multipart/bag', 'multipart/mixed',
        # }
        # _dynamic_web = {
        #     'text/html', 'application/xhtml+xml', 'text/x-java-source',
        # }
        self._static = _static
        self._static_cache_control: str = static_cache_control

        self._dynamic = None
        self._dynamic_cache_control: str = dynamic_cache_control

        self._tz = GetTimezone()[0]


    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        if not super()._precheck(scope):
            await self._app(scope, receive, send)
            return None

        # Reset the timezone.
        _request_time: datetime | None = None
        _request_time_in_str: str | None = None
        _response_timestamp: datetime | None = None

        # ASGI with Receive (Request) + Headers
        async def _receive_with_headers() -> Message:
            message = await receive()
            if message['type'] == 'http.request':
                # Timestamp for the request
                nonlocal _request_time_in_str, _request_time
                _request_time = datetime.now(tz=self._tz)
                _request_time_in_str = _request_time.isoformat()

                # headers = MutableHeaders(scope=message)
                # headers.append('X-Request-Datetime', _request_time_in_str.isoformat())
            return message

        # ASGI with Send (Response) + Headers
        async def _send_with_headers(message: Message | ASGISendEvent) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                # Cache-Control headers
                if 'Cache-Control' not in headers:  # Override only if not set
                    content_type = headers.get('Content-Type', '').split(';')[0].strip()
                    if self._static and content_type in self._static:
                        headers.append('Cache-Control', self._static_cache_control)
                    # elif self._dynamic and content_type in self._dynamic:
                    #     headers.append('Cache-Control', self._dynamic_cache_control)

                # Timestamp for the response
                nonlocal _request_time_in_str, _response_timestamp
                if _request_time_in_str is not None:
                    _response_timestamp = datetime.now(tz=self._tz)
                    headers.append('X-Response-Datetime',_response_timestamp.isoformat())
                    headers.append('X-Request-Datetime', _request_time_in_str)

                    _duration = (_response_timestamp - _request_time).microseconds / K10
                    headers.append('X-Response-DurationInMs', f'{_duration:.2f}')

            await send(message)

        await self._app(scope, _receive_with_headers, _send_with_headers)
