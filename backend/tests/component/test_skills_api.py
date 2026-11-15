from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.imports import MAX_UPLOAD_BYTES
from app.models import Skill
from app.schemas import RowErrorRead, SkillImportResult, SkillQuery
from app.services import skills
from app.services.csv_parsing import CsvFileError
from tests.component.conftest import MockService

URL = "/api/v1/skills"
GO = Skill(id=7, name="Go")


def test_lists_the_catalogue_with_employee_counts(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    list_skills = mock_service(skills, "list_skills", return_value=([(GO, 12)], 1))

    # When
    response = client.get(URL, params={"q": "go", "page_size": 10})

    # Then
    assert response.json() == {
        "items": [{"id": 7, "name": "Go", "employee_count": 12}],
        "total": 1,
        "page": 1,
        "page_size": 10,
    }
    list_skills.assert_called_once_with(session, SkillQuery(q="go", page_size=10))


def test_adds_a_skill_with_normalised_whitespace(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    create_skill = mock_service(
        skills, "create_skill", return_value=Skill(id=8, name="Apache Kafka")
    )

    # When
    response = client.post(URL, json={"name": "  Apache   Kafka "})

    # Then
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {"id": 8, "name": "Apache Kafka"}
    create_skill.assert_called_once_with(session, "Apache Kafka")


@pytest.mark.parametrize("name", ["", "   ", "x" * 101], ids=["empty", "blank", "too-long"])
def test_rejects_invalid_skill_names_without_adding_anything(
    client: TestClient, mock_service: MockService, name: str
) -> None:
    # Given
    create_skill = mock_service(skills, "create_skill")

    # When
    response = client.post(URL, json={"name": name})

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert [error["name"] for error in response.json()["errors"]] == ["name"]
    create_skill.assert_not_called()


def test_a_duplicate_skill_is_a_409_naming_the_existing_one(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    existing = Skill(id=15, name="Node.js")
    mock_service(skills, "create_skill", side_effect=skills.DuplicateSkillError(existing))

    # When
    response = client.post(URL, json={"name": "nodejs"})

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The catalogue already has Node.js (skill 15)"


def test_renames_a_skill(client: TestClient, session: MagicMock, mock_service: MockService) -> None:
    # Given
    mock_service(skills, "get_skill", return_value=GO)
    rename_skill = mock_service(skills, "rename_skill", return_value=Skill(id=7, name="Golang"))

    # When
    response = client.patch(f"{URL}/7", json={"name": "Golang"})

    # Then
    assert response.json() == {"id": 7, "name": "Golang"}
    rename_skill.assert_called_once_with(session, GO, "Golang")


def test_renaming_into_another_skill_is_a_409(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(skills, "get_skill", return_value=Skill(id=8, name="Golang"))
    mock_service(skills, "rename_skill", side_effect=skills.DuplicateSkillError(GO))

    # When
    response = client.patch(f"{URL}/8", json={"name": "go"})

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The catalogue already has Go (skill 7)"


def test_deletes_a_skill(client: TestClient, session: MagicMock, mock_service: MockService) -> None:
    # Given
    mock_service(skills, "get_skill", return_value=GO)
    delete_skill = mock_service(skills, "delete_skill")

    # When
    response = client.delete(f"{URL}/7")

    # Then
    assert response.status_code == status.HTTP_204_NO_CONTENT
    delete_skill.assert_called_once_with(session, GO)


def test_deleting_a_skill_someone_has_is_a_409(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(skills, "get_skill", return_value=GO)
    mock_service(skills, "delete_skill", side_effect=skills.SkillInUseError(3))

    # When
    response = client.delete(f"{URL}/7")

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The skill is assigned to 3 employees"


@pytest.mark.parametrize(
    ("method", "body"), [("patch", {"name": "Go"}), ("delete", None)], ids=["rename", "delete"]
)
def test_an_unknown_skill_is_a_404(
    client: TestClient, mock_service: MockService, method: str, body: dict[str, str] | None
) -> None:
    # Given
    mock_service(skills, "get_skill", return_value=None)

    # When
    response = client.request(method, f"{URL}/999999", json=body)

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Skill 999999 does not exist"


def test_imports_a_file_of_skills(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    result = SkillImportResult(
        rows_created=2,
        rows_existing=1,
        row_errors=[RowErrorRead(row=4, field="name", message="too long")],
    )
    import_skills = mock_service(skills, "import_skills", return_value=result)

    # When
    response = client.post(f"{URL}/import", files={"file": ("skills.csv", b"name\nGo\n")})

    # Then
    assert response.json() == result.model_dump()
    import_skills.assert_called_once_with(session, b"name\nGo\n")


def test_an_unusable_skill_file_is_a_422(client: TestClient, mock_service: MockService) -> None:
    # Given
    mock_service(skills, "import_skills", side_effect=CsvFileError("Missing required column: name"))

    # When
    response = client.post(f"{URL}/import", files={"file": ("skills.csv", b"skill\nGo\n")})

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Missing required column: name"


def test_rejects_a_skill_file_larger_than_the_limit(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    import_skills = mock_service(skills, "import_skills")
    content = b"x" * (MAX_UPLOAD_BYTES + 1)

    # When
    response = client.post(f"{URL}/import", files={"file": ("big.csv", content)})

    # Then
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    import_skills.assert_not_called()
