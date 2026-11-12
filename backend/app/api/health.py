from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.database import get_session

router = APIRouter(tags=["infrastructure"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]


# Liveness must not depend on the database: a probe that fails during a brief
# database outage makes the orchestrator restart healthy tasks.
@router.get("/healthz", summary="Liveness probe")
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/readyz",
    summary="Readiness probe",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readyz(
    session: Annotated[AsyncSession, Depends(get_session)], response: Response
) -> ReadinessResponse:
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable")
    return ReadinessResponse(status="ok")
