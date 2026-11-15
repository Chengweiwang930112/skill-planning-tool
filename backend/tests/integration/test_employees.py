from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ProficiencyLevel, Skill
from tests.factories import make_employee, persist

URL = "/api/v1/employees"
BEGINNER, INTERMEDIATE, ADVANCED, EXPERT = ProficiencyLevel


def get_page(client: TestClient, **params: Any) -> Any:
    response = client.get(URL, params=params)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


def last_names(client: TestClient, **params: Any) -> list[str]:
    return [employee["last_name"] for employee in get_page(client, **params)["items"]]


@pytest.fixture
def team(session: Session) -> None:
    k8s, python, go = Skill(name="Kubernetes"), Skill(name="Python"), Skill(name="Go")
    persist(
        session,
        make_employee({k8s: INTERMEDIATE, python: EXPERT}, last_name="Intermediate"),
        make_employee({k8s: ADVANCED, python: BEGINNER}, last_name="Advanced"),
        make_employee({k8s: EXPERT, go: ADVANCED}, last_name="Expert", department="Mobility"),
        make_employee({python: ADVANCED}, last_name="NoKubernetes"),
    )


def test_lists_nothing_when_there_are_no_employees(client: TestClient) -> None:
    # When
    page = get_page(client)

    # Then
    assert page == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_lists_employees_with_their_skills_strongest_first(
    client: TestClient, session: Session
) -> None:
    # Given
    python, k8s = Skill(name="Python"), Skill(name="Kubernetes")
    persist(
        session,
        make_employee(
            {python: BEGINNER, k8s: EXPERT},
            employee_number="E-1001",
            last_name="Schmidt",
            department="Digital Industries",
        ),
    )

    # When
    [employee] = get_page(client)["items"]

    # Then
    assert (employee["employee_number"], employee["department"]) == (
        "E-1001",
        "Digital Industries",
    )
    assert [(s["skill"]["name"], s["level"]) for s in employee["skills"]] == [
        ("Kubernetes", "expert"),
        ("Python", "beginner"),
    ]


def test_paginates_and_counts_all_matches(client: TestClient, session: Session) -> None:
    # Given
    persist(session, *(make_employee(last_name=name) for name in "ABCDE"))

    # When
    page = get_page(client, page=2, page_size=2)

    # Then
    assert [e["last_name"] for e in page["items"]] == ["C", "D"]
    assert (page["total"], page["page"], page["page_size"]) == (5, 2, 2)


def test_a_page_beyond_the_end_is_empty(client: TestClient, session: Session) -> None:
    # Given
    persist(session, make_employee())

    # When
    page = get_page(client, page=3)

    # Then
    assert (page["items"], page["total"]) == ([], 1)


@pytest.mark.parametrize(
    ("sort", "expected"),
    [("department", ["B", "A", "C"]), ("-department", ["A", "B", "C"])],
)
def test_sorts_with_missing_values_last(
    client: TestClient, session: Session, sort: str, expected: list[str]
) -> None:
    # Given
    persist(
        session,
        make_employee(last_name="A", department="Mobility"),
        make_employee(last_name="B", department="Healthineers"),
        make_employee(last_name="C", department=None),
    )

    # When
    result = last_names(client, sort=sort)

    # Then
    assert result == expected


@pytest.mark.parametrize(
    "q", ["anna schmidt", "SCHMIDT", "anna.schmidt@example", "e-1001"], ids=str
)
def test_searches_name_email_and_employee_number(
    client: TestClient, session: Session, q: str
) -> None:
    # Given
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

    # When
    result = last_names(client, q=q)

    # Then
    assert result == ["Schmidt"]


def test_search_treats_wildcards_literally(client: TestClient, session: Session) -> None:
    # Given
    persist(session, make_employee(last_name="Schmidt"))

    # When
    result = last_names(client, q="%")

    # Then
    assert result == []


def test_filters_by_department_ignoring_case(client: TestClient, session: Session) -> None:
    # Given
    persist(
        session,
        make_employee(last_name="A", department="Mobility"),
        make_employee(last_name="B", department="Healthineers"),
    )

    # When
    result = last_names(client, department="mobility")

    # Then
    assert result == ["A"]


@pytest.mark.usefixtures("team")
def test_finds_employees_with_a_skill_at_the_level_or_higher(client: TestClient) -> None:
    # When
    result = last_names(client, skill="kubernetes:advanced")

    # Then
    assert result == ["Advanced", "Expert"]


@pytest.mark.usefixtures("team")
@pytest.mark.parametrize("criterion", ["Kubernetes", "KUBERNETES:beginner", " kubernetes "])
def test_a_skill_without_a_level_matches_any_level(client: TestClient, criterion: str) -> None:
    # When
    result = last_names(client, skill=criterion)

    # Then
    assert result == ["Advanced", "Expert", "Intermediate"]


@pytest.mark.usefixtures("team")
def test_requires_every_skill_when_several_are_given(client: TestClient) -> None:
    # When
    some = last_names(client, skill=["kubernetes:advanced", "python"])
    none = last_names(client, skill=["kubernetes:advanced", "python:advanced"])

    # Then
    assert (some, none) == (["Advanced"], [])


@pytest.mark.usefixtures("team")
def test_combines_skills_with_the_other_filters_and_counts_matches(client: TestClient) -> None:
    # When
    page = get_page(client, skill="kubernetes:advanced", department="mobility", page_size=1)

    # Then
    assert ([e["last_name"] for e in page["items"]], page["total"]) == (["Expert"], 1)


@pytest.mark.usefixtures("team")
def test_returns_all_skills_of_a_match_not_only_the_searched_one(client: TestClient) -> None:
    # When
    [employee] = get_page(client, skill="go")["items"]

    # Then
    assert [(s["skill"]["name"], s["level"]) for s in employee["skills"]] == [
        ("Kubernetes", "expert"),
        ("Go", "advanced"),
    ]


@pytest.mark.usefixtures("team")
def test_an_unknown_skill_matches_nobody(client: TestClient) -> None:
    # When
    result = last_names(client, skill="cobol")

    # Then
    assert result == []


def test_matches_skill_names_like_the_catalogue_does(client: TestClient, session: Session) -> None:
    # Given
    persist(session, make_employee({Skill(name="Node.js"): EXPERT}, last_name="Node"))

    # When
    result = last_names(client, skill="nodejs:advanced")

    # Then
    assert result == ["Node"]


def test_gets_one_employee_with_their_skills(client: TestClient, session: Session) -> None:
    # Given
    employee = make_employee({Skill(name="Go"): ADVANCED}, last_name="Schmidt")
    persist(session, employee)

    # When
    response = client.get(f"{URL}/{employee.id}")

    # Then
    body = response.json()
    assert body["last_name"] == "Schmidt"
    assert [(s["skill"]["name"], s["level"]) for s in body["skills"]] == [("Go", "advanced")]


def test_an_unknown_employee_is_a_404_problem(client: TestClient) -> None:
    # When
    response = client.get(f"{URL}/999999")

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "Employee 999999 does not exist"
