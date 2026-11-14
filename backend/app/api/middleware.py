import json
import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.logging import get_logger

log = get_logger("api.middleware")


class ASGIMiddleware:
    """Pure ASGI middleware managing correlation ID, payload limit, API key check,
    and minimal structured request logging."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self.settings = get_settings()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        path = scope.get("path", "")
        method = scope.get("method", "")

        # 1. Request ID (extract or generate)
        raw_req_id = headers.get(b"x-request-id")
        req_id = raw_req_id.decode("latin1") if raw_req_id else str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(req_id=req_id)

        # 2. Body limit check (> 1 MiB)
        content_length_bytes = headers.get(b"content-length")
        if content_length_bytes:
            try:
                if int(content_length_bytes.decode()) > 1024 * 1024:
                    await self._send_error(send, 413, "Payload too large: maximum body size is 1 MiB", req_id)
                    return
            except ValueError:
                pass

        # 3. Optional API key check on mutating requests
        if self.settings.api_key and method in ("POST", "PATCH", "PUT", "DELETE"):
            client_key = headers.get(b"x-api-key", b"").decode("latin1")
            if client_key != self.settings.api_key:
                await self._send_error(send, 400, "Unauthorized: missing or invalid API key", req_id)
                return

        # 4. Wrap send to capture status code and add X-Request-ID header
        start_time = time.perf_counter()
        status_code = 200

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                res_headers = list(message.get("headers", []))
                res_headers.append((b"x-request-id", req_id.encode("latin1")))
                message["headers"] = res_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Skip logging health probes
            if path not in ("/healthz", "/readyz"):
                dur_ms = round((time.perf_counter() - start_time) * 1000, 1)
                log.info(
                    "http_request",
                    method=method,
                    path=path,
                    status=status_code,
                    dur_ms=dur_ms,
                    req_id=req_id,
                )

    async def _send_error(self, send: Send, status: int, message: str, req_id: str) -> None:
        body = json.dumps({"message": message, "status_code": status}).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin1")),
                (b"x-request-id", req_id.encode("latin1")),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
