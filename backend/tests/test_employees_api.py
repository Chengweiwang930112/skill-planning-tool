from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ProficiencyLevel, Skill
from tests.factories import make_employee, persist

URL = "/api/v1/employees"


def get_json(client: TestClient, url: str, **params: Any) -> Any:
    response = client.get(url, params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def last_names(page: dict[str, Any]) -> list[str]:
    return [item["last_name"] for item in page["items"]]


def test_lists_nothing_when_there_are_no_employees(client: TestClient) -> None:
    assert get_json(client, URL) == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_lists_employees_with_skills_strongest_first(client: TestClient, session: Session) -> None:
    python, k8s = Skill(name="Python"), Skill(name="Kubernetes")
    persist(
        session,
        make_employee(
            {python: ProficiencyLevel.BEGINNER, k8s: ProficiencyLevel.EXPERT},
            employee_number="E-1001",
            first_name="Anna",
            last_name="Schmidt",
            email="anna.schmidt@example.com",
            department="Digital Industries",
        ),
    )

    [employee] = (get_json(client, URL))["items"]

    assert employee["employee_number"] == "E-1001"
    assert employee["department"] == "Digital Industries"
    assert [(s["skill"]["name"], s["level"]) for s in employee["skills"]] == [
        ("Kubernetes", "expert"),
        ("Python", "beginner"),
    ]


def test_paginates_and_reports_the_total(client: TestClient, session: Session) -> None:
    persist(session, *(make_employee(last_name=name) for name in "ABCDE"))

    page = get_json(client, URL, page=2, page_size=2)

    assert last_names(page) == ["C", "D"]
    assert (page["total"], page["page"], page["page_size"]) == (5, 2, 2)


def test_a_page_beyond_the_end_is_empty(client: TestClient, session: Session) -> None:
    persist(session, make_employee())

    page = get_json(client, URL, page=3)

    assert (page["items"], page["total"]) == ([], 1)


@pytest.mark.parametrize(
    ("sort", "expected"),
    [("department", ["B", "A", "C"]), ("-department", ["A", "B", "C"])],
)
def test_sorts_with_missing_values_last(
    client: TestClient, session: Session, sort: str, expected: list[str]
) -> None:
    persist(
        session,
        make_employee(last_name="A", department="Mobility"),
        make_employee(last_name="B", department="Healthineers"),
        make_employee(last_name="C", department=None),
    )

    assert last_names(get_json(client, URL, sort=sort)) == expected


@pytest.mark.parametrize(
    "q", ["anna schmidt", "SCHMIDT", "anna.schmidt@example", "e-1001"], ids=str
)
def test_searches_name_email_and_employee_number(
    client: TestClient, session: Session, q: str
) -> None:
    persist(
        session,
        make_employee(
            employee_number="E-1001",
            first_name="Anna",
            last_name="Schmidt",
            email="anna.schmidt@example.com",
        ),
        make_employee(first_name="Jonas", last_name="Fischer", email="jonas@example.com"),
    )

    assert last_names(get_json(client, URL, q=q)) == ["Schmidt"]


def test_search_treats_wildcards_literally(client: TestClient, session: Session) -> None:
    persist(session, make_employee(last_name="Schmidt"))

    assert (get_json(client, URL, q="%"))["total"] == 0


def test_filters_by_department_ignoring_case(client: TestClient, session: Session) -> None:
    persist(
        session,
        make_employee(last_name="A", department="Mobility"),
        make_employee(last_name="B", department="Healthineers"),
    )

    assert last_names(get_json(client, URL, department="mobility")) == ["A"]


@pytest.mark.parametrize(
    ("params", "invalid"),
    [({"page_size": 101}, "page_size"), ({"page": 0}, "page"), ({"sort": "salary"}, "sort")],
    ids=["page_size", "page", "sort"],
)
def test_rejects_invalid_parameters_as_problem_details(
    client: TestClient, params: dict[str, Any], invalid: str
) -> None:
    response = client.get(URL, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert (body["status"], body["detail"]) == (422, "Invalid request parameters")
    assert [error["name"] for error in body["errors"]] == [invalid]


def test_gets_one_employee(client: TestClient, session: Session) -> None:
    employee = make_employee({Skill(name="Go"): ProficiencyLevel.ADVANCED}, last_name="Schmidt")
    persist(session, employee)

    body = get_json(client, f"{URL}/{employee.id}")

    assert body["last_name"] == "Schmidt"
    assert [(s["skill"]["name"], s["level"]) for s in body["skills"]] == [("Go", "advanced")]


def test_unknown_employee_is_a_404_problem(client: TestClient) -> None:
    response = client.get(f"{URL}/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Employee 999999 does not exist",
    }


def test_openapi_documents_problem_details_instead_of_the_default_error(
    client: TestClient,
) -> None:
    schema = (client.get("/openapi.json")).json()
    list_operation = schema["paths"][URL]["get"]

    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert list_operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ProblemDetail"
    }
    assert {p["name"] for p in list_operation["parameters"]} == {
        "q", "department", "skill", "sort", "page", "page_size"
    }  # fmt: skip
