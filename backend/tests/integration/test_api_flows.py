"""A few journeys through the whole stack, HTTP to database: the layers below are
tested on their own, these only show that they are wired together."""

from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.integration.conftest import SAMPLES, TEST_DATABASE_URL


def test_imported_employees_appear_in_the_overview(client: TestClient) -> None:
    # Given
    content = (SAMPLES / "employees.csv").read_bytes()

    # When
    upload = client.post("/api/v1/imports", files={"file": ("employees.csv", content)})

    # Then
    assert upload.status_code == status.HTTP_201_CREATED
    overview = client.get("/api/v1/employees", params={"q": "schmidt"}).json()
    assert [(e["first_name"], e["last_name"]) for e in overview["items"]] == [("Anna", "Schmidt")]
    history = client.get("/api/v1/imports").json()
    assert [item["id"] for item in history["items"]] == [upload.json()["id"]]


def test_skills_assigned_from_the_catalogue_are_found_by_the_skill_search(
    client: TestClient,
) -> None:
    # Given
    client.post(
        "/api/v1/imports", files={"file": ("e.csv", (SAMPLES / "employees.csv").read_bytes())}
    )
    client.post(
        "/api/v1/skills/import", files={"file": ("s.csv", (SAMPLES / "skills.csv").read_bytes())}
    )
    [anna] = client.get("/api/v1/employees", params={"q": "anna schmidt"}).json()["items"]
    [k8s] = client.get("/api/v1/skills", params={"q": "kubernetes"}).json()["items"]

    # When
    saved = client.put(
        f"/api/v1/employees/{anna['id']}/skills",
        json={"skills": [{"skill_id": k8s["id"], "level": "expert"}]},
    )

    # Then
    assert saved.json()["skills"] == [
        {"skill": {"id": k8s["id"], "name": "Kubernetes"}, "level": "expert"}
    ]
    found = client.get("/api/v1/employees", params={"skill": "kubernetes:advanced"}).json()
    assert [e["id"] for e in found["items"]] == [anna["id"]]
    catalogue = client.get("/api/v1/skills", params={"q": "kubernetes"}).json()
    assert catalogue["items"][0]["employee_count"] == 1


def test_the_application_reaches_its_database_without_test_overrides() -> None:
    # Given
    app = create_app(Settings(environment="test", database_url=TEST_DATABASE_URL))

    # When
    with TestClient(app) as client:
        response = client.get("/readyz")

    # Then
    assert response.json() == {"status": "ok"}
