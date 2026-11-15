from unittest.mock import MagicMock

import pytest

from app.models import Employee, ProficiencyLevel
from app.schemas import EmployeeQuery, SkillLevelWrite
from app.services.employees import (
    UnknownSkillsError,
    assign_skill,
    get_employee,
    list_employees,
    remove_skill,
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
    assert "ORDER BY employee.department DESC NULLS LAST, employee.id" in query


def test_searches_name_email_and_number_with_wildcards_escaped(session: MagicMock) -> None:
    # When
    query = listed_sql(session, EmployeeQuery(q="50%"))

    # Then
    for column in ("concat(employee.first_name, ' ', employee.last_name)", "employee.email"):
        assert f"{column} ILIKE '%' || '50/%' || '%' ESCAPE '/'" in query
    assert "employee.employee_number ILIKE" in query


def test_filters_by_department_ignoring_case(session: MagicMock) -> None:
    # When
    query = listed_sql(session, EmployeeQuery(department="Mobility"))

    # Then
    assert "lower(employee.department) = 'mobility'" in query


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


@pytest.mark.parametrize("inserted", [True, False], ids=["new", "changed"])
def test_assigning_a_skill_is_one_upsert_that_tells_new_from_changed(
    session: MagicMock, inserted: bool
) -> None:
    # Given
    session.scalar.return_value = inserted

    # When
    created = assign_skill(session, 1, 7, EXPERT)

    # Then
    assert created is inserted
    statement = sql(session.scalar.call_args.args[0])
    assert "ON CONFLICT (employee_id, skill_id) DO UPDATE SET level" in statement
    assert "RETURNING xmax = 0" in statement
    session.commit.assert_called_once()


def test_removing_a_skill_deletes_only_that_assignment(session: MagicMock) -> None:
    # When
    remove_skill(session, 1, 7)

    # Then
    statement = sql(session.execute.call_args.args[0])
    assert statement == (
        "DELETE FROM employee_skill "
        "WHERE employee_skill.employee_id = 1 AND employee_skill.skill_id = 7"
    )
    session.commit.assert_called_once()


def test_replacing_skills_removes_the_others_and_upserts_only_changed_levels(
    session: MagicMock,
) -> None:
    # Given
    session.scalars.return_value = [7, 8]
    skills = [
        SkillLevelWrite(skill_id=7, level=ADVANCED),
        SkillLevelWrite(skill_id=8, level=EXPERT),
    ]

    # When
    replace_skills(session, 1, skills)

    # Then
    delete, upsert = (sql(call.args[0]) for call in session.execute.call_args_list)
    assert "employee_skill.employee_id = 1 AND (employee_skill.skill_id NOT IN (7, 8))" in delete
    assert "VALUES (1, 7, 3), (1, 8, 4)" in upsert
    assert "DO UPDATE SET level = excluded.level, updated_at = now()" in upsert
    assert "WHERE employee_skill.level != excluded.level" in upsert
    session.commit.assert_called_once()


def test_replacing_with_no_skills_only_deletes(session: MagicMock) -> None:
    # Given
    session.scalars.return_value = []

    # When
    replace_skills(session, 1, [])

    # Then
    [delete] = session.execute.call_args_list
    assert sql(delete.args[0]).startswith("DELETE FROM employee_skill")
    session.commit.assert_called_once()


def test_refuses_skills_missing_from_the_catalogue_before_changing_anything(
    session: MagicMock,
) -> None:
    # Given
    session.scalars.return_value = [7]
    skills = [
        SkillLevelWrite(skill_id=7, level=EXPERT),
        SkillLevelWrite(skill_id=999, level=EXPERT),
    ]

    # When / Then
    with pytest.raises(UnknownSkillsError, match="Unknown skills: 999"):
        replace_skills(session, 1, skills)
    session.execute.assert_not_called()
    session.commit.assert_not_called()
