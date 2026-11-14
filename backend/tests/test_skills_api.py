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


async def test_creates_a_skill_with_normalised_whitespace(client: AsyncClient) -> None:
    skill = await create_skill(client, "  Apache   Kafka ")

    assert skill["name"] == "Apache Kafka"


async def test_returns_the_existing_skill_regardless_of_case(
    client: AsyncClient, session: AsyncSession
) -> None:
    existing = await create_skill(client, "Kubernetes")

    response = await client.post(SKILLS, json={"name": "kubernetes"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == existing
    assert await session.scalar(select(func.count()).select_from(Skill)) == 1


@pytest.mark.parametrize("name", ["", "   ", "x" * 101], ids=["empty", "blank", "too-long"])
async def test_rejects_invalid_skill_names(client: AsyncClient, name: str) -> None:
    response = await client.post(SKILLS, json={"name": name})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert [error["name"] for error in response.json()["errors"]] == ["name"]


async def test_lists_skills_alphabetically_ignoring_case(
    client: AsyncClient, session: AsyncSession
) -> None:
    await persist(session, *(Skill(name=name) for name in ["python", "Angular", "Kubernetes"]))

    page = (await client.get(SKILLS)).json()

    assert [skill["name"] for skill in page["items"]] == ["Angular", "Kubernetes", "python"]
    assert page["total"] == 3


async def test_filters_skills_by_part_of_the_name(
    client: AsyncClient, session: AsyncSession
) -> None:
    await persist(session, *(Skill(name=name) for name in ["TypeScript", "JavaScript", "Go"]))

    page = (await client.get(SKILLS, params={"q": "script", "page_size": 1})).json()

    assert ([skill["name"] for skill in page["items"]], page["total"]) == (["JavaScript"], 2)


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
                {"name": "python", "level": "advanced"},
                {"name": "kubernetes", "level": "expert"},
                {"name": "Rust", "level": "beginner"},
            ]
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert [(s["skill"]["name"], s["level"]) for s in response.json()["skills"]] == [
        ("Kubernetes", "expert"),
        ("Python", "advanced"),
        ("Rust", "beginner"),
    ]
    assert await employee_skills(client, employee.id) == [
        ("Kubernetes", "expert"),
        ("Python", "advanced"),
        ("Rust", "beginner"),
    ]
    assert await session.scalar(select(func.count()).select_from(Skill)) == 4


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
            "skills": [{"name": "Go", "level": "advanced"}, {"name": "Python", "level": "expert"}]
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


@pytest.mark.parametrize(
    ("skills", "reason"),
    [
        (
            [{"name": "Go", "level": "expert"}, {"name": "go", "level": "beginner"}],
            "more than once",
        ),
        ([{"name": "Go", "level": "guru"}], "must be one of"),
        ([{"name": " ", "level": "expert"}], "at least 1 character"),
    ],
    ids=["duplicate", "level", "blank-name"],
)
async def test_rejects_an_invalid_skill_list(
    client: AsyncClient, session: AsyncSession, skills: list[dict[str, str]], reason: str
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
