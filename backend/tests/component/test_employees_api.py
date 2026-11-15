from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models import ProficiencyLevel, Skill
from app.schemas import EmployeeQuery, SkillLevelWrite
from app.services import employees_service, skills_service
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
            "department": "Mobility",
            "skill": ["kubernetes:advanced", "python"],
            "sort": "-hire_date",
        },
    )

    # Then
    list_employees.assert_called_once_with(
        session,
        EmployeeQuery(
            q="schmidt",
            department="Mobility",
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


def test_replaces_the_skills_and_answers_with_the_stored_ones(
    client: TestClient, session: MagicMock, mock_service: MockService
) -> None:
    # Given
    go = Skill(id=7, name="Go")
    mock_service(
        employees_service,
        "get_employee",
        side_effect=[anna(), anna((go, ProficiencyLevel.ADVANCED))],
    )
    replace_skills = mock_service(employees_service, "replace_skills")

    # When
    response = client.put(
        f"{URL}/1/skills", json={"skills": [{"skill_id": 7, "level": "advanced"}]}
    )

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["skills"] == [{"skill": {"id": 7, "name": "Go"}, "level": "advanced"}]
    replace_skills.assert_called_once_with(
        session, 1, [SkillLevelWrite(skill_id=7, level=ProficiencyLevel.ADVANCED)]
    )


def test_replacing_skills_of_an_unknown_employee_is_a_404(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(employees_service, "get_employee", return_value=None)
    replace_skills = mock_service(employees_service, "replace_skills")

    # When
    response = client.put(f"{URL}/999999/skills", json={"skills": []})

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Employee 999999 does not exist"
    replace_skills.assert_not_called()


def test_skills_missing_from_the_catalogue_are_a_422(
    client: TestClient, mock_service: MockService
) -> None:
    # Given
    mock_service(employees_service, "get_employee", return_value=anna())
    mock_service(
        employees_service,
        "replace_skills",
        side_effect=employees_service.UnknownSkillsError([999999]),
    )

    # When
    response = client.put(
        f"{URL}/1/skills", json={"skills": [{"skill_id": 999999, "level": "expert"}]}
    )

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Unknown skills: 999999"


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
    get_employee = mock_service(employees_service, "get_employee")
    replace_skills = mock_service(employees_service, "replace_skills")

    # When
    response = client.put(f"{URL}/1/skills", json={"skills": skills})

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert reason in response.json()["errors"][0]["reason"]
    get_employee.assert_not_called()
    replace_skills.assert_not_called()


@pytest.mark.parametrize(("created", "code"), [(True, 201), (False, 200)], ids=["new", "changed"])
def test_assigning_a_skill_tells_new_from_changed(
    client: TestClient, session: MagicMock, mock_service: MockService, created: bool, code: int
) -> None:
    # Given
    mock_service(employees_service, "get_employee", return_value=anna())
    mock_service(skills_service, "get_skill", return_value=Skill(id=7, name="Go"))
    assign_skill = mock_service(employees_service, "assign_skill", return_value=created)

    # When
    response = client.put(f"{URL}/1/skills/7", json={"level": "expert"})

    # Then
    assert response.status_code == code
    assert response.json() == {"skill": {"id": 7, "name": "Go"}, "level": "expert"}
    assign_skill.assert_called_once_with(session, 1, 7, ProficiencyLevel.EXPERT)


def test_removes_a_skill(client: TestClient, session: MagicMock, mock_service: MockService) -> None:
    # Given
    mock_service(employees_service, "get_employee", return_value=anna())
    mock_service(skills_service, "get_skill", return_value=Skill(id=7, name="Go"))
    remove_skill = mock_service(employees_service, "remove_skill")

    # When
    response = client.delete(f"{URL}/1/skills/7")

    # Then
    assert response.status_code == status.HTTP_204_NO_CONTENT
    remove_skill.assert_called_once_with(session, 1, 7)


@pytest.mark.parametrize("method", ["put", "delete"])
@pytest.mark.parametrize(
    ("employee_found", "skill_found", "detail"),
    [(False, True, "Employee 1 does not exist"), (True, False, "Skill 7 does not exist")],
    ids=["unknown-employee", "unknown-skill"],
)
def test_an_assignment_of_an_unknown_employee_or_skill_is_a_404(
    client: TestClient,
    mock_service: MockService,
    method: str,
    employee_found: bool,
    skill_found: bool,
    detail: str,
) -> None:
    # Given
    mock_service(employees_service, "get_employee", return_value=anna() if employee_found else None)
    mock_service(
        skills_service, "get_skill", return_value=Skill(id=7, name="Go") if skill_found else None
    )
    assign_skill = mock_service(employees_service, "assign_skill")
    remove_skill = mock_service(employees_service, "remove_skill")
    body = {"level": "advanced"} if method == "put" else None

    # When
    response = client.request(method, f"{URL}/1/skills/7", json=body)

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == detail
    assign_skill.assert_not_called()
    remove_skill.assert_not_called()


def test_openapi_documents_problem_details_instead_of_the_default_error(
    client: TestClient,
) -> None:
    # When
    schema = client.get("/openapi.json").json()

    # Then
    list_operation = schema["paths"][URL]["get"]
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert list_operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ProblemDetail"
    }
    assert {p["name"] for p in list_operation["parameters"]} == {
        "q", "department", "skill", "sort", "page", "page_size"
    }  # fmt: skip
