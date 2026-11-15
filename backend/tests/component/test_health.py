from unittest.mock import MagicMock

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import __version__
from app.core.config import Settings
from app.main import create_app
from tests.component.conftest import UNUSED_DATABASE


def test_healthz_reports_ok_without_asking_the_database(
    client: TestClient, session: MagicMock
) -> None:
    # When
    response = client.get("/healthz")

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "version": __version__}
    session.execute.assert_not_called()


def test_readyz_reports_ok_when_the_database_answers(
    client: TestClient, session: MagicMock
) -> None:
    # When
    response = client.get("/readyz")

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
    session.execute.assert_called_once()


def test_readyz_reports_unavailable_when_the_database_does_not_answer(
    client: TestClient, session: MagicMock
) -> None:
    # Given
    session.execute.side_effect = OperationalError("SELECT 1", {}, OSError("refused"))

    # When
    response = client.get("/readyz")

    # Then
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable"}


def test_openapi_schema_is_served(client: TestClient) -> None:
    # When
    response = client.get("/openapi.json")

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["info"]["title"] == "Staff & Skill Planning Tool"


def test_openapi_schema_is_hidden_in_production() -> None:
    # Given
    app = create_app(Settings(environment="production", database_url=UNUSED_DATABASE))

    # When
    with TestClient(app) as client:
        schema = client.get("/openapi.json")
        health = client.get("/healthz")

    # Then
    assert schema.status_code == status.HTTP_404_NOT_FOUND
    assert health.status_code == status.HTTP_200_OK
