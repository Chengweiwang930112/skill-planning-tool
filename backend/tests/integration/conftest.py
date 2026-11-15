"""Against a real PostgreSQL, migrated from scratch once per run; each test runs in a
transaction that is rolled back afterwards."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "APP_TEST_DATABASE_URL", "postgresql+psycopg://skills:skills@localhost:5432/skills_test"
)
SAMPLES = Path(__file__).parents[3] / "samples"


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    config = Config(Path(__file__).parents[2] / "alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


@pytest.fixture(scope="session")
def migrated_database(alembic_config: Config) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


@pytest.fixture(scope="session")
def engine(migrated_database: None) -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        transaction.rollback()


@pytest.fixture
def app(session: Session) -> FastAPI:
    app = create_app(Settings(environment="test", database_url=TEST_DATABASE_URL))

    def override_session() -> Iterator[Session]:
        yield session
        # Every request gets a fresh session in production; forget what this one loaded.
        session.expunge_all()

    app.dependency_overrides[get_session] = override_session
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client
