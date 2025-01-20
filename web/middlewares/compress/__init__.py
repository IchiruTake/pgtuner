"""
This module is the public interface for the compressor middlewares. Applied fo ASGI applications such as Starlette,
FastAPI, etc. The supported list of compression algorithms are depending on the installed libraries. But
currently, the supported algorithms are:
- zstd: Zstandard (Zstd) offers a high compression ratio and fast decompression speed. It is designed to be fast and
    efficient for web servers and other applications that require high-speed compression and decompression. This
    algorithm is suitable for compressing large files and data streams, and was developed by Facebook in 2016.
- gzip: Gzip is a widely used compression algorithm that offers a good balance of compression ratio and speed. It is
    commonly used for compressing web content, such as HTML, CSS, and JavaScript files, as well as other types of data.
    Gzip is supported by most web browsers and servers, making it a popular choice for web developers.
- brotli: Brotli is a relatively new compression algorithm that was developed by Google in 2015. It offers a higher
    compression ratio than Gzip and is designed to be fast and efficient for web content. Brotli is supported by modern
    web browsers and servers, and is becoming increasingly popular for compressing web content.

Non-supported algorithms:
- lzma: LZMA is a compression algorithm that offers a high compression ratio and good compression speed. It is commonly
    used for compressing software packages and other types of data that require high compression ratios. LZMA is
    supported by most modern operating systems and is widely used in software distribution and archiving.
- deflate: Deflate is a compression algorithm that is based on LZ77 and Huffman coding. It is commonly used for
    compressing web content, such as HTML, CSS, and JavaScript files. Deflate is supported by most web browsers and
    servers, making it a popular choice for web developers.
- bzip2: Bzip2 is a compression algorithm that offers a high compression ratio and good compression speed. It is commonly
    used for compressing software packages and other types of data that require high compression ratios. Bzip2 is
    supported by most modern operating systems and is widely used in software distribution and archiving.

The design is highly inspired by the Starlette's GZipMiddleware, https://github.com/Zaczero/starlette-compress,
and https://github.com/tuffnatty/zstd-asgi

"""

import re
from enum import Enum
from collections import defaultdict
from functools import lru_cache
from random import shuffle, seed
from typing import NoReturn

from starlette.datastructures import Headers, MutableHeaders
# from starlette.middleware.gzip import GZipMiddleware as _GZip

import logging
from datetime import datetime
from math import ceil

from src.static.vars import APP_NAME_UPPER, Ki
from starlette.types import ASGIApp, Send, Receive, Message, Scope as StarletteScope
from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, Scope as ASGI3Scope
from web.middlewares.middlewares import BaseMiddleware

try:
    from web.middlewares.compress._gzip import GZipResponder
except (ImportError, ModuleNotFoundError):
    GZipResponder = None

try:
    from web.middlewares.compress._zstd import ZstdResponder
except (ImportError, ModuleNotFoundError):
    ZstdResponder = None

# ==============================================================================
_logger = logging.getLogger(APP_NAME_UPPER)
_SAMPLE_SIZE: int = 300
seed(datetime.now().timestamp())    # Seed the random number generator

class ALG_SELECT(Enum):
    PRIORITY_FIRST = 0
    PRIORITY_SAMPLING = 1
    PRIORITY_METHOD = 2
    SAMPLING = 3


@lru_cache(maxsize=Ki >> 2) # 256 entries
def _parse_accept_encoding(accept_encoding: str, supported_algorithms: tuple[str, ...],
                           ignore_wildcard: bool = True) -> dict[str, float]:
    """
    Parse the accept encoding header and return a dictionary of supported encodings.
    Arguments:
    ---------

    accept_encoding: str
        The accept encoding header string.

    supported_algorithms: tuple[str, ...]
        A tuple of supported algorithms.

    ignore_wildcard: bool
        Ignore the wildcard symbol in the accept encoding header. Default to True

    """
    if not supported_algorithms:
        return {}
    result = {}
    for algorithm in accept_encoding.split(','):
        algorithm_breakdown: list[str] = algorithm.strip().split(';')
        alg = algorithm[0]
        if len(algorithm_breakdown) == 1: # Found no relative quality 'weighted' value
            w = 1.0
        else:
            try:
                w = float(algorithm_breakdown[1].split('=')[1])
                if w > 1.0 or w < 0.01: # Skip invalid relative weight, and ignore too small value
                    _logger.warning(f"Invalid relative weight value: {w}. Must be in supported range between 0.01 and "
                                    f"1.0. The magic number 0.01 is to exclude too small weight value")
                    continue
            except ValueError: # For invalid 'Accept-Encoding' header -> Skip
                continue
        if alg == '*':
            if ignore_wildcard:
                continue
            else:
                # Use the highest quality value for all supported algorithms
                alg = supported_algorithms[0]
        if alg in supported_algorithms:
            if alg in result:
                result[alg] = max(result[alg], w)   # Force it to be the highest quality value
            else:
                result[alg] = w

    return result


def _select_accept_encoding(accept_encoding: dict[str, float], sampling_list: tuple[str, ...],
                            method: ALG_SELECT) -> str:
    if len(accept_encoding) == 0:
        return ''
    elif len(accept_encoding) == 1:
        return accept_encoding.popitem()[0]

    # Priority selection
    if method in (ALG_SELECT.PRIORITY_FIRST, ALG_SELECT.PRIORITY_SAMPLING, ALG_SELECT.PRIORITY_METHOD):
        # If multiple algorithms have the same weight, we select the first on
        if method in (ALG_SELECT.PRIORITY_FIRST, ALG_SELECT.PRIORITY_METHOD):
            if method == ALG_SELECT.PRIORITY_METHOD:
                for alg in sampling_list:
                    if alg in accept_encoding:
                        return alg
            return max(accept_encoding, key=accept_encoding.get)

        else:
            max_weight = max(accept_encoding.values())
            max_weight_algorithms = [k for k, v in accept_encoding.items() if v == max_weight]
            shuffle(max_weight_algorithms)
            return max_weight_algorithms[0]
    elif method == ALG_SELECT.SAMPLING:
        # Sampling algorithm
        sample_space = []
        for alg, w in accept_encoding.items():
            sample_space.extend([alg] * ceil(w * _SAMPLE_SIZE))
        shuffle(sample_space)
        return sample_space[0]

    raise ValueError('Invalid selection algorithm')


# Based on
# - https://github.com/h5bp/server-configs-nginx/blob/main/h5bp/web_performance/compression.conf#L38
# - https://developers.cloudflare.com/speed/optimization/content/compression/
_compress_content_types: set[str] = {
    'application/atom+xml',
    'application/eot',
    'application/font',
    'application/font-sfnt',
    'application/font-woff',
    'application/geo+json',
    'application/gpx+xml',
    'application/graphql+json',
    'application/javascript',
    'application/javascript-binast',
    'application/json',
    'application/ld+json',
    'application/manifest+json',
    'application/opentype',
    'application/otf',
    'application/rdf+xml',
    'application/rss+xml',
    'application/truetype',
    'application/ttf',
    'application/vnd.api+json',
    'application/vnd.mapbox-vector-tile',
    'application/vnd.ms-fontobject',
    'application/wasm',
    'application/x-httpd-cgi',
    'application/x-javascript',
    'application/x-opentype',
    'application/x-otf',
    'application/x-perl',
    'application/x-protobuf',
    'application/x-ttf',
    'application/x-web-app-manifest+json',
    'application/xhtml+xml',
    'application/xml',
    'font/eot',
    'font/otf',
    'font/ttf',
    'font/x-woff',
    'image/bmp',
    'image/svg+xml',
    'image/vnd.microsoft.icon',
    'image/x-icon',
    'multipart/bag',
    'multipart/mixed',
    'text/cache-manifest',
    'text/calendar',
    'text/css',
    'text/html',
    'text/javascript',
    'text/js',
    'text/markdown',
    'text/plain',
    'text/richtext',
    'text/vcard',
    'text/vnd.rim.location.xloc',
    'text/vtt',
    'text/x-component',
    'text/x-cross-domain-policy',
    'text/x-java-source',
    'text/x-markdown',
    'text/x-script',
    'text/xml',
}

# ==============================================================================
class CompressMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp, *, minimum_size: int = Ki >> 1, compress_level: int = 3,
                 method: ALG_SELECT = ALG_SELECT.PRIORITY_FIRST, **kwargs) -> None:
        super(CompressMiddleware, self).__init__(app, accept_scope='http')
        self._method = method
        self._compressor: dict[str, BaseResponder] = defaultdict()

        # Compressor
        if ZstdResponder is not None and kwargs.get('zstd-enabled', True):
            self._compressor['zstd'] = (
                ZstdResponder(self._app,
                              minimum_size=kwargs.get('zstd-minimum_size', minimum_size),
                              compress_level=kwargs.get('zstd-compress_level', compress_level),
                              include_paths=kwargs.get('zstd-include_paths', None),
                              exclude_paths=kwargs.get('zstd-exclude_paths', None),
                              include_content_types=kwargs.get('zstd-include_content_types', None),
                              exclude_content_types=kwargs.get('zstd-exclude_content_types', None),
                              )
            )
        if GZipResponder is not None and kwargs.get('gzip-enabled', True):
            self._compressor['gzip'] = (
                GZipResponder(self._app,
                              minimum_size=kwargs.get('gzip-minimum_size', minimum_size),
                              compress_level=kwargs.get('gzip-compress_level', compress_level),
                              include_paths=kwargs.get('gzip-include_paths', None),
                              exclude_paths=kwargs.get('gzip-exclude_paths', None),
                              include_content_types=kwargs.get('gzip-include_content_types', None),
                              exclude_content_types=kwargs.get('gzip-exclude_content_types', None))
            )
        self._compressor_keys = tuple(self._compressor.keys())

    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        # Check if the scope['type'] is valid (http)
        if not super()._precheck(scope):
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)

        # Try to discard the request if the content is already compressed (Content-Encoding headers is found)
        if headers.get('Content-Encoding', None) is not None:
            await self._app(scope, receive, send)
            return

        accept_encoding_string: str = headers.get('Accept-Encoding', '').strip()
        if not accept_encoding_string:
            await self._app(scope, receive, send)
            return

        # Accept-Encoding could be single or in multiple-format
        accept_encoding_dict = _parse_accept_encoding(accept_encoding_string, ignore_wildcard=True,
                                                      supported_algorithms=self._compressor_keys)
        alg = _select_accept_encoding(accept_encoding_dict, sampling_list=('zstd', 'gzip'),
                                      method=self._method)
        if alg == '' or alg not in self._compressor:
            await self._app(scope, receive, send)
            return

        _compressor = self._compressor[alg]
        if not await _compressor.path_validate(scope) or not await _compressor.content_type_validate(headers):
            await self._app(scope, receive, send)
            return

        return await _compressor(scope, receive, send)


async def unattached_send(message: Message) -> None | NoReturn:
    raise RuntimeError('send() method not attached to the middleware')


class BaseResponder(BaseMiddleware):
    def __init__(self, app: ASGIApp, content_name: str, minimum_size: int, compress_level: int,
                 include_paths: set[str, ...] = None, exclude_paths: set[str, ...] = None,
                 include_content_types: set[str, ...] = None, exclude_content_types: set[str, ...] = None):
        assert minimum_size >= 0, 'Minimum size must be greater than or equal to 0'
        # Ensure :var:`include_paths` and :var:`exclude_paths` are mutually exclusive
        assert not (include_paths and exclude_paths), \
            'Include and exclude paths are mutually exclusive'
        # Ensure :var:`include_content_types` and :var:`exclude_content_types` are mutually exclusive
        assert not (include_content_types and exclude_content_types), \
            'Include and exclude content types are mutually exclusive'
        super(BaseResponder, self).__init__(app, accept_scope='http')
        self._content_name = content_name
        self._minimum_size = minimum_size
        self._compress_level = compress_level
        self._include_paths = [re.compile(p) for p in include_paths] or []
        self._exclude_paths = [re.compile(p) for p in exclude_paths] or []
        self._allowed_content_types = _compress_content_types
        if include_content_types:
            self._allowed_content_types = set(include_content_types)
        elif exclude_content_types:
            self._allowed_content_types = _compress_content_types - set(exclude_content_types)

        # -------------------------------------------------------------------------------------
        # Cache thing back and forth
        self._send: Send = unattached_send
        self._initial_message: Message | None = {}
        self._is_response_started = False
        self._content_encoding_set = False

        # This is here to prevent file opening
        self._compress_buffer = None
        self._compress_file = None

    def reset_cache(self) -> None:
        self._initial_message: Message | None = None
        self._is_response_started = False
        self._content_encoding_set = False

    async def path_validate(self, scope: StarletteScope | ASGI3Scope) -> bool:
        # Check if the path is allowed to proceed or not
        ok_path: bool = False
        if self._include_paths or self._exclude_paths:
            scope_path = scope.get('path', '')
            if self._include_paths and any(p.search(scope_path) for p in self._include_paths):
                ok_path = True  # OK to proceed
            elif self._exclude_paths and not any(p.search(scope_path) for p in self._exclude_paths):
                ok_path = True  # OK to proceed
        return ok_path

    async def content_type_validate(self, headers: MutableHeaders | Headers) -> bool:
        # Check if the content type is allowed to proceed or not
        if content_type := headers.get('Content-Type', ''):
            basic_content_type = content_type.split(';', maxsplit=1)[0].strip()
            return basic_content_type in self._allowed_content_types
        return False

    async def __call__(self, scope: StarletteScope | ASGI3Scope, receive: ASGIReceiveCallable | Receive,
                       send: ASGISendCallable | Send) -> None:
        raise NotImplementedError('Method must be implemented in the subclass')
