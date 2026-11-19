from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models import ProficiencyLevel, Skill
from app.schemas import EmployeeQuery, SkillLevelWrite
from app.services import employees_service
from tests.component.conftest import MockService
from tests.factories import make_employee

URL = "/api/v1/employees"


def anna(*assigned: tuple[Skill, ProficiencyLevel]) -> Any:
    return make_employee(
        dict(assigned),
        id=1,
        employee_number="E-1001",
        first_name="Anna",
        last_name="Schmidt",
        email="anna.schmidt@example.com",
        department="Digital Industries",
    )


def test_lists_the_employees_the_service_found(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    go = Skill(id=7, name="Go")
    list_employees = mock_service(
        employees_service,
        "list_employees",
        return_value=([anna((go, ProficiencyLevel.EXPERT))], 41),
    )

    # When
    response = client.get(URL, params={"page": 3, "page_size": 20})

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "employee_number": "E-1001",
                "first_name": "Anna",
                "last_name": "Schmidt",
                "email": "anna.schmidt@example.com",
                "department": "Digital Industries",
                "job_title": None,
                "location": None,
                "hire_date": None,
                "skills": [{"skill": {"id": 7, "name": "Go"}, "level": "expert"}],
            }
        ],
        "total": 41,
        "page": 3,
        "page_size": 20,
    }
    list_employees.assert_called_once_with(session, EmployeeQuery(page=3, page_size=20))


def test_passes_search_filters_and_sorting_to_the_service(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    list_employees = mock_service(employees_service, "list_employees", return_value=([], 0))

    # When
    client.get(
        URL,
        params={
            "q": "schmidt",
            "department": ["Mobility", "Healthineers"],
            "location": "Munich",
            "skill": ["kubernetes:advanced", "python"],
            "sort": "-hire_date",
        },
    )

    # Then
    list_employees.assert_called_once_with(
        session,
        EmployeeQuery(
            q="schmidt",
            department=["Mobility", "Healthineers"],
            location=["Munich"],
            skill=["kubernetes:advanced", "python"],
            sort="-hire_date",
        ),
    )


@pytest.mark.parametrize(
    ("params", "name", "reason"),
    [
        ({"page_size": 101}, "page_size", "less than or equal to 100"),
        ({"page": 0}, "page", "greater than or equal to 1"),
        ({"sort": "salary"}, "sort", "Input should be"),
        ({"skill": ["kubernetes:advnced"]}, "skill.0", "must be one of beginner"),
        ({"skill": ["go", ":expert"]}, "skill.1", "needs a skill name"),
        ({"skill": [f"skill{n}" for n in range(11)]}, "skill", "at most 10 items"),
    ],
    ids=["page_size", "page", "sort", "unknown-level", "missing-name", "too-many-skills"],
)
def test_rejects_invalid_parameters_as_problem_details_without_searching(
    client: TestClient, mock_service: MockService, params: dict[str, Any], name: str, reason: str
) -> None:
    # Given
    list_employees = mock_service(employees_service, "list_employees")

    # When
    response = client.get(URL, params=params)

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert (body["status"], body["detail"]) == (422, "Invalid request parameters")
    [error] = body["errors"]
    assert error["name"] == name
    assert reason in error["reason"]
    list_employees.assert_not_called()


def test_gets_one_employee(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    get_employee = mock_service(employees_service, "get_employee", return_value=anna())

    # When
    response = client.get(f"{URL}/1")

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["last_name"] == "Schmidt"
    assert response.headers["etag"] == employees_service.etag(anna())
    get_employee.assert_called_once_with(session, 1)


def test_an_unknown_employee_is_a_404_problem(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(employees_service, "get_employee", return_value=None)

    # When
    response = client.get(f"{URL}/999999")

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Employee 999999 does not exist",
    }


def put_skills(client: TestClient, skills: list[dict[str, object]], if_match: str = "") -> Any:
    headers = {"If-Match": if_match} if if_match else {}
    return client.put(f"{URL}/1/skills", json={"skills": skills}, headers=headers)


def test_replaces_the_skills_of_the_loaded_version_and_answers_with_the_new_one(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    stored = anna((Skill(id=7, name="Go"), ProficiencyLevel.ADVANCED))
    replace_skills = mock_service(employees_service, "replace_skills", return_value=stored)

    # When
    response = put_skills(client, [{"skill_id": 7, "level": "advanced"}], if_match='"v1"')

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["skills"] == [{"skill": {"id": 7, "name": "Go"}, "level": "advanced"}]
    assert response.headers["etag"] == employees_service.etag(stored)
    replace_skills.assert_called_once_with(
        session, 1, [SkillLevelWrite(skill_id=7, level=ProficiencyLevel.ADVANCED)], '"v1"'
    )


def test_replacing_skills_without_a_version_is_a_428(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    replace_skills = mock_service(employees_service, "replace_skills")

    # When
    response = put_skills(client, [])

    # Then
    assert response.status_code == status.HTTP_428_PRECONDITION_REQUIRED
    assert "If-Match" in response.json()["detail"]
    replace_skills.assert_not_called()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (employees_service.EmployeeNotFoundError(1), status.HTTP_404_NOT_FOUND),
        (employees_service.EmployeeChangedError(), status.HTTP_412_PRECONDITION_FAILED),
        (employees_service.UnknownSkillsError([999999]), status.HTTP_422_UNPROCESSABLE_CONTENT),
    ],
    ids=["unknown-employee", "changed-since-loaded", "unknown-skill"],
)
def test_a_refused_replacement_is_a_problem_with_the_reason(
    client: TestClient, mock_service: MockService, error: Exception, code: int
) -> None:
    # Given
    mock_service(employees_service, "replace_skills", side_effect=error)

    # When
    response = put_skills(client, [{"skill_id": 999999, "level": "expert"}], if_match='"v1"')

    # Then
    assert response.status_code == code
    assert response.json()["detail"] == str(error)
    assert "etag" not in response.headers


@pytest.mark.parametrize(
    ("skills", "reason"),
    [
        (
            [{"skill_id": 1, "level": "expert"}, {"skill_id": 1, "level": "beginner"}],
            "more than once",
        ),
        ([{"skill_id": 1, "level": "guru"}], "must be one of"),
        ([{"name": "Go", "level": "expert"}], "Field required"),
    ],
    ids=["duplicate", "level", "name-instead-of-id"],
)
def test_rejects_an_invalid_skill_list_without_changing_anything(
    client: TestClient, mock_service: MockService, skills: list[dict[str, object]], reason: str
) -> None:
    # Given
    replace_skills = mock_service(employees_service, "replace_skills")

    # When
    response = put_skills(client, skills, if_match='"v1"')

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert reason in response.json()["errors"][0]["reason"]
    replace_skills.assert_not_called()


def test_deletes_an_employee(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    delete_employee = mock_service(employees_service, "delete_employee")

    # When
    response = client.delete(f"{URL}/1")

    # Then
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""
    delete_employee.assert_called_once_with(session, 1)


def test_deleting_an_unknown_employee_is_a_404(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(
        employees_service,
        "delete_employee",
        side_effect=employees_service.EmployeeNotFoundError(999999),
    )

    # When
    response = client.delete(f"{URL}/999999")

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Employee 999999 does not exist"
