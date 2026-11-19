from datetime import UTC, datetime
from itertools import count
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Department,
    Employee,
    EmployeeImport,
    EmployeeSkill,
    ImportStatus,
    Location,
    ProficiencyLevel,
    Skill,
)

_sequence = count(1)


def make_employee(
    skills: dict[Skill, ProficiencyLevel] | None = None, **overrides: Any
) -> Employee:
    n = next(_sequence)
    fields: dict[str, Any] = {
        "employee_number": f"E-{n:04d}",
        "first_name": "Anna",
        "last_name": f"Schmidt{n}",
        "email": f"employee{n}@example.com",
    }
    fields |= overrides
    # A name makes a new department or location; to share one, pass the same object.
    for field, model in (("department", Department), ("location", Location)):
        if isinstance(fields.get(field), str):
            fields[field] = model(name=fields[field])
    employee = Employee(**fields)
    employee.skills = [
        EmployeeSkill(skill=skill, level=level) for skill, level in (skills or {}).items()
    ]
    return employee


def make_import(**overrides: Any) -> EmployeeImport:
    fields: dict[str, Any] = {
        "id": 3,
        "filename": "employees.csv",
        "status": ImportStatus.PARTIALLY_SUCCEEDED,
        "rows_succeeded": 2,
        "rows_failed": 1,
        "rows_created": 1,
        "rows_updated": 1,
        "rows_unchanged": 0,
        "error": None,
        "created_at": datetime(2026, 11, 13, 9, 30, tzinfo=UTC),
        "row_errors": [{"row": 3, "field": "first_name", "message": "is required"}],
    }
    return EmployeeImport(**(fields | overrides))


def persist(session: Session, *objects: object) -> None:
    """Flush and detach, so the code under test loads from the database like a real request."""
    session.add_all(objects)
    session.flush()
    session.expunge_all()
