from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmployeeSkill, ProficiencyLevel, Skill
from tests.factories import make_employee, persist

SKILLS = "/api/v1/skills"


def assignment_url(employee_id: int, skill_id: int) -> str:
    return f"/api/v1/employees/{employee_id}/skills/{skill_id}"


async def employee_skills(client: AsyncClient, employee_id: int) -> list[tuple[str, str]]:
    body = (await client.get(f"/api/v1/employees/{employee_id}")).json()
    return [(s["skill"]["name"], s["level"]) for s in body["skills"]]


async def create_skill(client: AsyncClient, name: str) -> Any:
    response = await client.post(SKILLS, json={"name": name})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def test_assigns_a_skill_then_changes_its_level(
    client: AsyncClient, session: AsyncSession
) -> None:
    employee, skill = make_employee(), Skill(name="Kubernetes")
    await persist(session, employee, skill)
    url = assignment_url(employee.id, skill.id)

    created = await client.put(url, json={"level": "intermediate"})
    changed = await client.put(url, json={"level": "expert"})

    assert created.status_code == status.HTTP_201_CREATED
    assert created.json() == {
        "skill": {"id": skill.id, "name": "Kubernetes"},
        "level": "intermediate",
    }
    assert changed.status_code == status.HTTP_200_OK
    assert changed.json()["level"] == "expert"
    assert await employee_skills(client, employee.id) == [("Kubernetes", "expert")]
    assert await session.scalar(select(func.count()).select_from(EmployeeSkill)) == 1


async def test_assigning_the_same_level_again_is_harmless(
    client: AsyncClient, session: AsyncSession
) -> None:
    skill = Skill(name="Go")
    employee = make_employee({skill: ProficiencyLevel.ADVANCED})
    await persist(session, employee)

    response = await client.put(assignment_url(employee.id, skill.id), json={"level": "advanced"})

    assert response.status_code == status.HTTP_200_OK
    assert await employee_skills(client, employee.id) == [("Go", "advanced")]


@pytest.mark.parametrize("level", ["guru", 3, None], ids=["unknown", "number", "null"])
async def test_rejects_levels_that_are_not_on_the_scale(
    client: AsyncClient, session: AsyncSession, level: object
) -> None:
    employee, skill = make_employee(), Skill(name="Go")
    await persist(session, employee, skill)

    response = await client.put(assignment_url(employee.id, skill.id), json={"level": level})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    [error] = response.json()["errors"]
    assert error == {
        "name": "level",
        "reason": "Value error, must be one of beginner, intermediate, advanced, expert",
    }


async def test_removes_a_skill_and_removing_it_again_is_harmless(
    client: AsyncClient, session: AsyncSession
) -> None:
    go, python = Skill(name="Go"), Skill(name="Python")
    employee = make_employee({go: ProficiencyLevel.BEGINNER, python: ProficiencyLevel.EXPERT})
    await persist(session, employee)

    first = await client.delete(assignment_url(employee.id, go.id))
    second = await client.delete(assignment_url(employee.id, go.id))

    assert (first.status_code, second.status_code) == (204, 204)
    assert await employee_skills(client, employee.id) == [("Python", "expert")]
    assert await session.scalar(select(func.count()).select_from(Skill)) == 2


@pytest.mark.parametrize("method", ["put", "delete"])
async def test_unknown_employee_or_skill_is_a_404_problem(
    client: AsyncClient, session: AsyncSession, method: str
) -> None:
    employee, skill = make_employee(), Skill(name="Go")
    await persist(session, employee, skill)
    body = {"level": "advanced"} if method == "put" else None

    unknown_employee = await client.request(method, assignment_url(999999, skill.id), json=body)
    unknown_skill = await client.request(method, assignment_url(employee.id, 999999), json=body)

    assert (unknown_employee.status_code, unknown_skill.status_code) == (404, 404)
    assert unknown_employee.json()["detail"] == "Employee 999999 does not exist"
    assert unknown_skill.json()["detail"] == "Skill 999999 does not exist"


def skills_url(employee_id: int) -> str:
    return f"/api/v1/employees/{employee_id}/skills"


async def test_replaces_all_skills_in_one_request(
    client: AsyncClient, session: AsyncSession
) -> None:
    go, python, k8s = Skill(name="Go"), Skill(name="Python"), Skill(name="Kubernetes")
    employee = make_employee({go: ProficiencyLevel.BEGINNER, python: ProficiencyLevel.EXPERT})
    await persist(session, employee, k8s)

    response = await client.put(
        skills_url(employee.id),
        json={
            "skills": [
                {"skill_id": python.id, "level": "advanced"},
                {"skill_id": k8s.id, "level": "expert"},
            ]
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert [(s["skill"]["name"], s["level"]) for s in response.json()["skills"]] == [
        ("Kubernetes", "expert"),
        ("Python", "advanced"),
    ]
    assert await employee_skills(client, employee.id) == [
        ("Kubernetes", "expert"),
        ("Python", "advanced"),
    ]


async def test_replacing_leaves_unchanged_assignments_untouched(
    client: AsyncClient, session: AsyncSession
) -> None:
    go, python = Skill(name="Go"), Skill(name="Python")
    employee = make_employee({go: ProficiencyLevel.BEGINNER, python: ProficiencyLevel.EXPERT})
    await persist(session, employee)
    # now() is fixed within the test's transaction, so updated_at cannot show an update;
    # the row's physical location (ctid) changes with every update.
    row_version = text("SELECT ctid::text FROM employee_skill WHERE skill_id = :id")
    go_before = await session.scalar(row_version, {"id": go.id})
    python_before = await session.scalar(row_version, {"id": python.id})

    await client.put(
        skills_url(employee.id),
        json={
            "skills": [
                {"skill_id": go.id, "level": "advanced"},
                {"skill_id": python.id, "level": "expert"},
            ]
        },
    )

    assert await session.scalar(row_version, {"id": go.id}) != go_before
    assert await session.scalar(row_version, {"id": python.id}) == python_before


async def test_replacing_with_nothing_removes_every_skill(
    client: AsyncClient, session: AsyncSession
) -> None:
    employee = make_employee({Skill(name="Go"): ProficiencyLevel.BEGINNER})
    await persist(session, employee)

    response = await client.put(skills_url(employee.id), json={"skills": []})

    assert response.json()["skills"] == []
    assert await session.scalar(select(func.count()).select_from(EmployeeSkill)) == 0


async def test_only_assigns_skills_from_the_catalogue(
    client: AsyncClient, session: AsyncSession
) -> None:
    go = Skill(name="Go")
    employee = make_employee({go: ProficiencyLevel.BEGINNER})
    await persist(session, employee)

    response = await client.put(
        skills_url(employee.id),
        json={
            "skills": [
                {"skill_id": go.id, "level": "expert"},
                {"skill_id": 999999, "level": "expert"},
            ]
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Unknown skills: 999999"
    assert await employee_skills(client, employee.id) == [("Go", "beginner")]
    assert await session.scalar(select(func.count()).select_from(Skill)) == 1


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
async def test_rejects_an_invalid_skill_list(
    client: AsyncClient, session: AsyncSession, skills: list[dict[str, object]], reason: str
) -> None:
    employee = make_employee({Skill(name="Go"): ProficiencyLevel.BEGINNER})
    await persist(session, employee)

    response = await client.put(skills_url(employee.id), json={"skills": skills})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert reason in response.json()["errors"][0]["reason"]
    assert await employee_skills(client, employee.id) == [("Go", "beginner")]


async def test_replacing_skills_of_an_unknown_employee_is_a_404(client: AsyncClient) -> None:
    response = await client.put(skills_url(999999), json={"skills": []})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Employee 999999 does not exist"
