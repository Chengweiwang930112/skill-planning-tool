from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.limits import MAX_REQUEST_BYTES
from app.main import create_app
from tests.conftest import TEST_DATABASE_URL

INDEX = "<!doctype html><app-root></app-root>"
SCRIPT = "console.log('app');" * 200


@pytest.fixture
async def site(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "main-AB12cd_3.js").write_text(SCRIPT)
    (tmp_path / "favicon.svg").write_text("<svg/>")
    app = create_app(
        Settings(environment="test", database_url=TEST_DATABASE_URL, static_dir=tmp_path)
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


@pytest.mark.parametrize("path", ["/", "/employees", "/search?skill=go:expert&employee=1"])
async def test_serves_the_app_for_its_own_routes(site: AsyncClient, path: str) -> None:
    response = await site.get(path)

    assert response.status_code == status.HTTP_200_OK
    assert response.text == INDEX
    assert response.headers["cache-control"] == "no-cache"


async def test_caches_files_with_a_content_hash_for_good(site: AsyncClient) -> None:
    hashed = await site.get("/main-AB12cd_3.js")
    plain = await site.get("/favicon.svg")

    assert hashed.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert plain.headers["cache-control"] == "no-cache"


async def test_compresses_responses(site: AsyncClient) -> None:
    response = await site.get("/main-AB12cd_3.js", headers={"accept-encoding": "gzip"})

    assert response.headers["content-encoding"] == "gzip"
    assert response.text == SCRIPT


async def test_keeps_unknown_api_paths_a_404_problem(site: AsyncClient) -> None:
    response = await site.get("/api/v2/whatever")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"] == "application/problem+json"


async def test_refuses_to_change_the_app(site: AsyncClient) -> None:
    response = await site.post("/employees")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


async def test_routes_still_win_over_the_app(site: AsyncClient) -> None:
    response = await site.get("/healthz")

    assert response.json()["status"] == "ok"


async def test_refuses_oversized_requests_before_reading_them(site: AsyncClient) -> None:
    response = await site.post(
        "/api/v1/imports",
        content=b"",
        headers={"content-length": str(MAX_REQUEST_BYTES + 1), "content-type": "text/csv"},
    )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json()["detail"] == "The request is larger than 12 MB"


async def test_serves_no_app_without_a_build(client: AsyncClient) -> None:
    response = await client.get("/employees")

    assert response.status_code == status.HTTP_404_NOT_FOUND
