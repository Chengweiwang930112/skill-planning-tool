"""Modules on their own, with what they talk to replaced by mocks: the routers with
mocked services, the services with a mocked database session."""

from collections.abc import Callable, Iterator
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, create_autospec

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql import ClauseElement

from app.core.config import Settings
from app.core.database import get_session
from app.main import create_app

type MockService = Callable[..., MagicMock]

# Never connected to: every request gets the mocked session below.
UNUSED_DATABASE = "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"
# The application's dialect, for rendering statements; creating it connects nowhere.
DIALECT = create_engine("postgresql+psycopg://").dialect


@pytest.fixture
def session() -> MagicMock:
    mock: MagicMock = create_autospec(Session, instance=True)
    return mock


@pytest.fixture
def app(session: MagicMock) -> FastAPI:
    app = create_app(Settings(environment="test", database_url=UNUSED_DATABASE))
    app.dependency_overrides[get_session] = lambda: session
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_service(monkeypatch: pytest.MonkeyPatch) -> MockService:
    """Replaces a service function by a mock with the same signature, so that a call
    the real function would not accept fails the test."""

    def mock(module: ModuleType, name: str, **behaviour: Any) -> MagicMock:
        fake: MagicMock = create_autospec(getattr(module, name), **behaviour)
        monkeypatch.setattr(module, name, fake)
        return fake

    return mock


def sql(statement: ClauseElement) -> str:
    """The statement as PostgreSQL would receive it, values inlined, on one line."""
    compiled = statement.compile(dialect=DIALECT, compile_kwargs={"literal_binds": True})
    # psycopg's parameter style doubles every literal percent sign.
    return " ".join(str(compiled).split()).replace("%%", "%")
