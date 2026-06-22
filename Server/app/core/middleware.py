from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class MaxBodySizeMiddleware:
    """Rejects requests whose declared Content-Length exceeds the limit
    before the body (e.g. a large multipart upload) is read at all.

    This is a fast-fail guard on top of -- not a replacement for -- the
    authoritative size check performed once the file is actually in hand,
    since a client can omit or lie about Content-Length.
    """

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > self.max_body_size:
                response = JSONResponse(
                    {"detail": "Request body exceeds the maximum allowed size"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
