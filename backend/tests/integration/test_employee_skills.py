from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import EmployeeSkill, ProficiencyLevel, Skill
from tests.factories import make_employee, persist

BEGINNER, INTERMEDIATE, ADVANCED, EXPERT = ProficiencyLevel


def skills_url(employee_id: int) -> str:
    return f"/api/v1/employees/{employee_id}/skills"


def version(client: TestClient, employee_id: int) -> str:
    etag: str = client.get(f"/api/v1/employees/{employee_id}").headers["etag"]
    return etag


def put_skills(client: TestClient, employee_id: int, skills: list[dict[str, Any]]) -> Any:
    """As the frontend saves: the skills of the version it loaded."""
    headers = {"If-Match": version(client, employee_id)}
    return client.put(skills_url(employee_id), json={"skills": skills}, headers=headers)


def stored_skills(client: TestClient, employee_id: int) -> list[tuple[str, str]]:
    body = client.get(f"/api/v1/employees/{employee_id}").json()
    return [(s["skill"]["name"], s["level"]) for s in body["skills"]]


def count(session: Session, model: type[object]) -> int | None:
    return session.scalar(select(func.count()).select_from(model))


def test_replaces_all_skills_in_one_request(client: TestClient, session: Session) -> None:
    # Given
    go, python, k8s = Skill(name="Go"), Skill(name="Python"), Skill(name="Kubernetes")
    employee = make_employee({go: BEGINNER, python: EXPERT})
    persist(session, employee, k8s)
    skills = [
        {"skill_id": python.id, "level": "advanced"},
        {"skill_id": k8s.id, "level": "expert"},
    ]

    # When
    response = put_skills(client, employee.id, skills)

    # Then
    assert [(s["skill"]["name"], s["level"]) for s in response.json()["skills"]] == [
        ("Kubernetes", "expert"),
        ("Python", "advanced"),
    ]
    assert stored_skills(client, employee.id) == [("Kubernetes", "expert"), ("Python", "advanced")]


def test_replacing_leaves_unchanged_assignments_untouched(
    client: TestClient, session: Session
) -> None:
    # Given
    go, python = Skill(name="Go"), Skill(name="Python")
    employee = make_employee({go: BEGINNER, python: EXPERT})
    persist(session, employee)
    # now() is fixed within the test's transaction, so updated_at cannot show an update;
    # the row's physical location (ctid) changes with every update.
    row_version = text("SELECT ctid::text FROM employee_skill WHERE skill_id = :id")
    go_before = session.scalar(row_version, {"id": go.id})
    python_before = session.scalar(row_version, {"id": python.id})
    skills = [
        {"skill_id": go.id, "level": "advanced"},
        {"skill_id": python.id, "level": "expert"},
    ]

    # When
    put_skills(client, employee.id, skills)

    # Then
    assert session.scalar(row_version, {"id": go.id}) != go_before
    assert session.scalar(row_version, {"id": python.id}) == python_before


def test_replacing_with_nothing_removes_every_skill(client: TestClient, session: Session) -> None:
    # Given
    employee = make_employee({Skill(name="Go"): BEGINNER})
    persist(session, employee)

    # When
    response = put_skills(client, employee.id, [])

    # Then
    assert response.json()["skills"] == []
    assert count(session, EmployeeSkill) == 0


def test_only_assigns_skills_from_the_catalogue_and_then_changes_nothing(
    client: TestClient, session: Session
) -> None:
    # Given
    go = Skill(name="Go")
    employee = make_employee({go: BEGINNER})
    persist(session, employee)
    skills = [
        {"skill_id": go.id, "level": "expert"},
        {"skill_id": 999999, "level": "expert"},
    ]

    # When
    response = put_skills(client, employee.id, skills)

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Unknown skills: 999999"
    assert stored_skills(client, employee.id) == [("Go", "beginner")]
    assert count(session, Skill) == 1


def test_refuses_to_overwrite_skills_someone_saved_since_they_were_loaded(
    client: TestClient, session: Session
) -> None:
    # Given
    go, rust = Skill(name="Go"), Skill(name="Rust")
    employee = make_employee()
    persist(session, employee, go, rust)
    loaded = version(client, employee.id)
    first = client.put(
        skills_url(employee.id),
        json={"skills": [{"skill_id": go.id, "level": "expert"}]},
        headers={"If-Match": loaded},
    )

    # When
    second = client.put(
        skills_url(employee.id),
        json={"skills": [{"skill_id": rust.id, "level": "beginner"}]},
        headers={"If-Match": loaded},
    )

    # Then
    assert first.status_code == status.HTTP_200_OK
    assert first.headers["etag"] == version(client, employee.id) != loaded
    assert second.status_code == status.HTTP_412_PRECONDITION_FAILED
    assert stored_skills(client, employee.id) == [("Go", "expert")]


def test_changing_skills_needs_the_version_they_were_loaded_at(
    client: TestClient, session: Session
) -> None:
    # Given
    employee = make_employee({Skill(name="Go"): BEGINNER})
    persist(session, employee)

    # When
    response = client.put(skills_url(employee.id), json={"skills": []})

    # Then
    assert response.status_code == status.HTTP_428_PRECONDITION_REQUIRED
    assert stored_skills(client, employee.id) == [("Go", "beginner")]


def test_replacing_the_skills_of_an_unknown_employee_is_a_404(client: TestClient) -> None:
    # When
    response = client.put(skills_url(999999), json={"skills": []}, headers={"If-Match": '"v"'})

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Employee 999999 does not exist"


def test_deleting_an_employee_removes_their_skills_but_not_the_catalogues(
    client: TestClient, session: Session
) -> None:
    # Given
    go = Skill(name="Go")
    anna, jonas = make_employee({go: EXPERT}), make_employee({go: BEGINNER})
    persist(session, anna, jonas)

    # When
    deleted = client.delete(f"/api/v1/employees/{anna.id}")
    again = client.delete(f"/api/v1/employees/{anna.id}")

    # Then
    assert (deleted.status_code, again.status_code) == (204, 404)
    assert client.get(f"/api/v1/employees/{anna.id}").status_code == status.HTTP_404_NOT_FOUND
    assert count(session, EmployeeSkill) == 1
    [catalogue_go] = client.get("/api/v1/skills").json()["items"]
    assert (catalogue_go["name"], catalogue_go["employee_count"]) == ("Go", 1)
