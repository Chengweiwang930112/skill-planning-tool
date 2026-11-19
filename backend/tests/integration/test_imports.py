from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, select
from sqlalchemy.orm import Session

from app.models import Employee, EmployeeImport
from tests.factories import make_employee, persist
from tests.integration.conftest import SAMPLES

URL = "/api/v1/imports"


def upload(client: TestClient, content: bytes, filename: str = "employees.csv") -> Any:
    response = client.post(URL, files={"file": (filename, content, "text/csv")})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def count(session: Session, model: type[object]) -> int | None:
    return session.scalar(select(func.count()).select_from(model))


def test_imports_the_sample_file_and_records_the_import(
    client: TestClient, session: Session
) -> None:
    # When
    record = upload(client, sample("employees.csv"))

    # Then
    assert record["status"] == "succeeded"
    assert (record["rows_total"], record["rows_created"], record["rows_failed"]) == (12, 12, 0)
    assert count(session, Employee) == 12
    stored = session.get(EmployeeImport, record["id"])
    assert stored is not None
    assert (stored.filename, stored.rows_succeeded) == ("employees.csv", 12)


def test_importing_the_same_file_again_changes_nothing(
    client: TestClient, session: Session
) -> None:
    # Given
    upload(client, sample("employees.csv"))

    # When
    second = upload(client, sample("employees.csv"))

    # Then
    assert (second["rows_created"], second["rows_unchanged"]) == (0, 12)
    assert count(session, Employee) == 12
    assert count(session, EmployeeImport) == 2


def test_updates_employees_whose_data_changed(client: TestClient, session: Session) -> None:
    # Given
    persist(
        session,
        make_employee(
            employee_number="E-1001",
            first_name="Anna",
            last_name="Schmidt",
            email="anna.schmidt@example.com",
            job_title="Software Engineer",
        ),
    )

    # When
    record = upload(client, sample("employees.csv"))

    # Then
    assert (record["rows_created"], record["rows_updated"]) == (11, 1)
    employee = session.scalar(select(Employee).where(Employee.employee_number == "E-1001"))
    assert employee is not None
    assert employee.job_title == "Senior Software Engineer"


def test_imports_valid_rows_and_reports_the_others(client: TestClient, session: Session) -> None:
    # Given
    persist(session, make_employee(employee_number="E-1001", email="anna.schmidt@example.com"))

    # When
    record = upload(client, sample("employees-with-errors.csv"))

    # Then
    assert record["status"] == "partially_succeeded"
    assert (record["rows_succeeded"], record["rows_failed"]) == (2, 7)
    errors = {error["row"]: (error["field"], error["message"]) for error in record["row_errors"]}
    assert list(errors) == [3, 4, 5, 6, 7, 8, 9]
    assert errors[8] == ("email", "Email belongs to employee E-1001")
    imported = session.scalars(
        select(Employee.employee_number).where(Employee.employee_number.like("E-3%"))
    )
    assert sorted(imported) == ["E-3001", "E-3008"]


def test_imports_a_german_excel_export(client: TestClient, session: Session) -> None:
    # When
    record = upload(client, sample("employees-excel-de.csv"))

    # Then
    assert (record["status"], record["rows_created"]) == ("succeeded", 4)
    employee = session.scalar(select(Employee).where(Employee.employee_number == "E-2001"))
    assert employee is not None
    assert employee.location is not None
    assert (employee.first_name, employee.last_name, employee.location.name) == (
        "Jürgen",
        "Weiß",
        "München",
    )


def test_records_a_rejected_file_as_a_failed_import(client: TestClient, session: Session) -> None:
    # When
    record = upload(client, b"employee_number,first_name\nE-1,Anna\n", "wrong.csv")

    # Then
    assert record["status"] == "failed"
    assert record["error"] == "Missing required columns: last_name, email"
    stored = session.get(EmployeeImport, record["id"])
    assert stored is not None
    assert stored.error == record["error"]
    assert count(session, Employee) == 0


def test_lists_imports_newest_first_and_gets_one(client: TestClient) -> None:
    # Given
    first = upload(client, sample("employees.csv"), "first.csv")
    upload(client, sample("employees-with-errors.csv"), "second.csv")

    # When
    page = client.get(URL, params={"page_size": 1}).json()
    detail = client.get(f"{URL}/{first['id']}").json()

    # Then
    assert (page["total"], [item["filename"] for item in page["items"]]) == (2, ["second.csv"])
    assert detail == first


def test_looks_up_existing_employees_with_one_parameter_regardless_of_row_count(
    client: TestClient, engine: Engine
) -> None:
    # Given
    # PostgreSQL allows 65535 parameters per statement, so a parameter per row would
    # fail for large files.
    lookups: list[int] = []

    def count_parameters(*args: Any) -> None:
        statement, parameters = args[2], args[3]
        if statement.lstrip().startswith("SELECT") and "FROM employee " in statement:
            lookups.append(len(parameters))

    rows = "".join(f"E-{n},Anna,Schmidt,anna.{n}@example.com\n" for n in range(500))
    content = f"employee_number,first_name,last_name,email\n{rows}".encode()
    event.listen(engine, "before_cursor_execute", count_parameters)

    # When
    try:
        record = upload(client, content)
    finally:
        event.remove(engine, "before_cursor_execute", count_parameters)

    # Then
    assert record["rows_created"] == 500
    assert lookups == [1, 1]
