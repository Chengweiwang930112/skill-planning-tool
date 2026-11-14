from itertools import count
from typing import Any

from sqlalchemy.orm import Session

from app.models import Employee, EmployeeSkill, ProficiencyLevel, Skill

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
    employee = Employee(**(fields | overrides))
    employee.skills = [
        EmployeeSkill(skill=skill, level=level) for skill, level in (skills or {}).items()
    ]
    return employee


def persist(session: Session, *objects: object) -> None:
    """Flush and detach, so the code under test loads from the database like a real request."""
    session.add_all(objects)
    session.flush()
    session.expunge_all()
