from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Skill
from app.schemas import SkillQuery
from app.services.skills import (
    DuplicateSkillError,
    SkillInUseError,
    create_skill,
    delete_skill,
    import_skills,
    list_skills,
    rename_skill,
)
from tests.component.conftest import sql

GO = Skill(id=7, name="Go")


def test_lists_skills_with_their_employee_counts(session: MagicMock) -> None:
    # Given
    session.scalar.return_value = 1
    session.execute.return_value = [(GO, 12)]

    # When
    rows, total = list_skills(session, SkillQuery())

    # Then
    assert (rows, total) == ([(GO, 12)], 1)
    statement = sql(session.execute.call_args.args[0])
    assert "count(employee_skill.employee_id)" in statement
    assert "LEFT OUTER JOIN employee_skill" in statement
    assert "ORDER BY lower(skill.name)" in statement


@pytest.mark.parametrize(
    ("q", "condition"),
    [
        ("Node.JS", "skill.key LIKE '%' || 'nodejs' || '%' ESCAPE '/'"),
        ("...", "skill.name ILIKE '%' || '...' || '%' ESCAPE '/'"),
    ],
    ids=["by-key", "punctuation-only"],
)
def test_finds_skills_by_their_key_or_else_by_name(
    session: MagicMock, q: str, condition: str
) -> None:
    # Given
    session.scalar.return_value = 0
    session.execute.return_value = []

    # When
    list_skills(session, SkillQuery(q=q))

    # Then
    assert condition in sql(session.execute.call_args.args[0])


def test_adds_a_skill_in_one_statement_that_cannot_race(session: MagicMock) -> None:
    # Given
    created = Skill(id=8, name="Apache Kafka")
    session.scalar.return_value = 8
    session.get.return_value = created

    # When
    skill = create_skill(session, "Apache Kafka")

    # Then
    assert skill is created
    assert sql(session.scalar.call_args.args[0]) == (
        "INSERT INTO skill (name, key) VALUES ('Apache Kafka', 'apachekafka') "
        "ON CONFLICT (key) DO NOTHING RETURNING skill.id"
    )
    session.commit.assert_called_once()


def test_a_conflicting_insert_names_the_existing_skill(session: MagicMock) -> None:
    # Given
    existing = Skill(id=15, name="Node.js")
    session.scalar.side_effect = [None, existing]

    # When / Then
    with pytest.raises(DuplicateSkillError) as error:
        create_skill(session, "nodejs")
    assert error.value.existing is existing


def test_renames_a_skill(session: MagicMock) -> None:
    # Given
    skill = Skill(id=7, name="go")
    session.scalar.return_value = skill

    # When
    renamed = rename_skill(session, skill, "Go")

    # Then
    assert (renamed.name, renamed.key) == ("Go", "go")
    session.commit.assert_called_once()


def test_refuses_to_rename_into_another_skill_without_changing_anything(
    session: MagicMock,
) -> None:
    # Given
    skill = Skill(id=8, name="Golang")
    session.scalar.return_value = GO

    # When / Then
    with pytest.raises(DuplicateSkillError):
        rename_skill(session, skill, "go")
    assert skill.name == "Golang"
    session.commit.assert_not_called()


def test_a_rename_racing_another_one_rolls_back(session: MagicMock) -> None:
    # Given
    skill = Skill(id=8, name="Golang")
    session.scalar.side_effect = [None, GO]
    session.commit.side_effect = IntegrityError("UPDATE skill", {}, Exception("uq_skill_key"))

    # When / Then
    with pytest.raises(DuplicateSkillError) as error:
        rename_skill(session, skill, "go")
    assert error.value.existing is GO
    session.rollback.assert_called_once()


def test_deletes_a_skill_nobody_has(session: MagicMock) -> None:
    # Given
    session.scalar.return_value = 0

    # When
    delete_skill(session, GO)

    # Then
    session.delete.assert_called_once_with(GO)
    session.commit.assert_called_once()


def test_refuses_to_delete_a_skill_someone_has(session: MagicMock) -> None:
    # Given
    session.scalar.return_value = 3

    # When / Then
    with pytest.raises(SkillInUseError, match="assigned to 3 employees"):
        delete_skill(session, GO)
    session.delete.assert_not_called()


def test_imports_each_new_name_once_and_leaves_existing_ones_alone(session: MagicMock) -> None:
    # Given
    session.scalars.return_value.all.return_value = [21]
    content = b"name\nNode.js\nGo\nnodejs\n"

    # When
    result = import_skills(session, content)

    # Then
    assert (result.rows_created, result.rows_existing) == (1, 2)
    statement = sql(session.scalars.call_args.args[0])
    assert "('Node.js', 'nodejs')" in statement
    assert "('Go', 'go')" in statement
    assert "'nodejs', 'nodejs'" not in statement
    assert "ON CONFLICT (key) DO NOTHING" in statement
    session.commit.assert_called_once()


def test_a_file_with_only_invalid_names_inserts_nothing(session: MagicMock) -> None:
    # Given
    content = f"name\n{'x' * 101}\n".encode()

    # When
    result = import_skills(session, content)

    # Then
    assert (result.rows_created, len(result.row_errors)) == (0, 1)
    session.scalars.assert_not_called()
    session.commit.assert_not_called()
