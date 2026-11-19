import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"

logger = logging.getLogger(__name__)


class InvalidParam(BaseModel):
    name: str = Field(examples=["page_size"])
    reason: str = Field(examples=["Input should be less than or equal to 100"])


class ProblemDetail(BaseModel):
    """Error body following RFC 9457 (Problem Details for HTTP APIs)."""

    type: str = "about:blank"
    title: str = Field(examples=["Not Found"])
    status: int = Field(examples=[404])
    detail: str | None = Field(None, examples=["Employee 42 does not exist"])
    errors: list[InvalidParam] | None = None


def problem_response(description: str) -> dict[str, Any]:
    return {"model": ProblemDetail, "description": description}


def problem(
    status_code: int,
    detail: str | None = None,
    errors: list[InvalidParam] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ProblemDetail(
        title=HTTPStatus(status_code).phrase, status=status_code, detail=detail, errors=errors
    )
    return JSONResponse(
        body.model_dump(exclude_none=True),
        status_code=status_code,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


async def _http_exception(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    return problem(exc.status_code, detail=exc.detail, headers=exc.headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        InvalidParam(name=".".join(str(part) for part in e["loc"][1:]) or "body", reason=e["msg"])
        for e in exc.errors()
    ]
    return problem(
        status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid request parameters", errors=errors
    )


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Outside the request's middleware, so its id comes from the request, not the context.
    current = getattr(request.state, "request_id", None)
    logger.error("Unexpected error", exc_info=exc, extra={"request_id": current})
    return problem(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Something went wrong on our side; the request id identifies it in the logs",
        headers={"X-Request-ID": current} if current else None,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected_error)
