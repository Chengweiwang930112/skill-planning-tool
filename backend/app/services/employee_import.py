import hashlib
from collections.abc import Sequence
from dataclasses import asdict

from sqlalchemy import String, any_, func, literal, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, EmployeeImport, ImportStatus
from app.services.csv_parsing import CsvFileError, ParsedRow, RowError, parse_employee_csv

# Imports are serialised: two concurrent uploads creating the same employee number
# would otherwise race between the existence check and the insert.
IMPORT_LOCK_KEY = 4_201_001


async def import_employees(session: AsyncSession, filename: str, content: bytes) -> EmployeeImport:
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": IMPORT_LOCK_KEY})
    record = EmployeeImport(
        filename=filename,
        file_sha256=hashlib.sha256(content).hexdigest(),
        rows_created=0,
        rows_updated=0,
        rows_unchanged=0,
        row_errors=[],
    )
    try:
        parsed = parse_employee_csv(content)
    except CsvFileError as exc:
        record.error = str(exc)
        errors: list[RowError] = []
    else:
        errors = list(parsed.errors)
        await _upsert(session, _without_duplicates(parsed.rows, errors), errors, record)

    record.rows_succeeded = record.rows_created + record.rows_updated + record.rows_unchanged
    record.rows_failed = len({error.row for error in errors})
    record.row_errors = [asdict(error) for error in sorted(errors, key=lambda e: e.row)]
    record.status = (
        ImportStatus.FAILED
        if record.rows_succeeded == 0
        else ImportStatus.PARTIALLY_SUCCEEDED
        if record.rows_failed
        else ImportStatus.SUCCEEDED
    )
    session.add(record)
    await session.commit()
    return record


def _without_duplicates(rows: list[ParsedRow], errors: list[RowError]) -> list[ParsedRow]:
    first_number: dict[str, int] = {}
    first_email: dict[str, int] = {}
    unique = []
    for parsed in rows:
        number, email = parsed.employee.employee_number, parsed.employee.email
        if number in first_number:
            message = f"Duplicate employee_number, already in row {first_number[number]}"
            errors.append(RowError(parsed.row, "employee_number", message))
        elif email in first_email:
            message = f"Duplicate email, already in row {first_email[email]}"
            errors.append(RowError(parsed.row, "email", message))
        else:
            first_number[number], first_email[email] = parsed.row, parsed.row
            unique.append(parsed)
    return unique


async def _upsert(
    session: AsyncSession, rows: list[ParsedRow], errors: list[RowError], record: EmployeeImport
) -> None:
    # One array parameter instead of IN (...): asyncpg allows at most 32767 parameters.
    numbers = literal([parsed.employee.employee_number for parsed in rows], ARRAY(String))
    emails = literal([parsed.employee.email for parsed in rows], ARRAY(String))
    existing = {
        employee.employee_number: employee
        for employee in await session.scalars(
            select(Employee).where(Employee.employee_number == any_(numbers))
        )
    }
    email_owners = {
        email: number
        for email, number in await session.execute(
            select(Employee.email, Employee.employee_number).where(Employee.email == any_(emails))
        )
    }

    for parsed in rows:
        values = parsed.employee.model_dump()
        owner = email_owners.get(parsed.employee.email)
        if owner is not None and owner != parsed.employee.employee_number:
            errors.append(RowError(parsed.row, "email", f"Email belongs to employee {owner}"))
            continue

        employee = existing.get(parsed.employee.employee_number)
        if employee is None:
            session.add(Employee(**values))
            record.rows_created += 1
        elif all(getattr(employee, name) == value for name, value in values.items()):
            record.rows_unchanged += 1
        else:
            for name, value in values.items():
                setattr(employee, name, value)
            record.rows_updated += 1


async def list_imports(
    session: AsyncSession, page: int, page_size: int
) -> tuple[Sequence[EmployeeImport], int]:
    total = await session.scalar(select(func.count()).select_from(EmployeeImport))
    imports = await session.scalars(
        select(EmployeeImport)
        .order_by(EmployeeImport.created_at.desc(), EmployeeImport.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return imports.all(), total or 0


async def get_import(session: AsyncSession, import_id: int) -> EmployeeImport | None:
    return await session.get(EmployeeImport, import_id)
