import asyncio
import logging
import ipaddress
from math import ceil
from time import perf_counter
from typing import Callable
from collections import defaultdict, deque

from src.static.c_timezone import GetTimezone
from src.utils.static import APP_NAME_UPPER, K10
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
class RateLimitMiddleware(BaseMiddleware):
    """
    This clas is a merged version of GlobalRateLimitMiddleware and UserRateLimitMiddleware, responsible to handle
    the rate limiting for the global and user requests. The reason for the merged is to reduce the cost of excessive
    middleware calls.

    Arguments:
    ---------

    max_requests: int && interval: int
        The maximum number of requests to be processed in the request bucket. The interval is the time window in
        seconds to process the requests. Applied for the global rate limiting.

    max_requests_per_window: int && window_length: int
        The maximum number of requests to be processed in the given time window. The window_length is the time window
        in seconds to process the requests. Applied for the user rate limiting.

    cost_function: Callable[[str], int]
        The blackbox callable function to calculate the cost of the request (based on the provided path). The default is
        (lambda x: 1) meant that every HTTP request has a cost of 1. A cost of 0 is not allowed. For example, if
        the request is heavy, we can increase the cost to 2 meant that it took 2 tokens from the bucket or in the
        user time window.

    time_operator: Callable[[], int | float]
        The callable function to get the current time. The default is `perf_counter` from the `time` module.
        You can use `time.time` or `time.monotonic` as well, but its unit must be measured in seconds.

    """

    def __init__(self, app: ASGIApp | ASGI3Application,
                 max_requests: int | float = int(100 * 60 * 0.9), max_requests_per_window: int = 10,
                 interval: int | float = 60, window_length: int | float = 15,
                 cost_function: Callable[[str], int] = lambda x: 1,
                 time_operator: Callable[[], int | float] = perf_counter, accept_scope: str | list[str] = 'http',
                 ignore_if_private_loopback: bool = True):
        super(RateLimitMiddleware, self).__init__(app, accept_scope=accept_scope)
        # Others
        self._cost_function = cost_function or (lambda x: 1)    # Ensure the cost function is not None
        self._operator: Callable = time_operator
        self._ignore_if_private_loopback: bool = ignore_if_private_loopback

        # Global Rate Limiting
        self.max_requests: int | float = max_requests
        self.interval: int = interval
        self._refill_rate: float = self.max_requests / self.interval    # Minor optimization
        self._capacity: int | float = self.max_requests
        self._last_request_time: float = self._operator()

        # User Rate Limiting
        self.max_requests_per_window: int = max_requests_per_window
        self.window_length: int = window_length
        self._user_storage = defaultdict(lambda: deque(maxlen=self.max_requests_per_window * 2))
        self._cleanup_lock = False  # This served as a lock

        # Validation
        assert self.max_requests_per_window > 0, 'The max requests per window must be greater than 0.'
        assert self.max_requests > 0, 'The max requests must be greater than 0.'
        assert self.interval > 0, 'The interval by second must be greater than 0.'
        assert self.window_length > 0, 'The window length must be greater than 0.'
        assert self.max_requests_per_window <= self.max_requests, \
            'The max requests per window must be less than or equal to the max requests.'
        user_limit = self.max_requests_per_window / self.window_length
        global_limit = self.max_requests / self.interval
        assert user_limit < global_limit, 'The user limit must be less than or equal to the global limit.'

    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        if not super()._precheck(scope):
            await self._app(scope, receive, send)
            return None

        # User-rate limiting is called first, then the global rate limiting
        user, port = scope.get('client')
        user_location = ipaddress.IPv4Address(f'{user}')
        if self._ignore_if_private_loopback and (user_location.is_private or user_location.is_loopback):
            await self._app(scope, receive, send)
            return None
        path_cost: int = max(1, ceil(self._cost_function(scope['path'])))
        assert path_cost <= self.max_requests, 'The path cost must be less than or equal to the max requests.'
        assert path_cost <= self.max_requests_per_window, \
            'The path cost must be less than or equal to the max requests per user.'

        # Calculate time interval
        current_time = self._operator()

        # User rate limiting. It is best to keep the pool of user rate is small to minimize the memory usage,
        # and time different
        past_datetime = current_time - self.window_length
        _request_pool = self._user_storage[f'{user}_{port}']
        while _request_pool and _request_pool[0] <= past_datetime:
            _request_pool.popleft()

        # Global rate limiting.
        diff_time: float = current_time - self._last_request_time
        self._capacity = min(self._capacity + self._refill_rate * diff_time - path_cost,
                             self.max_requests)
        self._last_request_time = current_time

        # Validation
        if len(_request_pool) > self.max_requests_per_window + path_cost:
            message = f'Your request limit is exceeded. Try again in {self.window_length / 2:.2f} seconds.'
            _logger.warning(message)
            raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail=message)
        if self._capacity <= 0:
            message = f'The server limit exceeded. Try again in some seconds.'
            _logger.warning(message)
            raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail=message)

        # Minor optimization to reduce un-necessary Python instructions
        if path_cost == 1:
            _request_pool.append(current_time)
        else:
            _request_pool.extend([current_time] * path_cost)

        if not self._cleanup_lock:
            # Minor fast-path to reduce stress on the asyncio event_loop(). Remove don't impact the code
            asyncio.create_task(self._cleanup())
        await self._app(scope, receive, send)

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
        for user_id_key, request_pool in self._user_storage.items():
            past_datetime = self._operator() - self.window_length
            while request_pool and request_pool[0] <= past_datetime:
                request_pool.popleft()
            if not request_pool:
                pending_deletion.append(user_id_key)

        for user_id_key in pending_deletion:
            del self._user_storage[user_id_key]

        self._cleanup_lock = False
        _logger.debug(f'Request cleanup is completed. Lock is released.')
        return None

# ==============================================================================
# Header Hardening
class HeaderManageMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp | ASGI3Application, accept_scope: str | list[str] = 'http',
                 static_cache_control: str = 'max-age=600, private, must-revalidate, stale-while-revalidate=60',
                 dynamic_cache_control: str = 'no-cache',
                 time_operator: Callable[[], int | float] = perf_counter):
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
        self._time_operator: Callable = time_operator


    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        if not super()._precheck(scope):
            await self._app(scope, receive, send)
            return None

        # Trigger the time
        _request_time: float = self._time_operator()

        # ASGI with Send (Response) + Headers
        async def _send_with_headers(message: Message | ASGISendEvent) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)

                nonlocal _request_time
                headers.append('X-Response-FullTime', f'{(perf_counter() - _request_time) * K10:.2f}ms')

                # Cache-Control headers
                if 'Cache-Control' not in headers:  # Override only if not set
                    content_type = headers.get('Content-Type', '').split(';')[0].strip()
                    if self._static and content_type in self._static:
                        headers.append('Cache-Control', self._static_cache_control)
                    # elif self._dynamic and content_type in self._dynamic:
                    #     headers.append('Cache-Control', self._dynamic_cache_control)
                pass
            await send(message)

        await self._app(scope, receive, _send_with_headers)
