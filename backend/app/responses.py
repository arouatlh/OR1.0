from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    message: str
    status_code: int


class SuccessResponse(BaseModel):
    message: str = "Success"
    data: Any = None
    status_code: int


class Pagination(BaseModel):  # kept for future use, not emitted in v1
    offset: int
    limit: int
    total: int


class PaginatedResponse(BaseModel):
    message: str = "Success"
    data: Any = None
    status_code: int
    count: int  # number of items in this page


def write_error_response(status_code: int, message: str) -> JSONResponse:
    body = ErrorResponse(message=message, status_code=status_code)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def write_success_response(status_code: int, data: Any = None) -> JSONResponse:
    body = SuccessResponse(data=jsonable_encoder(data), status_code=status_code)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def write_paginated_response(status_code: int, data: Any, count: int) -> JSONResponse:
    body = PaginatedResponse(data=jsonable_encoder(data), status_code=status_code, count=count)
    return JSONResponse(status_code=status_code, content=body.model_dump())


MAX_LIMIT = 500


def get_pagination_params(request: Request) -> tuple[int, int]:
    """Returns (offset, limit). Lenient like the Go version: bad values fall back to defaults."""
    limit, offset = 20, 0
    try:
        lim = int(request.query_params.get("limit", ""))
        if lim > 0:
            limit = min(lim, MAX_LIMIT)
    except ValueError:
        pass
    try:
        o = int(request.query_params.get("offset", ""))
        if o > 0:
            offset = o
    except ValueError:
        pass
    return offset, limit
