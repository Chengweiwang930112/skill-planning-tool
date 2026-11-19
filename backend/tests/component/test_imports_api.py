from unittest.mock import MagicMock

from fastapi import status
from fastapi.testclient import TestClient

from app.api.imports_api import MAX_UPLOAD_BYTES
from app.services import import_service
from tests.component.conftest import MockService
from tests.factories import make_import

URL = "/api/v1/imports"


def test_imports_an_uploaded_file_and_answers_with_its_record(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    import_employees = mock_service(import_service, "import_employees", return_value=make_import())

    # When
    response = client.post(URL, files={"file": ("team.csv", b"employee_number\n", "text/csv")})

    # Then
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {
        "id": 3,
        "filename": "employees.csv",
        "status": "partially_succeeded",
        "rows_total": 3,
        "rows_succeeded": 2,
        "rows_failed": 1,
        "rows_created": 1,
        "rows_updated": 1,
        "rows_unchanged": 0,
        "error": None,
        "created_at": "2026-11-13T09:30:00Z",
        "row_errors": [{"row": 3, "field": "first_name", "message": "is required"}],
    }
    import_employees.assert_called_once_with(session, "team.csv", b"employee_number\n")


def test_rejects_files_larger_than_the_limit_without_importing(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    import_employees = mock_service(import_service, "import_employees")
    content = b"x" * (MAX_UPLOAD_BYTES + 1)

    # When
    response = client.post(URL, files={"file": ("big.csv", content, "text/csv")})

    # Then
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.headers["content-type"] == "application/problem+json"
    import_employees.assert_not_called()


def test_requires_a_file(client: TestClient, mock_service: MockService) -> None:
    # Given
    import_employees = mock_service(import_service, "import_employees")

    # When
    response = client.post(URL)

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert [error["name"] for error in response.json()["errors"]] == ["file"]
    import_employees.assert_not_called()


def test_lists_imports_without_their_row_errors(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    list_imports = mock_service(
        import_service, "list_imports", return_value=([make_import(id=9)], 12)
    )

    # When
    response = client.get(URL, params={"page": 2, "page_size": 5})

    # Then
    body = response.json()
    assert (body["total"], body["page"], body["page_size"]) == (12, 2, 5)
    assert [item["id"] for item in body["items"]] == [9]
    assert "row_errors" not in body["items"][0]
    list_imports.assert_called_once_with(session, 2, 5)


def test_gets_one_import_with_its_row_errors(client: TestClient, mock_service: MockService) -> None:
    # Given
    mock_service(import_service, "get_import", return_value=make_import())

    # When
    response = client.get(f"{URL}/3")

    # Then
    assert response.json()["row_errors"] == [
        {"row": 3, "field": "first_name", "message": "is required"}
    ]


def test_an_unknown_import_is_a_404_problem(client: TestClient, mock_service: MockService) -> None:
    # Given
    mock_service(import_service, "get_import", return_value=None)

    # When
    response = client.get(f"{URL}/999999")

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Import 999999 does not exist"
