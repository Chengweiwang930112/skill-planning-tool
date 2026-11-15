from unittest.mock import MagicMock

import pytest

from app.models import Employee, EmployeeImport, ImportStatus
from app.services.employee_import import IMPORT_LOCK_KEY, import_employees
from tests.component.conftest import DIALECT
from tests.factories import make_employee

HEADER = "employee_number,first_name,last_name,email,job_title"


def given_the_database_has(
    session: MagicMock,
    employees: list[Employee] | None = None,
    email_owners: list[tuple[str, str]] | None = None,
) -> None:
    session.scalars.return_value = employees or []
    # The first statement takes the lock, the second looks up who owns the emails.
    session.execute.side_effect = [None, email_owners or []]


def added[T](session: MagicMock, model: type[T]) -> list[T]:
    return [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], model)]


def test_takes_the_import_lock_before_anything_else(session: MagicMock) -> None:
    # Given
    given_the_database_has(session)

    # When
    import_employees(session, "team.csv", f"{HEADER}\nE-1,Anna,Schmidt,a@example.com,\n".encode())

    # Then
    statement, parameters = session.execute.call_args_list[0].args
    assert "pg_advisory_xact_lock" in str(statement)
    assert parameters == {"key": IMPORT_LOCK_KEY}


def test_creates_new_employees_updates_changed_ones_and_counts_unchanged_ones(
    session: MagicMock,
) -> None:
    # Given
    unchanged = make_employee(
        employee_number="E-2", first_name="Jonas", last_name="Fischer", email="j@example.com"
    )
    changed = make_employee(
        employee_number="E-3",
        first_name="Mia",
        last_name="Weber",
        email="m@example.com",
        job_title="Developer",
    )
    given_the_database_has(session, [unchanged, changed])
    content = (
        f"{HEADER}\nE-1,Anna,Schmidt,a@example.com,\nE-2,Jonas,Fischer,j@example.com,\n"
        "E-3,Mia,Weber,m@example.com,Architect\n"
    ).encode()

    # When
    record = import_employees(session, "team.csv", content)

    # Then
    assert (record.rows_created, record.rows_updated, record.rows_unchanged) == (1, 1, 1)
    assert record.status is ImportStatus.SUCCEEDED
    assert [e.employee_number for e in added(session, Employee)] == ["E-1"]
    assert changed.job_title == "Architect"
    session.commit.assert_called_once()


def test_looks_up_existing_employees_with_one_array_parameter(session: MagicMock) -> None:
    # Given
    given_the_database_has(session)
    rows = "".join(f"E-{n},Anna,Schmidt,a{n}@example.com,\n" for n in range(3))

    # When
    import_employees(session, "team.csv", f"{HEADER}\n{rows}".encode())

    # Then
    lookup = session.scalars.call_args.args[0].compile(dialect=DIALECT)
    assert "employee.employee_number = ANY (%(param_1)s::VARCHAR[])" in str(lookup)
    assert lookup.params["param_1"] == ["E-0", "E-1", "E-2"]


def test_refuses_an_email_that_belongs_to_another_employee(session: MagicMock) -> None:
    # Given
    given_the_database_has(session, email_owners=[("a@example.com", "E-9")])
    content = f"{HEADER}\nE-1,Anna,Schmidt,a@example.com,\nE-2,Jonas,Fischer,j@example.com,\n"

    # When
    record = import_employees(session, "team.csv", content.encode())

    # Then
    assert record.row_errors == [
        {"row": 2, "field": "email", "message": "Email belongs to employee E-9"}
    ]
    assert (record.status, record.rows_created) == (ImportStatus.PARTIALLY_SUCCEEDED, 1)


def test_keeps_the_first_of_two_rows_for_the_same_employee(session: MagicMock) -> None:
    # Given
    given_the_database_has(session)
    content = f"{HEADER}\nE-1,Anna,Schmidt,a@example.com,\nE-1,Anna,Schmidt,b@example.com,\n"

    # When
    record = import_employees(session, "team.csv", content.encode())

    # Then
    assert record.rows_created == 1
    assert record.row_errors == [
        {
            "row": 3,
            "field": "employee_number",
            "message": "Duplicate employee_number, already in row 2",
        }
    ]


@pytest.mark.parametrize(
    ("content", "error"),
    [
        (b"", "The file is empty"),
        (b"employee_number,first_name\nE-1,Anna\n", "Missing required columns: last_name, email"),
    ],
    ids=["empty", "missing-columns"],
)
def test_records_an_unusable_file_as_a_failed_import_without_lookups(
    session: MagicMock, content: bytes, error: str
) -> None:
    # Given
    given_the_database_has(session)

    # When
    record = import_employees(session, "wrong.csv", content)

    # Then
    assert (record.status, record.error, record.rows_failed) == (ImportStatus.FAILED, error, 0)
    assert added(session, EmployeeImport) == [record]
    session.scalars.assert_not_called()
    session.commit.assert_called_once()


def test_a_file_whose_rows_all_fail_is_a_failed_import(session: MagicMock) -> None:
    # Given
    given_the_database_has(session)
    content = f"{HEADER}\nE-1,,Schmidt,a@example.com,\nE-2,Jonas,,j@example.com,\n"

    # When
    record = import_employees(session, "team.csv", content.encode())

    # Then
    assert (record.status, record.rows_succeeded, record.rows_failed) == (
        ImportStatus.FAILED,
        0,
        2,
    )
