from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProficiencyLevel, Skill
from tests.factories import make_employee, persist

URL = "/api/v1/employees"
BEGINNER, INTERMEDIATE, ADVANCED, EXPERT = ProficiencyLevel


@pytest.fixture
async def team(session: AsyncSession) -> None:
    k8s, python, go = Skill(name="Kubernetes"), Skill(name="Python"), Skill(name="Go")
    await persist(
        session,
        make_employee({k8s: INTERMEDIATE, python: EXPERT}, last_name="Intermediate"),
        make_employee({k8s: ADVANCED, python: BEGINNER}, last_name="Advanced"),
        make_employee({k8s: EXPERT, go: ADVANCED}, last_name="Expert", department="Mobility"),
        make_employee({python: ADVANCED}, last_name="NoKubernetes"),
    )


async def search(client: AsyncClient, *skills: str, **params: Any) -> list[str]:
    response = await client.get(URL, params={"skill": list(skills), **params})
    assert response.status_code == status.HTTP_200_OK, response.text
    return [employee["last_name"] for employee in response.json()["items"]]


@pytest.mark.usefixtures("team")
async def test_finds_employees_at_the_level_or_higher(client: AsyncClient) -> None:
    assert await search(client, "kubernetes:advanced") == ["Advanced", "Expert"]


@pytest.mark.usefixtures("team")
@pytest.mark.parametrize("criterion", ["Kubernetes", "KUBERNETES:beginner", " kubernetes "])
async def test_a_skill_without_a_level_matches_any_level(
    client: AsyncClient, criterion: str
) -> None:
    assert await search(client, criterion) == ["Advanced", "Expert", "Intermediate"]


@pytest.mark.usefixtures("team")
async def test_requires_every_skill_when_several_are_given(client: AsyncClient) -> None:
    assert await search(client, "kubernetes:advanced", "python") == ["Advanced"]
    assert await search(client, "kubernetes:advanced", "python:advanced") == []


@pytest.mark.usefixtures("team")
async def test_combines_with_the_other_filters_and_counts_matches(client: AsyncClient) -> None:
    response = await client.get(
        URL, params={"skill": "kubernetes:advanced", "department": "mobility", "page_size": 1}
    )

    body = response.json()
    assert ([e["last_name"] for e in body["items"]], body["total"]) == (["Expert"], 1)


@pytest.mark.usefixtures("team")
async def test_returns_all_skills_of_a_match_not_only_the_searched_one(
    client: AsyncClient,
) -> None:
    response = await client.get(URL, params={"skill": "go"})

    [employee] = response.json()["items"]
    assert [(s["skill"]["name"], s["level"]) for s in employee["skills"]] == [
        ("Kubernetes", "expert"),
        ("Go", "advanced"),
    ]


@pytest.mark.usefixtures("team")
async def test_an_unknown_skill_matches_nobody(client: AsyncClient) -> None:
    assert await search(client, "cobol") == []


@pytest.mark.parametrize(
    ("skills", "name", "reason"),
    [
        (["kubernetes:advnced"], "skill.0", "must be one of beginner, intermediate, advanced"),
        (["go", ":expert"], "skill.1", "needs a skill name"),
        ([f"skill{n}" for n in range(11)], "skill", "at most 10 items"),
    ],
    ids=["unknown-level", "missing-name", "too-many"],
)
async def test_rejects_malformed_criteria(
    client: AsyncClient, skills: list[str], name: str, reason: str
) -> None:
    response = await client.get(URL, params={"skill": skills})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    [error] = response.json()["errors"]
    assert error["name"] == name
    assert reason in error["reason"]
