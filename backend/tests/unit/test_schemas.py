from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import ImportStatus, ProficiencyLevel
from app.schemas import (
    EmployeeQuery,
    EmployeeSkillsWrite,
    ImportSummary,
    PageQuery,
    SkillAssignmentRead,
    SkillAssignmentWrite,
    SkillCriterion,
    SkillRead,
    SkillWrite,
    parse_skill_criterion,
)

BEGINNER, INTERMEDIATE, ADVANCED, EXPERT = ProficiencyLevel


def reasons(error: ValidationError) -> list[str]:
    return [e["msg"] for e in error.errors()]


@pytest.mark.parametrize(
    ("value", "level"), [("advanced", ADVANCED), ("EXPERT", EXPERT), (BEGINNER, BEGINNER)]
)
def test_reads_a_level_by_its_name_ignoring_case(value: object, level: ProficiencyLevel) -> None:
    # When
    write = SkillAssignmentWrite.model_validate({"level": value})

    # Then
    assert write.level is level


@pytest.mark.parametrize("value", ["guru", 3, None], ids=["unknown", "number", "null"])
def test_accepts_only_the_names_of_the_levels(value: object) -> None:
    # When / Then
    with pytest.raises(ValidationError) as error:
        SkillAssignmentWrite.model_validate({"level": value})
    assert reasons(error.value) == [
        "Value error, must be one of beginner, intermediate, advanced, expert"
    ]


def test_writes_a_level_as_its_name() -> None:
    # Given
    assignment = SkillAssignmentRead(skill=SkillRead(id=7, name="Go"), level=INTERMEDIATE)

    # When
    body = assignment.model_dump(mode="json")

    # Then
    assert body == {"skill": {"id": 7, "name": "Go"}, "level": "intermediate"}


@pytest.mark.parametrize(
    ("value", "criterion"),
    [
        ("kubernetes:advanced", SkillCriterion("kubernetes", ADVANCED)),
        ("Kubernetes", SkillCriterion("Kubernetes", BEGINNER)),
        ("  Apache   Kafka :Expert", SkillCriterion("Apache Kafka", EXPERT)),
        ("ci:cd:beginner", SkillCriterion("ci:cd", BEGINNER)),
    ],
    ids=["with-level", "any-level", "spaces", "colon-in-name"],
)
def test_parses_a_skill_criterion(value: str, criterion: SkillCriterion) -> None:
    # When
    parsed = parse_skill_criterion(value)

    # Then
    assert parsed == criterion


@pytest.mark.parametrize(
    ("value", "reason"),
    [(":expert", "needs a skill name"), ("go:guru", "must be one of beginner")],
    ids=["no-name", "unknown-level"],
)
def test_rejects_a_malformed_skill_criterion(value: str, reason: str) -> None:
    # When / Then
    with pytest.raises(ValueError, match=reason):
        parse_skill_criterion(value)


def test_an_employee_query_turns_skills_into_criteria() -> None:
    # Given
    query = EmployeeQuery(skill=["kubernetes:advanced", "python"])

    # When
    criteria = query.skill_criteria

    # Then
    assert criteria == [
        SkillCriterion("kubernetes", ADVANCED),
        SkillCriterion("python", BEGINNER),
    ]


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"skill": ["go:guru"]}, "skill"),
        ({"skill": [f"skill{n}" for n in range(11)]}, "skill"),
        ({"sort": "salary"}, "sort"),
        ({"q": ""}, "q"),
    ],
    ids=["level", "too-many-skills", "sort", "empty-q"],
)
def test_rejects_an_invalid_employee_query(params: dict[str, Any], field: str) -> None:
    # When / Then
    with pytest.raises(ValidationError) as error:
        EmployeeQuery.model_validate(params)
    assert error.value.errors()[0]["loc"][0] == field


def test_an_employee_query_defaults_to_the_first_page_by_last_name() -> None:
    # When
    query = EmployeeQuery()

    # Then
    assert (query.page, query.page_size, query.sort, query.skill) == (1, 20, "last_name", [])


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}], ids=str)
def test_rejects_pages_outside_the_limits(params: dict[str, int]) -> None:
    # When / Then
    with pytest.raises(ValidationError):
        PageQuery.model_validate(params)


def test_rejects_a_skill_listed_twice() -> None:
    # Given
    skills = [{"skill_id": 1, "level": "expert"}, {"skill_id": 1, "level": "beginner"}]

    # When / Then
    with pytest.raises(ValidationError) as error:
        EmployeeSkillsWrite.model_validate({"skills": skills})
    assert reasons(error.value) == ["Value error, skills listed more than once: 1"]


def test_normalises_the_whitespace_of_a_skill_name() -> None:
    # When
    write = SkillWrite(name="  Apache   Kafka ")

    # Then
    assert write.name == "Apache Kafka"


@pytest.mark.parametrize("name", ["", "   ", "x" * 101], ids=["empty", "blank", "too-long"])
def test_rejects_an_invalid_skill_name(name: str) -> None:
    # When / Then
    with pytest.raises(ValidationError):
        SkillWrite(name=name)


def test_an_import_summary_counts_all_rows() -> None:
    # Given
    summary = ImportSummary(
        id=1,
        filename="employees.csv",
        status=ImportStatus.PARTIALLY_SUCCEEDED,
        rows_succeeded=11,
        rows_failed=2,
        rows_created=2,
        rows_updated=1,
        rows_unchanged=8,
        error=None,
        file_sha256="c0a7",
        created_at=datetime(2026, 11, 13, tzinfo=UTC),
    )

    # When
    body = summary.model_dump()

    # Then
    assert body["rows_total"] == 13
