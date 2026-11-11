from fastapi import status
from httpx import ASGITransport, AsyncClient

from app import __version__
from app.core.config import Settings
from app.main import create_app


async def test_healthz_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "version": __version__}


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["info"]["title"] == "Staff & Skill Planning Tool"


async def test_openapi_schema_is_hidden_in_production() -> None:
    app = create_app(Settings(environment="production"))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.get("/openapi.json")).status_code == status.HTTP_404_NOT_FOUND
        assert (await client.get("/healthz")).status_code == status.HTTP_200_OK
