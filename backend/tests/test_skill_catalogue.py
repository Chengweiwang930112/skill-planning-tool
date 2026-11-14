from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ProficiencyLevel, Skill, skill_key
from tests.factories import make_employee, persist

URL = "/api/v1/skills"


def create(client: TestClient, name: str) -> Any:
    response = client.post(URL, json={"name": name})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def names(client: TestClient, **params: Any) -> list[str]:
    return [skill["name"] for skill in (client.get(URL, params=params)).json()["items"]]


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


def test_adds_a_skill_with_normalised_whitespace(client: TestClient) -> None:
    assert (create(client, "  Apache   Kafka "))["name"] == "Apache Kafka"


@pytest.mark.parametrize("duplicate", ["nodejs", "Node JS", " node.js "])
def test_refuses_a_skill_that_differs_only_in_case_spaces_or_punctuation(
    client: TestClient, session: Session, duplicate: str
) -> None:
    existing = create(client, "Node.js")

    response = client.post(URL, json={"name": duplicate})

    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.json()["detail"] == f"The catalogue already has Node.js (skill {existing['id']})"
    )
    assert session.scalar(select(func.count()).select_from(Skill)) == 1


def test_keeps_c_cplusplus_and_csharp_apart(client: TestClient) -> None:
    for name in ["C", "C++", "C#"]:
        create(client, name)

    assert names(client) == ["C", "C#", "C++"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 101], ids=["empty", "blank", "too-long"])
def test_rejects_invalid_skill_names(client: TestClient, name: str) -> None:
    response = client.post(URL, json={"name": name})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert [error["name"] for error in response.json()["errors"]] == ["name"]


def test_lists_skills_alphabetically_with_their_employee_counts(
    client: TestClient, session: Session
) -> None:
    python, k8s, angular = Skill(name="python"), Skill(name="Kubernetes"), Skill(name="Angular")
    persist(
        session,
        make_employee({python: ProficiencyLevel.EXPERT, k8s: ProficiencyLevel.BEGINNER}),
        make_employee({python: ProficiencyLevel.BEGINNER}),
        angular,
    )

    page = (client.get(URL)).json()

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
def test_finds_skills_by_part_of_the_name_ignoring_punctuation(
    client: TestClient, session: Session, q: str, expected: list[str]
) -> None:
    persist(session, *(Skill(name=n) for n in ["TypeScript", "JavaScript", "Node.js", "Go"]))

    assert names(client, q=q) == expected


def test_renames_a_skill_for_everyone_who_has_it(client: TestClient, session: Session) -> None:
    skill = Skill(name="kubernetes")
    employee = make_employee({skill: ProficiencyLevel.ADVANCED})
    persist(session, employee)

    response = client.patch(f"{URL}/{skill.id}", json={"name": "Kubernetes"})

    assert (response.status_code, response.json()["name"]) == (200, "Kubernetes")
    detail = (client.get(f"/api/v1/employees/{employee.id}")).json()
    assert detail["skills"][0]["skill"]["name"] == "Kubernetes"


def test_refuses_to_rename_a_skill_into_another_one(client: TestClient, session: Session) -> None:
    go, golang = Skill(name="Go"), Skill(name="Golang")
    persist(session, go, golang)

    response = client.patch(f"{URL}/{golang.id}", json={"name": "go"})

    assert response.status_code == status.HTTP_409_CONFLICT
    assert names(client) == ["Go", "Golang"]


def test_deletes_a_skill_nobody_has(client: TestClient) -> None:
    skill = create(client, "COBOL")

    response = client.delete(f"{URL}/{skill['id']}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert names(client) == []


def test_refuses_to_delete_a_skill_someone_has(client: TestClient, session: Session) -> None:
    skill = Skill(name="Go")
    persist(session, make_employee({skill: ProficiencyLevel.EXPERT}))

    response = client.delete(f"{URL}/{skill.id}")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The skill is assigned to 1 employees"


@pytest.mark.parametrize(
    ("method", "body"), [("patch", {"name": "Go"}), ("delete", None)], ids=["rename", "delete"]
)
def test_unknown_skill_is_a_404(
    client: TestClient, method: str, body: dict[str, str] | None
) -> None:
    response = client.request(method, f"{URL}/999999", json=body)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Skill 999999 does not exist"


def test_imports_a_list_of_skills(client: TestClient, session: Session) -> None:
    persist(session, Skill(name="Kubernetes"))
    content = (
        "Name;Category\nkubernetes;Cloud\nApache   Kafka;Data\nNode.js;Web\nnodejs;Web\n"
        f"{'x' * 101};Too long\n;\n"
    ).encode("cp1252")

    response = client.post(f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")})

    assert response.json() == {
        "rows_created": 2,
        "rows_existing": 2,
        "row_errors": [
            {"row": 6, "field": "name", "message": "String should have at most 100 characters"}
        ],
    }
    assert names(client) == ["Apache Kafka", "Kubernetes", "Node.js"]


def test_importing_the_same_skills_again_changes_nothing(client: TestClient) -> None:
    content = b"name\nGo\nRust\n"
    client.post(f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")})

    response = client.post(f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")})

    assert (response.json()["rows_created"], response.json()["rows_existing"]) == (0, 2)


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        (b"skill\nGo\n", "Missing required column: name"),
        (b"name\n\n", "The file has no skill names"),
    ],
)
def test_rejects_an_unusable_skill_file(client: TestClient, content: bytes, detail: str) -> None:
    response = client.post(f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == detail


def test_searching_employees_matches_skill_names_like_the_catalogue(
    client: TestClient, session: Session
) -> None:
    persist(
        session,
        make_employee({Skill(name="Node.js"): ProficiencyLevel.EXPERT}, last_name="Node"),
    )

    response = client.get("/api/v1/employees", params={"skill": "nodejs:advanced"})

    assert [e["last_name"] for e in response.json()["items"]] == ["Node"]
