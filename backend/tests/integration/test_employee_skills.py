from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import EmployeeSkill, ProficiencyLevel, Skill
from tests.factories import make_employee, persist

BEGINNER, INTERMEDIATE, ADVANCED, EXPERT = ProficiencyLevel


def assignment_url(employee_id: int, skill_id: int) -> str:
    return f"/api/v1/employees/{employee_id}/skills/{skill_id}"


def skills_url(employee_id: int) -> str:
    return f"/api/v1/employees/{employee_id}/skills"


def stored_skills(client: TestClient, employee_id: int) -> list[tuple[str, str]]:
    body = client.get(f"/api/v1/employees/{employee_id}").json()
    return [(s["skill"]["name"], s["level"]) for s in body["skills"]]


def count(session: Session, model: type[object]) -> int | None:
    return session.scalar(select(func.count()).select_from(model))


def test_assigns_a_skill_then_changes_its_level(client: TestClient, session: Session) -> None:
    # Given
    employee, skill = make_employee(), Skill(name="Kubernetes")
    persist(session, employee, skill)

    # When
    created = client.put(assignment_url(employee.id, skill.id), json={"level": "intermediate"})
    changed = client.put(assignment_url(employee.id, skill.id), json={"level": "expert"})

    # Then
    assert (created.status_code, changed.status_code) == (201, 200)
    assert created.json() == {
        "skill": {"id": skill.id, "name": "Kubernetes"},
        "level": "intermediate",
    }
    assert stored_skills(client, employee.id) == [("Kubernetes", "expert")]
    assert count(session, EmployeeSkill) == 1


def test_assigning_the_same_level_again_is_harmless(client: TestClient, session: Session) -> None:
    # Given
    skill = Skill(name="Go")
    employee = make_employee({skill: ADVANCED})
    persist(session, employee)

    # When
    response = client.put(assignment_url(employee.id, skill.id), json={"level": "advanced"})

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert stored_skills(client, employee.id) == [("Go", "advanced")]


def test_removes_a_skill_and_removing_it_again_is_harmless(
    client: TestClient, session: Session
) -> None:
    # Given
    go, python = Skill(name="Go"), Skill(name="Python")
    employee = make_employee({go: BEGINNER, python: EXPERT})
    persist(session, employee)

    # When
    first = client.delete(assignment_url(employee.id, go.id))
    second = client.delete(assignment_url(employee.id, go.id))

    # Then
    assert (first.status_code, second.status_code) == (204, 204)
    assert stored_skills(client, employee.id) == [("Python", "expert")]
    assert count(session, Skill) == 2


def test_an_assignment_of_an_unknown_employee_or_skill_is_a_404(
    client: TestClient, session: Session
) -> None:
    # Given
    employee, skill = make_employee(), Skill(name="Go")
    persist(session, employee, skill)

    # When
    unknown_employee = client.put(assignment_url(999999, skill.id), json={"level": "expert"})
    unknown_skill = client.delete(assignment_url(employee.id, 999999))

    # Then
    assert unknown_employee.json()["detail"] == "Employee 999999 does not exist"
    assert unknown_skill.json()["detail"] == "Skill 999999 does not exist"


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
    response = client.put(skills_url(employee.id), json={"skills": skills})

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
    client.put(skills_url(employee.id), json={"skills": skills})

    # Then
    assert session.scalar(row_version, {"id": go.id}) != go_before
    assert session.scalar(row_version, {"id": python.id}) == python_before


def test_replacing_with_nothing_removes_every_skill(client: TestClient, session: Session) -> None:
    # Given
    employee = make_employee({Skill(name="Go"): BEGINNER})
    persist(session, employee)

    # When
    response = client.put(skills_url(employee.id), json={"skills": []})

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
    response = client.put(skills_url(employee.id), json={"skills": skills})

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Unknown skills: 999999"
    assert stored_skills(client, employee.id) == [("Go", "beginner")]
    assert count(session, Skill) == 1
