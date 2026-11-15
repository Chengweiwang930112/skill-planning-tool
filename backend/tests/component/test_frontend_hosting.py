from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.limits import MAX_REQUEST_BYTES
from app.main import create_app
from tests.component.conftest import UNUSED_DATABASE

INDEX = "<!doctype html><app-root></app-root>"
SCRIPT = "console.log('app');" * 200


@pytest.fixture
def site(tmp_path: Path) -> Iterator[TestClient]:
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "main-AB12cd_3.js").write_text(SCRIPT)
    (tmp_path / "favicon.svg").write_text("<svg/>")
    app = create_app(
        Settings(environment="test", database_url=UNUSED_DATABASE, static_dir=tmp_path)
    )
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/employees", "/search?skill=go:expert&employee=1"])
def test_serves_the_app_for_its_own_routes(site: TestClient, path: str) -> None:
    # When
    response = site.get(path)

    # Then
    assert response.status_code == status.HTTP_200_OK
    assert response.text == INDEX
    assert response.headers["cache-control"] == "no-cache"


def test_caches_files_with_a_content_hash_for_good(site: TestClient) -> None:
    # When
    hashed = site.get("/main-AB12cd_3.js")
    plain = site.get("/favicon.svg")

    # Then
    assert hashed.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert plain.headers["cache-control"] == "no-cache"


def test_compresses_responses(site: TestClient) -> None:
    # When
    response = site.get("/main-AB12cd_3.js", headers={"accept-encoding": "gzip"})

    # Then
    assert response.headers["content-encoding"] == "gzip"
    assert response.text == SCRIPT


def test_keeps_unknown_api_paths_a_404_problem(site: TestClient) -> None:
    # When
    response = site.get("/api/v2/whatever")

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"


def test_refuses_to_change_the_app(site: TestClient) -> None:
    # When
    response = site.post("/employees")

    # Then
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_routes_still_win_over_the_app(site: TestClient) -> None:
    # When
    response = site.get("/healthz")

    # Then
    assert response.json()["status"] == "ok"


def test_refuses_oversized_requests_before_reading_them(site: TestClient) -> None:
    # Given
    headers = {"content-length": str(MAX_REQUEST_BYTES + 1), "content-type": "text/csv"}

    # When
    response = site.post("/api/v1/imports", content=b"", headers=headers)

    # Then
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json()["detail"] == "The request is larger than 12 MB"


def test_serves_no_app_without_a_build(client: TestClient) -> None:
    # When
    response = client.get("/employees")

    # Then
    assert response.status_code == status.HTTP_404_NOT_FOUND
