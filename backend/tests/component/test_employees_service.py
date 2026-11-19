from unittest.mock import MagicMock

import pytest

from app.models import Employee, ProficiencyLevel
from app.schemas import EmployeeQuery, SkillLevelWrite
from app.services.employees_service import (
    EmployeeChangedError,
    EmployeeNotFoundError,
    UnknownSkillsError,
    delete_employee,
    etag,
    get_employee,
    list_employees,
    replace_skills,
)
from tests.component.conftest import sql
from tests.factories import make_employee

ADVANCED, EXPERT = ProficiencyLevel.ADVANCED, ProficiencyLevel.EXPERT


def listed_sql(session: MagicMock, query: EmployeeQuery) -> str:
    session.scalar.return_value = 0
    list_employees(session, query)
    return sql(session.scalars.call_args.args[0])


def test_lists_a_page_of_employees_and_counts_all_matches(session: MagicMock) -> None:
    # Given
    anna = make_employee()
    session.scalar.return_value = 41
    session.scalars.return_value.all.return_value = [anna]

    # When
    employees, total = list_employees(session, EmployeeQuery(page=3, page_size=20))

    # Then
    assert (employees, total) == ([anna], 41)
    assert "LIMIT 20 OFFSET 40" in sql(session.scalars.call_args.args[0])


def test_counts_no_matches_as_zero(session: MagicMock) -> None:
    # Given
    session.scalar.return_value = None

    # When
    _, total = list_employees(session, EmployeeQuery())

    # Then
    assert total == 0


def test_sorts_descending_with_missing_values_last_and_a_stable_tie_break(
    session: MagicMock,
) -> None:
    # When
    query = listed_sql(session, EmployeeQuery(sort="-department"))

    # Then
    assert "ORDER BY department.name DESC NULLS LAST, employee.id" in query


def test_searches_name_email_and_number_with_wildcards_escaped(session: MagicMock) -> None:
    # When
    query = listed_sql(session, EmployeeQuery(q="50%"))

    # Then
    for column in ("concat(employee.first_name, ' ', employee.last_name)", "employee.email"):
        assert f"{column} ILIKE '%' || '50/%' || '%' ESCAPE '/'" in query
    assert "employee.employee_number ILIKE" in query


def test_filters_by_any_of_the_departments_and_locations_by_their_keys(
    session: MagicMock,
) -> None:
    # When
    query = listed_sql(
        session, EmployeeQuery(department=["Digital Industries", "mobility"], location=["Zug"])
    )

    # Then
    assert "department.key IN ('digitalindustries', 'mobility')" in query
    assert ") AND (EXISTS (SELECT 1 FROM location" in query
    assert "location.key IN ('zug')" in query


def test_a_skill_criterion_matches_the_catalogue_key_at_the_level_or_higher(
    session: MagicMock,
) -> None:
    # When
    query = listed_sql(session, EmployeeQuery(skill=["Node.js:advanced", "python"]))

    # Then
    assert "skill.key = 'nodejs' AND employee_skill.level >= 3" in query
    assert "skill.key = 'python' AND employee_skill.level >= 1" in query


def test_gets_an_employee_with_their_skills(session: MagicMock) -> None:
    # Given
    anna = make_employee()
    session.get.return_value = anna

    # When
    employee = get_employee(session, 7)

    # Then
    assert employee is anna
    model, employee_id = session.get.call_args.args
    assert (model, employee_id) == (Employee, 7)
    assert session.get.call_args.kwargs["options"]


def loaded(session: MagicMock) -> str:
    """The employee as the request finds it, locked; returns its version."""
    employee = make_employee(id=1)
    session.scalar.return_value = employee
    session.get.return_value = make_employee(id=1)
    return etag(employee)


def test_replacing_skills_locks_the_employee_then_upserts_only_changed_levels(
    session: MagicMock,
) -> None:
    # Given
    version = loaded(session)
    session.scalars.return_value = [7, 8]
    skills = [
        SkillLevelWrite(skill_id=7, level=ADVANCED),
        SkillLevelWrite(skill_id=8, level=EXPERT),
    ]

    # When
    stored = replace_skills(session, 1, skills, version)

    # Then
    assert sql(session.scalar.call_args.args[0]).endswith("FOR UPDATE OF employee")
    delete, upsert = (sql(call.args[0]) for call in session.execute.call_args_list)
    assert "employee_skill.employee_id = 1 AND (employee_skill.skill_id NOT IN (7, 8))" in delete
    assert "VALUES (1, 7, 3), (1, 8, 4)" in upsert
    assert "DO UPDATE SET level = excluded.level, updated_at = now()" in upsert
    assert "WHERE employee_skill.level != excluded.level" in upsert
    session.commit.assert_called_once()
    assert stored is session.get.return_value
    assert session.get.call_args.kwargs["populate_existing"] is True


def test_replacing_with_no_skills_only_deletes(session: MagicMock) -> None:
    # Given
    version = loaded(session)
    session.scalars.return_value = []

    # When
    replace_skills(session, 1, [], version)

    # Then
    [delete] = session.execute.call_args_list
    assert sql(delete.args[0]).startswith("DELETE FROM employee_skill")
    session.commit.assert_called_once()


def test_refuses_skills_missing_from_the_catalogue_before_changing_anything(
    session: MagicMock,
) -> None:
    # Given
    version = loaded(session)
    session.scalars.return_value = [7]
    skills = [
        SkillLevelWrite(skill_id=7, level=EXPERT),
        SkillLevelWrite(skill_id=999, level=EXPERT),
    ]

    # When / Then
    with pytest.raises(UnknownSkillsError, match="Unknown skills: 999"):
        replace_skills(session, 1, skills, version)
    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_refuses_to_replace_the_skills_of_a_version_that_is_out_of_date(
    session: MagicMock,
) -> None:
    # Given
    loaded(session)

    # When / Then
    with pytest.raises(EmployeeChangedError, match="changed since it was loaded"):
        replace_skills(session, 1, [], '"an-older-version"')
    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_replacing_the_skills_of_an_unknown_employee_changes_nothing(session: MagicMock) -> None:
    # Given
    session.scalar.return_value = None

    # When / Then
    with pytest.raises(EmployeeNotFoundError, match="Employee 1 does not exist"):
        replace_skills(session, 1, [], '"v1"')
    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_deletes_the_employee_in_one_statement_and_logs_who_it_was(
    session: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    # Given
    session.scalar.return_value = "E-1001"
    caplog.set_level("INFO", logger="app")

    # When
    delete_employee(session, 1)

    # Then
    assert sql(session.scalar.call_args.args[0]) == (
        "DELETE FROM employee WHERE employee.id = 1 RETURNING employee.employee_number"
    )
    session.commit.assert_called_once()
    [entry] = [r for r in caplog.records if r.name == "app.services.employees_service"]
    assert entry.getMessage() == "Deleted employee E-1001"


def test_deleting_an_unknown_employee_commits_nothing(session: MagicMock) -> None:
    # Given
    session.scalar.return_value = None

    # When / Then
    with pytest.raises(EmployeeNotFoundError, match="Employee 1 does not exist"):
        delete_employee(session, 1)
    session.commit.assert_not_called()
