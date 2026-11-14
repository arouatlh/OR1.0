import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import AppError, Kind
from app.logging import get_logger
from app.responses import write_error_response

log = get_logger("api.handlers")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        status_map = {
            Kind.BAD_REQUEST: 400,
            Kind.NOT_FOUND: 404,
            Kind.CONFLICT: 409,
            Kind.VALIDATION: 422,
            Kind.UNAVAILABLE: 503,
            Kind.INTERNAL: 500,
        }
        status_code = status_map.get(exc.kind, 500)

        if status_code >= 500:
            req_id = structlog.contextvars.get_contextvars().get("req_id", "-")
            log.error("request_failed", req_id=req_id, op=exc.op, exc_info=exc)

        return write_error_response(status_code, exc.public_message())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        issues: list[str] = []
        for err in exc.errors():
            loc_parts = [str(p) for p in err.get("loc", []) if p != "body"]
            field_name = ".".join(loc_parts)
            msg = err.get("msg", "invalid")
            # Strip Pydantic prefixes if present
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, "):]
            if field_name:
                issues.append(f"{field_name} {msg}")
            else:
                issues.append(msg)

        detail_str = "; ".join(issues) if issues else "invalid request"
        return write_error_response(422, f"validation failed: {detail_str}")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        msg = "Resource not found." if exc.status_code == 404 else ("Method not allowed." if exc.status_code == 405 else str(exc.detail))
        return write_error_response(exc.status_code, msg)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        req_id = structlog.contextvars.get_contextvars().get("req_id", "-")
        log.error("request_failed", req_id=req_id, op="unhandled_exception", exc_info=exc)
        return write_error_response(500, "Something went wrong.")
