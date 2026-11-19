from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models import Skill
from app.schemas import NameQuery
from app.services import skills_service
from tests.component.conftest import MockService

URL = "/api/v1/skills"
GO = Skill(id=7, name="Go")


def test_lists_the_catalogue_with_employee_counts(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    list_skills = mock_service(skills_service, "list_skills", return_value=([(GO, 12)], 1))

    # When
    response = client.get(URL, params={"q": "go", "page_size": 10})

    # Then
    assert response.json() == {
        "items": [{"id": 7, "name": "Go", "employee_count": 12}],
        "total": 1,
        "page": 1,
        "page_size": 10,
    }
    list_skills.assert_called_once_with(session, NameQuery(q="go", page_size=10))


def test_adds_a_skill_with_normalised_whitespace(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    create_skill = mock_service(
        skills_service, "create_skill", return_value=Skill(id=8, name="Apache Kafka")
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
    create_skill = mock_service(skills_service, "create_skill")

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
    mock_service(
        skills_service, "create_skill", side_effect=skills_service.DuplicateSkillError(existing)
    )

    # When
    response = client.post(URL, json={"name": "nodejs"})

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The catalogue already has Node.js (skill 15)"


def test_renames_a_skill(client: TestClient, session: MagicMock, mock_service: MockService) -> None:
    # Given
    mock_service(skills_service, "get_skill", return_value=GO)
    rename_skill = mock_service(
        skills_service, "rename_skill", return_value=Skill(id=7, name="Golang")
    )

    # When
    response = client.patch(f"{URL}/7", json={"name": "Golang"})

    # Then
    assert response.json() == {"id": 7, "name": "Golang"}
    rename_skill.assert_called_once_with(session, GO, "Golang")


def test_renaming_into_another_skill_is_a_409(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(skills_service, "get_skill", return_value=Skill(id=8, name="Golang"))
    mock_service(skills_service, "rename_skill", side_effect=skills_service.DuplicateSkillError(GO))

    # When
    response = client.patch(f"{URL}/8", json={"name": "go"})

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The catalogue already has Go (skill 7)"


def test_deletes_a_skill(client: TestClient, session: MagicMock, mock_service: MockService) -> None:
    # Given
    mock_service(skills_service, "get_skill", return_value=GO)
    delete_skill = mock_service(skills_service, "delete_skill")

    # When
    response = client.delete(f"{URL}/7")

    # Then
    assert response.status_code == status.HTTP_204_NO_CONTENT
    delete_skill.assert_called_once_with(session, GO)


def test_deleting_a_skill_someone_has_is_a_409(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(skills_service, "get_skill", return_value=GO)
    mock_service(skills_service, "delete_skill", side_effect=skills_service.SkillInUseError(3))

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
    mock_service(skills_service, "get_skill", return_value=None)

    # When
    response = client.request(method, f"{URL}/999999", json=body)

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Skill 999999 does not exist"
