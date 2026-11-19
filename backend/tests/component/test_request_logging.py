"""Request ids, request log lines and unexpected errors, with the services mocked."""

import logging
import re
from typing import Any

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.services import employees_service
from tests.component.conftest import MockService
from tests.factories import make_employee


@pytest.fixture
def logs(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level("INFO", logger="app")
    return caplog


def request_lines(logs: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in logs.records if r.name == "app" and hasattr(r, "duration_ms")]


def fields(line: logging.LogRecord, *names: str) -> tuple[Any, ...]:
    return tuple(getattr(line, name) for name in names)


def test_gives_every_request_an_id_and_logs_one_line_for_it(
    client: TestClient, mock_service: MockService, logs: pytest.LogCaptureFixture
) -> None:
    # Given
    mock_service(employees_service, "get_employee", return_value=make_employee(id=1))

    # When
    response = client.get("/api/v1/employees/1")

    # Then
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
    [line] = request_lines(logs)
    assert fields(line, "method", "path", "status") == ("GET", "/api/v1/employees/1", 200)
    assert line.getMessage() == "GET /api/v1/employees/1 200"


@pytest.mark.parametrize(
    ("given", "kept"), [("trace-42.a_b", True), ("bad id\r\nx", False), ("x" * 65, False)]
)
def test_keeps_a_callers_request_id_only_if_it_is_safe(
    client: TestClient, given: str, kept: bool
) -> None:
    # When
    response = client.get("/healthz", headers={"X-Request-ID": given})

    # Then
    assert (response.headers["x-request-id"] == given) is kept


def test_does_not_log_health_probes_that_pass(
    client: TestClient, logs: pytest.LogCaptureFixture
) -> None:
    # When
    client.get("/healthz")

    # Then
    assert request_lines(logs) == []


def test_an_unexpected_error_is_a_logged_500_problem_with_the_request_id(
    app: FastAPI, mock_service: MockService, logs: pytest.LogCaptureFixture
) -> None:
    # Given
    mock_service(employees_service, "get_employee", side_effect=RuntimeError("database gone"))

    # When
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/employees/1", headers={"X-Request-ID": "trace-42"})

    # Then
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["x-request-id"] == "trace-42"
    assert "database gone" not in response.text
    [error] = [r for r in logs.records if r.name == "app.core.errors"]
    assert error.request_id == "trace-42"  # type: ignore[attr-defined]
    assert error.exc_info and "database gone" in str(error.exc_info[1])
    [line] = request_lines(logs)
    assert fields(line, "status") == (500,)
