from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProficiencyLevel, Skill, skill_key
from tests.factories import make_employee, persist

URL = "/api/v1/skills"


async def create(client: AsyncClient, name: str) -> Any:
    response = await client.post(URL, json={"name": name})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


async def names(client: AsyncClient, **params: Any) -> list[str]:
    return [skill["name"] for skill in (await client.get(URL, params=params)).json()["items"]]


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Node.js", "nodejs"),
        ("node js", "nodejs"),
        ("CI/CD", "cicd"),
        ("C", "c"),
        ("C++", "cplusplus"),
        ("C#", "csharp"),
        ("Größe", "grösse"),
    ],
)
def test_a_skill_key_ignores_case_spaces_and_punctuation_but_not_plus_or_sharp(
    name: str, key: str
) -> None:
    assert skill_key(name) == key


async def test_adds_a_skill_with_normalised_whitespace(client: AsyncClient) -> None:
    assert (await create(client, "  Apache   Kafka "))["name"] == "Apache Kafka"


@pytest.mark.parametrize("duplicate", ["nodejs", "Node JS", " node.js "])
async def test_refuses_a_skill_that_differs_only_in_case_spaces_or_punctuation(
    client: AsyncClient, session: AsyncSession, duplicate: str
) -> None:
    existing = await create(client, "Node.js")

    response = await client.post(URL, json={"name": duplicate})

    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.json()["detail"] == f"The catalogue already has Node.js (skill {existing['id']})"
    )
    assert await session.scalar(select(func.count()).select_from(Skill)) == 1


async def test_keeps_c_cplusplus_and_csharp_apart(client: AsyncClient) -> None:
    for name in ["C", "C++", "C#"]:
        await create(client, name)

    assert await names(client) == ["C", "C#", "C++"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 101], ids=["empty", "blank", "too-long"])
async def test_rejects_invalid_skill_names(client: AsyncClient, name: str) -> None:
    response = await client.post(URL, json={"name": name})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert [error["name"] for error in response.json()["errors"]] == ["name"]


async def test_lists_skills_alphabetically_with_their_employee_counts(
    client: AsyncClient, session: AsyncSession
) -> None:
    python, k8s, angular = Skill(name="python"), Skill(name="Kubernetes"), Skill(name="Angular")
    await persist(
        session,
        make_employee({python: ProficiencyLevel.EXPERT, k8s: ProficiencyLevel.BEGINNER}),
        make_employee({python: ProficiencyLevel.BEGINNER}),
        angular,
    )

    page = (await client.get(URL)).json()

    assert [(s["name"], s["employee_count"]) for s in page["items"]] == [
        ("Angular", 0),
        ("Kubernetes", 1),
        ("python", 2),
    ]
    assert page["total"] == 3


@pytest.mark.parametrize(
    ("q", "expected"),
    [("script", ["JavaScript", "TypeScript"]), ("nodejs", ["Node.js"]), ("node.", ["Node.js"])],
)
async def test_finds_skills_by_part_of_the_name_ignoring_punctuation(
    client: AsyncClient, session: AsyncSession, q: str, expected: list[str]
) -> None:
    await persist(session, *(Skill(name=n) for n in ["TypeScript", "JavaScript", "Node.js", "Go"]))

    assert await names(client, q=q) == expected


async def test_renames_a_skill_for_everyone_who_has_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    skill = Skill(name="kubernetes")
    employee = make_employee({skill: ProficiencyLevel.ADVANCED})
    await persist(session, employee)

    response = await client.patch(f"{URL}/{skill.id}", json={"name": "Kubernetes"})

    assert (response.status_code, response.json()["name"]) == (200, "Kubernetes")
    detail = (await client.get(f"/api/v1/employees/{employee.id}")).json()
    assert detail["skills"][0]["skill"]["name"] == "Kubernetes"


async def test_refuses_to_rename_a_skill_into_another_one(
    client: AsyncClient, session: AsyncSession
) -> None:
    go, golang = Skill(name="Go"), Skill(name="Golang")
    await persist(session, go, golang)

    response = await client.patch(f"{URL}/{golang.id}", json={"name": "go"})

    assert response.status_code == status.HTTP_409_CONFLICT
    assert await names(client) == ["Go", "Golang"]


async def test_deletes_a_skill_nobody_has(client: AsyncClient) -> None:
    skill = await create(client, "COBOL")

    response = await client.delete(f"{URL}/{skill['id']}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert await names(client) == []


async def test_refuses_to_delete_a_skill_someone_has(
    client: AsyncClient, session: AsyncSession
) -> None:
    skill = Skill(name="Go")
    await persist(session, make_employee({skill: ProficiencyLevel.EXPERT}))

    response = await client.delete(f"{URL}/{skill.id}")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The skill is assigned to 1 employees"


@pytest.mark.parametrize(
    ("method", "body"), [("patch", {"name": "Go"}), ("delete", None)], ids=["rename", "delete"]
)
async def test_unknown_skill_is_a_404(
    client: AsyncClient, method: str, body: dict[str, str] | None
) -> None:
    response = await client.request(method, f"{URL}/999999", json=body)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Skill 999999 does not exist"


async def test_imports_a_list_of_skills(client: AsyncClient, session: AsyncSession) -> None:
    await persist(session, Skill(name="Kubernetes"))
    content = (
        "Name;Category\nkubernetes;Cloud\nApache   Kafka;Data\nNode.js;Web\nnodejs;Web\n"
        f"{'x' * 101};Too long\n;\n"
    ).encode("cp1252")

    response = await client.post(
        f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")}
    )

    assert response.json() == {
        "rows_created": 2,
        "rows_existing": 2,
        "row_errors": [
            {"row": 6, "field": "name", "message": "String should have at most 100 characters"}
        ],
    }
    assert await names(client) == ["Apache Kafka", "Kubernetes", "Node.js"]


async def test_importing_the_same_skills_again_changes_nothing(client: AsyncClient) -> None:
    content = b"name\nGo\nRust\n"
    await client.post(f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")})

    response = await client.post(
        f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")}
    )

    assert (response.json()["rows_created"], response.json()["rows_existing"]) == (0, 2)


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        (b"skill\nGo\n", "Missing required column: name"),
        (b"name\n\n", "The file has no skill names"),
    ],
)
async def test_rejects_an_unusable_skill_file(
    client: AsyncClient, content: bytes, detail: str
) -> None:
    response = await client.post(
        f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == detail


async def test_searching_employees_matches_skill_names_like_the_catalogue(
    client: AsyncClient, session: AsyncSession
) -> None:
    await persist(
        session,
        make_employee({Skill(name="Node.js"): ProficiencyLevel.EXPERT}, last_name="Node"),
    )

    response = await client.get("/api/v1/employees", params={"skill": "nodejs:advanced"})

    assert [e["last_name"] for e in response.json()["items"]] == ["Node"]
