import re
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from tests.integration.conftest import TEST_DATABASE_URL


def run_sql(*statements: str) -> list[tuple[object, ...]]:
    """Runs outside the tests' rolled-back transactions; returns the last result."""
    engine = create_engine(TEST_DATABASE_URL)
    rows: list[tuple[object, ...]] = []
    with engine.begin() as connection:
        for statement in statements:
            result = connection.execute(text(statement))
            rows = [tuple(row) for row in result] if result.returns_rows else []
    engine.dispose()
    return rows


@pytest.fixture
def before_skill_keys(alembic_config: Config, migrated_database: None) -> Iterator[None]:
    command.downgrade(alembic_config, "0002")
    try:
        yield
    finally:
        run_sql("DELETE FROM skill")
        command.upgrade(alembic_config, "head")


@pytest.mark.usefixtures("before_skill_keys")
def test_skill_keys_are_filled_in_for_existing_skills(alembic_config: Config) -> None:
    # Given
    run_sql("INSERT INTO skill (name) VALUES ('Node.js'), ('C++'), ('C#'), ('C')")

    # When
    command.upgrade(alembic_config, "head")

    # Then
    assert run_sql("SELECT name, key FROM skill ORDER BY name") == [
        ("C", "c"),
        ("C#", "csharp"),
        ("C++", "cplusplus"),
        ("Node.js", "nodejs"),
    ]


@pytest.mark.usefixtures("before_skill_keys")
def test_skill_keys_are_not_added_while_skills_would_clash(alembic_config: Config) -> None:
    # Given
    run_sql("INSERT INTO skill (name) VALUES ('Node.js'), ('NodeJS'), ('Go')")

    # When / Then
    with pytest.raises(
        RuntimeError, match=re.escape("rename or remove them first: Node.js = NodeJS")
    ):
        command.upgrade(alembic_config, "head")

    assert run_sql("SELECT version_num FROM alembic_version") == [("0002",)]
