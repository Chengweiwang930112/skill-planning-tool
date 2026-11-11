from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["infrastructure"])


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: Literal["ok"]
    version: str


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> HealthResponse:

    return HealthResponse(status="ok", version=__version__)
