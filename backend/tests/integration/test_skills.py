from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ProficiencyLevel, Skill
from tests.factories import make_employee, persist
from tests.integration.conftest import SAMPLES

URL = "/api/v1/skills"


def create(client: TestClient, name: str) -> Any:
    response = client.post(URL, json={"name": name})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def names(client: TestClient, **params: Any) -> list[str]:
    return [skill["name"] for skill in client.get(URL, params=params).json()["items"]]


def upload(client: TestClient, content: bytes) -> Any:
    return client.post(f"{URL}/import", files={"file": ("skills.csv", content, "text/csv")})


def skill_count(session: Session) -> int | None:
    return session.scalar(select(func.count()).select_from(Skill))


def test_adds_a_skill_with_normalised_whitespace(client: TestClient) -> None:
    # When
    skill = create(client, "  Apache   Kafka ")

    # Then
    assert skill["name"] == "Apache Kafka"
    assert names(client) == ["Apache Kafka"]


@pytest.mark.parametrize("duplicate", ["nodejs", "Node JS", " node.js "])
def test_refuses_a_skill_that_differs_only_in_case_spaces_or_punctuation(
    client: TestClient, session: Session, duplicate: str
) -> None:
    # Given
    existing = create(client, "Node.js")

    # When
    response = client.post(URL, json={"name": duplicate})

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert (
        response.json()["detail"] == f"The catalogue already has Node.js (skill {existing['id']})"
    )
    assert skill_count(session) == 1


def test_keeps_c_cplusplus_and_csharp_apart(client: TestClient) -> None:
    # When
    for name in ["C", "C++", "C#"]:
        create(client, name)

    # Then
    assert names(client) == ["C", "C#", "C++"]


def test_lists_skills_alphabetically_with_their_employee_counts(
    client: TestClient, session: Session
) -> None:
    # Given
    python, k8s, angular = Skill(name="python"), Skill(name="Kubernetes"), Skill(name="Angular")
    persist(
        session,
        make_employee({python: ProficiencyLevel.EXPERT, k8s: ProficiencyLevel.BEGINNER}),
        make_employee({python: ProficiencyLevel.BEGINNER}),
        angular,
    )

    # When
    page = client.get(URL).json()

    # Then
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
    # Given
    persist(session, *(Skill(name=n) for n in ["TypeScript", "JavaScript", "Node.js", "Go"]))

    # When
    result = names(client, q=q)

    # Then
    assert result == expected


def test_renames_a_skill_for_everyone_who_has_it(client: TestClient, session: Session) -> None:
    # Given
    skill = Skill(name="kubernetes")
    employee = make_employee({skill: ProficiencyLevel.ADVANCED})
    persist(session, employee)

    # When
    response = client.patch(f"{URL}/{skill.id}", json={"name": "Kubernetes"})

    # Then
    assert response.json()["name"] == "Kubernetes"
    detail = client.get(f"/api/v1/employees/{employee.id}").json()
    assert detail["skills"][0]["skill"]["name"] == "Kubernetes"


def test_refuses_to_rename_a_skill_into_another_one(client: TestClient, session: Session) -> None:
    # Given
    go, golang = Skill(name="Go"), Skill(name="Golang")
    persist(session, go, golang)

    # When
    response = client.patch(f"{URL}/{golang.id}", json={"name": "go"})

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert names(client) == ["Go", "Golang"]


def test_deletes_a_skill_nobody_has(client: TestClient) -> None:
    # Given
    skill = create(client, "COBOL")

    # When
    response = client.delete(f"{URL}/{skill['id']}")

    # Then
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert names(client) == []


def test_refuses_to_delete_a_skill_someone_has(client: TestClient, session: Session) -> None:
    # Given
    skill = Skill(name="Go")
    persist(session, make_employee({skill: ProficiencyLevel.EXPERT}))

    # When
    response = client.delete(f"{URL}/{skill.id}")

    # Then
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "The skill is assigned to 1 employees"
    assert skill_count(session) == 1


def test_imports_the_new_names_of_a_file(client: TestClient, session: Session) -> None:
    # Given
    persist(session, Skill(name="Kubernetes"))
    content = (
        "Name;Category\nkubernetes;Cloud\nApache   Kafka;Data\nNode.js;Web\nnodejs;Web\n"
        f"{'x' * 101};Too long\n;\n"
    ).encode("cp1252")

    # When
    response = upload(client, content)

    # Then
    assert response.json() == {
        "rows_created": 2,
        "rows_existing": 2,
        "row_errors": [
            {"row": 6, "field": "name", "message": "String should have at most 100 characters"}
        ],
    }
    assert names(client) == ["Apache Kafka", "Kubernetes", "Node.js"]


def test_importing_the_sample_twice_adds_its_skills_once(client: TestClient) -> None:
    # Given
    content = (SAMPLES / "skills.csv").read_bytes()
    first = upload(client, content).json()

    # When
    second = upload(client, content).json()

    # Then
    assert (first["rows_created"], first["rows_existing"]) == (44, 0)
    assert (second["rows_created"], second["rows_existing"]) == (0, 44)
    assert client.get(URL).json()["total"] == 44


def test_rejects_an_unusable_skill_file(client: TestClient) -> None:
    # When
    response = upload(client, b"skill\nGo\n")

    # Then
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["detail"] == "Missing required column: name"
