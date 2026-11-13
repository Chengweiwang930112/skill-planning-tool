from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProficiencyLevel, Skill
from tests.factories import make_employee, persist

URL = "/api/v1/employees"


async def get_json(client: AsyncClient, url: str, **params: Any) -> Any:
    response = await client.get(url, params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def last_names(page: dict[str, Any]) -> list[str]:
    return [item["last_name"] for item in page["items"]]


async def test_lists_nothing_when_there_are_no_employees(client: AsyncClient) -> None:
    assert await get_json(client, URL) == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_lists_employees_with_skills_strongest_first(
    client: AsyncClient, session: AsyncSession
) -> None:
    python, k8s = Skill(name="Python"), Skill(name="Kubernetes")
    await persist(
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

    [employee] = (await get_json(client, URL))["items"]

    assert employee["employee_number"] == "E-1001"
    assert employee["department"] == "Digital Industries"
    assert [(s["skill"]["name"], s["level"]) for s in employee["skills"]] == [
        ("Kubernetes", "expert"),
        ("Python", "beginner"),
    ]


async def test_paginates_and_reports_the_total(client: AsyncClient, session: AsyncSession) -> None:
    await persist(session, *(make_employee(last_name=name) for name in "ABCDE"))

    page = await get_json(client, URL, page=2, page_size=2)

    assert last_names(page) == ["C", "D"]
    assert (page["total"], page["page"], page["page_size"]) == (5, 2, 2)


async def test_a_page_beyond_the_end_is_empty(client: AsyncClient, session: AsyncSession) -> None:
    await persist(session, make_employee())

    page = await get_json(client, URL, page=3)

    assert (page["items"], page["total"]) == ([], 1)


@pytest.mark.parametrize(
    ("sort", "expected"),
    [("department", ["B", "A", "C"]), ("-department", ["A", "B", "C"])],
)
async def test_sorts_with_missing_values_last(
    client: AsyncClient, session: AsyncSession, sort: str, expected: list[str]
) -> None:
    await persist(
        session,
        make_employee(last_name="A", department="Mobility"),
        make_employee(last_name="B", department="Healthineers"),
        make_employee(last_name="C", department=None),
    )

    assert last_names(await get_json(client, URL, sort=sort)) == expected


@pytest.mark.parametrize(
    "q", ["anna schmidt", "SCHMIDT", "anna.schmidt@example", "e-1001"], ids=str
)
async def test_searches_name_email_and_employee_number(
    client: AsyncClient, session: AsyncSession, q: str
) -> None:
    await persist(
        session,
        make_employee(
            employee_number="E-1001",
            first_name="Anna",
            last_name="Schmidt",
            email="anna.schmidt@example.com",
        ),
        make_employee(first_name="Jonas", last_name="Fischer", email="jonas@example.com"),
    )

    assert last_names(await get_json(client, URL, q=q)) == ["Schmidt"]


async def test_search_treats_wildcards_literally(
    client: AsyncClient, session: AsyncSession
) -> None:
    await persist(session, make_employee(last_name="Schmidt"))

    assert (await get_json(client, URL, q="%"))["total"] == 0


async def test_filters_by_department_ignoring_case(
    client: AsyncClient, session: AsyncSession
) -> None:
    await persist(
        session,
        make_employee(last_name="A", department="Mobility"),
        make_employee(last_name="B", department="Healthineers"),
    )

    assert last_names(await get_json(client, URL, department="mobility")) == ["A"]


@pytest.mark.parametrize(
    ("params", "invalid"),
    [({"page_size": 101}, "page_size"), ({"page": 0}, "page"), ({"sort": "salary"}, "sort")],
    ids=["page_size", "page", "sort"],
)
async def test_rejects_invalid_parameters_as_problem_details(
    client: AsyncClient, params: dict[str, Any], invalid: str
) -> None:
    response = await client.get(URL, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert (body["status"], body["detail"]) == (422, "Invalid request parameters")
    assert [error["name"] for error in body["errors"]] == [invalid]


async def test_gets_one_employee(client: AsyncClient, session: AsyncSession) -> None:
    employee = make_employee({Skill(name="Go"): ProficiencyLevel.ADVANCED}, last_name="Schmidt")
    await persist(session, employee)

    body = await get_json(client, f"{URL}/{employee.id}")

    assert body["last_name"] == "Schmidt"
    assert [(s["skill"]["name"], s["level"]) for s in body["skills"]] == [("Go", "advanced")]


async def test_unknown_employee_is_a_404_problem(client: AsyncClient) -> None:
    response = await client.get(f"{URL}/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Employee 999999 does not exist",
    }


async def test_openapi_documents_problem_details_instead_of_the_default_error(
    client: AsyncClient,
) -> None:
    schema = (await client.get("/openapi.json")).json()
    list_operation = schema["paths"][URL]["get"]

    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert list_operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ProblemDetail"
    }
    assert {p["name"] for p in list_operation["parameters"]} == {
        "q", "department", "skill", "sort", "page", "page_size"
    }  # fmt: skip
