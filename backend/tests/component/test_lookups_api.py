from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models import Department, Location
from app.schemas import NameQuery
from app.services import lookups_service
from tests.component.conftest import MockService


@pytest.mark.parametrize(
    ("url", "model", "entry"),
    [
        ("/api/v1/departments", Department, Department(id=3, name="Mobility")),
        ("/api/v1/locations", Location, Location(id=5, name="Munich")),
    ],
    ids=["departments", "locations"],
)
def test_lists_departments_and_locations_found_by_part_of_their_name(
    client: TestClient,
    session: MagicMock,
    mock_service: MockService,
    url: str,
    model: type[Department] | type[Location],
    entry: Department | Location,
) -> None:
    # Given
    list_names = mock_service(lookups_service, "list_names", return_value=([entry], 1))

    # When
    response = client.get(url, params={"q": "mu", "page_size": 10})

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "items": [{"id": entry.id, "name": entry.name}],
        "total": 1,
        "page": 1,
        "page_size": 10,
    }
    list_names.assert_called_once_with(session, model, NameQuery(q="mu", page_size=10))


def test_rejects_an_empty_search(client: TestClient, mock_service: MockService) -> None:
    # Given
    list_names = mock_service(lookups_service, "list_names")

    # When
    response = client.get("/api/v1/departments", params={"q": ""})

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    list_names.assert_not_called()
