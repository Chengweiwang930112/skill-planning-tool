from fastapi import status
from fastapi.testclient import TestClient

from app import __version__
from app.core.config import Settings
from app.main import create_app


def test_healthz_reports_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "version": __version__}


def test_readyz_reports_ok_when_the_database_answers(client: TestClient) -> None:
    response = client.get("/readyz")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_readyz_reports_unavailable_without_a_database() -> None:
    app = create_app(
        Settings(environment="test", database_url="postgresql+psycopg://x:x@127.0.0.1:1/none")
    )

    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable"}


def test_openapi_schema_is_served(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["info"]["title"] == "Staff & Skill Planning Tool"


def test_openapi_schema_is_hidden_in_production() -> None:
    app = create_app(Settings(environment="production"))

    with TestClient(app) as client:
        assert (client.get("/openapi.json")).status_code == status.HTTP_404_NOT_FOUND
        assert (client.get("/healthz")).status_code == status.HTTP_200_OK
