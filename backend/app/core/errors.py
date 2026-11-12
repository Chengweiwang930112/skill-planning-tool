from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"


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


def _problem(
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
    return _problem(exc.status_code, detail=exc.detail, headers=exc.headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        InvalidParam(name=".".join(str(part) for part in e["loc"][1:]) or "body", reason=e["msg"])
        for e in exc.errors()
    ]
    return _problem(
        status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid request parameters", errors=errors
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validation_error)
