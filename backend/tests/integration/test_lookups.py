from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Department, Employee, Location
from tests.factories import make_employee, persist

HEADER = "employee_number,first_name,last_name,email,department,location"


def upload(client: TestClient, rows: str) -> Any:
    content = f"{HEADER}\n{rows}".encode()
    return client.post("/api/v1/imports", files={"file": ("team.csv", content)}).json()


def names(client: TestClient, url: str, **params: Any) -> list[str]:
    return [item["name"] for item in client.get(url, params=params).json()["items"]]


def test_an_import_adds_the_departments_and_locations_it_has_not_seen(
    client: TestClient,
) -> None:
    # When
    upload(
        client,
        "E-1,Anna,Schmidt,a@example.com,Mobility,Munich\n"
        "E-2,Jonas,Fischer,j@example.com,mobility ,Zug\n"
        "E-3,Mia,Weber,m@example.com,Digital Industries,\n",
    )

    # Then
    assert names(client, "/api/v1/departments") == ["Digital Industries", "Mobility"]
    assert names(client, "/api/v1/locations") == ["Munich", "Zug"]


def test_another_spelling_in_a_later_import_is_the_same_department(
    client: TestClient, session: Session
) -> None:
    # Given
    upload(client, "E-1,Anna,Schmidt,a@example.com,Smart Infrastructure,Zug\n")

    # When
    record = upload(client, "E-2,Jonas,Fischer,j@example.com,SMART  infrastructure,Zug\n")

    # Then
    assert record["rows_created"] == 1
    assert names(client, "/api/v1/departments") == ["Smart Infrastructure"]
    departments = session.scalars(select(Employee.department_id)).all()
    assert len(set(departments)) == 1


def test_finds_departments_by_part_of_their_name(client: TestClient, session: Session) -> None:
    # Given
    persist(
        session,
        *(Department(name=name) for name in ["Digital Industries", "Mobility", "Smart Infra"]),
    )

    # When
    found = names(client, "/api/v1/departments", q="indus")

    # Then
    assert found == ["Digital Industries"]


def test_filters_employees_by_any_of_several_departments_and_a_location(
    client: TestClient, session: Session
) -> None:
    # Given
    mobility, health = Department(name="Mobility"), Department(name="Healthineers")
    munich = Location(name="Munich")
    persist(
        session,
        make_employee(last_name="A", department=mobility, location=munich),
        make_employee(last_name="B", department=health, location="Erlangen"),
        make_employee(last_name="C", department=mobility, location="Berlin"),
        make_employee(last_name="D", department="Digital Industries", location=munich),
    )

    # When
    either = client.get(
        "/api/v1/employees", params={"department": ["mobility", "Healthineers"]}
    ).json()
    both = client.get(
        "/api/v1/employees",
        params={"department": ["mobility", "healthineers"], "location": "munich"},
    ).json()

    # Then
    assert [e["last_name"] for e in either["items"]] == ["A", "B", "C"]
    assert [(e["last_name"], e["department"], e["location"]) for e in both["items"]] == [
        ("A", "Mobility", "Munich")
    ]
