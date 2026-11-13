from pathlib import Path
from typing import Any

from fastapi import status
from httpx import AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.api.imports import MAX_UPLOAD_BYTES
from app.models import Employee, EmployeeImport
from tests.factories import make_employee, persist

SAMPLES = Path(__file__).parents[2] / "samples"
URL = "/api/v1/imports"


async def upload(client: AsyncClient, content: bytes, filename: str = "employees.csv") -> Any:
    response = await client.post(URL, files={"file": (filename, content, "text/csv")})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def counts(record: dict[str, Any]) -> dict[str, int]:
    keys = ("rows_total", "rows_succeeded", "rows_failed", "rows_created", "rows_updated")
    return {key: record[key] for key in (*keys, "rows_unchanged")}


async def employee_count(session: AsyncSession) -> int | None:
    return await session.scalar(select(func.count()).select_from(Employee))


async def test_imports_the_sample_file_and_records_the_import(
    client: AsyncClient, session: AsyncSession
) -> None:
    record = await upload(client, (SAMPLES / "employees.csv").read_bytes())

    assert record["status"] == "succeeded"
    assert counts(record) == {
        "rows_total": 12,
        "rows_succeeded": 12,
        "rows_failed": 0,
        "rows_created": 12,
        "rows_updated": 0,
        "rows_unchanged": 0,
    }
    assert record["row_errors"] == []
    assert await employee_count(session) == 12

    stored = await session.get(EmployeeImport, record["id"])
    assert stored is not None
    assert (stored.filename, stored.rows_succeeded, stored.rows_failed) == ("employees.csv", 12, 0)


async def test_importing_the_same_file_again_changes_nothing(
    client: AsyncClient, session: AsyncSession
) -> None:
    content = (SAMPLES / "employees.csv").read_bytes()
    first = await upload(client, content)

    second = await upload(client, content)

    assert second["status"] == "succeeded"
    assert (second["rows_created"], second["rows_unchanged"]) == (0, 12)
    assert second["file_sha256"] == first["file_sha256"]
    assert await employee_count(session) == 12
    assert await session.scalar(select(func.count()).select_from(EmployeeImport)) == 2


async def test_updates_employees_whose_data_changed(
    client: AsyncClient, session: AsyncSession
) -> None:
    await persist(
        session,
        make_employee(
            employee_number="E-1001",
            first_name="Anna",
            last_name="Schmidt",
            email="anna.schmidt@example.com",
            job_title="Software Engineer",
        ),
    )

    record = await upload(client, (SAMPLES / "employees.csv").read_bytes())

    assert (record["rows_created"], record["rows_updated"]) == (11, 1)
    employee = await session.scalar(select(Employee).where(Employee.employee_number == "E-1001"))
    assert employee is not None
    assert employee.job_title == "Senior Software Engineer"


async def test_imports_valid_rows_and_reports_the_others(
    client: AsyncClient, session: AsyncSession
) -> None:
    await persist(
        session,
        make_employee(employee_number="E-1001", email="anna.schmidt@example.com"),
    )

    record = await upload(client, (SAMPLES / "employees-with-errors.csv").read_bytes())

    assert record["status"] == "partially_succeeded"
    assert (record["rows_succeeded"], record["rows_failed"]) == (2, 7)
    errors = {error["row"]: (error["field"], error["message"]) for error in record["row_errors"]}
    assert list(errors) == [3, 4, 5, 6, 7, 8, 9]
    assert errors[3] == ("first_name", "is required")
    assert errors[6] == ("employee_number", "Duplicate employee_number, already in row 2")
    assert errors[7] == ("email", "Duplicate email, already in row 2")
    assert errors[8] == ("email", "Email belongs to employee E-1001")
    imported = await session.scalars(
        select(Employee.employee_number).where(Employee.employee_number.like("E-3%"))
    )
    assert sorted(imported) == ["E-3001", "E-3008"]


async def test_imports_a_german_excel_export(client: AsyncClient, session: AsyncSession) -> None:
    record = await upload(client, (SAMPLES / "employees-excel-de.csv").read_bytes())

    assert (record["status"], record["rows_created"]) == ("succeeded", 4)
    employee = await session.scalar(select(Employee).where(Employee.employee_number == "E-2001"))
    assert employee is not None
    assert (employee.first_name, employee.last_name, employee.location) == (
        "Jürgen",
        "Weiß",
        "München",
    )


async def test_records_a_rejected_file_as_a_failed_import(
    client: AsyncClient, session: AsyncSession
) -> None:
    record = await upload(client, b"employee_number,first_name\nE-1,Anna\n", "wrong.csv")

    assert record["status"] == "failed"
    assert record["error"] == "Missing required columns: last_name, email"
    assert (record["rows_total"], record["row_errors"]) == (0, [])
    stored = await session.get(EmployeeImport, record["id"])
    assert stored is not None
    assert stored.error == record["error"]


async def test_rejects_files_larger_than_the_limit(
    client: AsyncClient, session: AsyncSession
) -> None:
    content = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = await client.post(URL, files={"file": ("big.csv", content, "text/csv")})

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.headers["content-type"] == "application/problem+json"
    assert await session.scalar(select(func.count()).select_from(EmployeeImport)) == 0


async def test_requires_a_file(client: AsyncClient) -> None:
    response = await client.post(URL)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert [error["name"] for error in response.json()["errors"]] == ["file"]


async def test_lists_imports_newest_first_and_gets_one(client: AsyncClient) -> None:
    first = await upload(client, (SAMPLES / "employees.csv").read_bytes(), "first.csv")
    second = await upload(
        client, (SAMPLES / "employees-with-errors.csv").read_bytes(), "second.csv"
    )

    page = (await client.get(URL, params={"page_size": 1})).json()
    detail = (await client.get(f"{URL}/{first['id']}")).json()

    assert (page["total"], [item["filename"] for item in page["items"]]) == (2, ["second.csv"])
    assert "row_errors" not in page["items"][0]
    assert detail == first
    assert second["id"] > first["id"]


async def test_unknown_import_is_a_404_problem(client: AsyncClient) -> None:
    response = await client.get(f"{URL}/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Import 999999 does not exist"


async def test_looks_up_existing_employees_with_one_parameter_regardless_of_row_count(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    # asyncpg allows 32767 parameters per statement, so a parameter per row would fail
    # for large files.
    lookups: list[int] = []

    def count_parameters(*args: Any) -> None:
        statement, parameters = args[2], args[3]
        if statement.lstrip().startswith("SELECT") and "FROM employee " in statement:
            lookups.append(len(parameters))

    rows = "".join(f"E-{n},Anna,Schmidt,anna.{n}@example.com\n" for n in range(500))
    content = f"employee_number,first_name,last_name,email\n{rows}".encode()
    event.listen(engine.sync_engine, "before_cursor_execute", count_parameters)
    try:
        record = await upload(client, content)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_parameters)

    assert record["rows_created"] == 500
    assert lookups == [1, 1]
