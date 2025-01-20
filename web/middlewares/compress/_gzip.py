import gzip
from io import BytesIO

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from web.middlewares.compress import BaseResponder

__all__ = ['GZipResponder']
class GZipResponder(BaseResponder):
    def __init__(self, app: ASGIApp, minimum_size: int, compress_level: int,
                 include_paths: set[str, ...] = None, exclude_paths: set[str, ...] = None,
                 include_content_types: set[str, ...] = None, exclude_content_types: set[str, ...] = None):
        super(GZipResponder, self).__init__(
            app, content_name='gzip', minimum_size=minimum_size, compress_level=compress_level,
            include_paths=include_paths, exclude_paths=exclude_paths,
            include_content_types=include_content_types, exclude_content_types=exclude_content_types)
        self._compress_buffer = BytesIO()
        self._compress_file = gzip.GzipFile(mode="wb", fileobj=self._compress_buffer,
                                            compresslevel=self._minimum_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.reset_cache()
        self._send = send       # Re-cache the custom send function every call
        with self._compress_buffer, self._compress_file:  # This is here to prevent file opening
            await self._app(scope, receive, self._compress_and_send)

    async def _compress_and_send(self, message: Message) -> None:
        message_type: str = message['type']
        if message_type == 'http.response.start':
            assert self._initial_message is None, 'Received multiple response start messages.'
            self._initial_message = message
            headers = Headers(raw=self._initial_message['headers'])
            self._content_encoding_set = 'content-encoding' in headers
        elif message_type == 'http.response.body' and self._content_encoding_set:
            # Don't support double/multi compression
            if not self._is_response_started:
                self._is_response_started = True
                await self._send(self._initial_message)
            await self._send(message)
        elif message_type == 'http.response.body' and not self._is_response_started:
            # First response body
            self._is_response_started = True
            body = message.get('body', b"")
            more_body = message.get('more_body', False)
            if len(body) < self._minimum_size and not more_body:
                # Don't apply GZip to small outgoing responses.
                pass
            elif not more_body:
                # Standard GZip response.
                self._compress_file.write(body)
                self._compress_file.close()
                body = self._compress_buffer.getvalue()

                headers = MutableHeaders(raw=self._initial_message['headers'])
                headers['Content-Encoding'] = self._content_name
                headers['Content-Length'] = str(len(body))
                headers.add_vary_header("Accept-Encoding")
                message['body'] = body
            else:
                # Initial body in streaming GZip response.
                headers = MutableHeaders(raw=self._initial_message['headers'])
                headers['Content-Encoding'] = self._content_name
                headers.add_vary_header('Accept-Encoding')
                del headers['Content-Length']

                self._compress_file.write(body)
                message['body'] = self._compress_buffer.getvalue()
                self._compress_buffer.seek(0)
                self._compress_buffer.truncate()

            await self._send(self._initial_message)
            await self._send(message)

        elif message_type == 'http.response.body':  # When more_body
            # Remaining body in streaming GZip response.
            body = message.get('body', b"")
            more_body = message.get('more_body', False)

            self._compress_file.write(body)
            if not more_body:
                self._compress_file.close()

            message['body'] = self._compress_buffer.getvalue()
            self._compress_buffer.seek(0)
            self._compress_buffer.truncate()

            await self._send(message)

