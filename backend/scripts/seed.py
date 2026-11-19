"""Fill a database without employees with fictional demo employees and their skills:
`uv run python -m scripts.seed`. Skills the catalogue already has are used, the others
added."""

from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Department,
    Employee,
    EmployeeSkill,
    Location,
    ProficiencyLevel,
    Skill,
    name_key,
)

BEG, INT, ADV, EXP = (
    ProficiencyLevel.BEGINNER,
    ProficiencyLevel.INTERMEDIATE,
    ProficiencyLevel.ADVANCED,
    ProficiencyLevel.EXPERT,
)

EMPLOYEES = [
    ("E-1001", "Anna", "Schmidt", "Digital Industries", "Senior Software Engineer", "Munich",
     date(2019, 4, 1), {"Python": EXP, "Kubernetes": ADV, "PostgreSQL": ADV}),
    ("E-1002", "Lukas", "Müller", "Digital Industries", "Software Engineer", "Munich",
     date(2021, 9, 15), {"Python": INT, "Go": BEG}),
    ("E-1003", "Mia", "Weber", "Smart Infrastructure", "Frontend Developer", "Zug",
     date(2020, 1, 6), {"Angular": EXP, "TypeScript": EXP}),
    ("E-1004", "Jonas", "Fischer", "Smart Infrastructure", "DevOps Engineer", "Zug",
     date(2018, 6, 1), {"Kubernetes": EXP, "Terraform": ADV, "AWS": ADV, "Go": INT}),
    ("E-1005", "Lea", "Wagner", "Mobility", "Cloud Architect", "Berlin",
     date(2016, 3, 14), {"AWS": EXP, "Terraform": EXP, "Kubernetes": INT}),
    ("E-1006", "Felix", "Becker", "Mobility", "Backend Developer", "Berlin",
     date(2022, 2, 1), {"Python": ADV, "PostgreSQL": INT}),
    ("E-1007", "Sophie", "Hoffmann", "Healthineers", "Full-Stack Developer", "Erlangen",
     date(2023, 5, 2), {"TypeScript": ADV, "Angular": INT, "Python": BEG}),
    ("E-1008", "Noah", "Schulz", "Healthineers", "Data Engineer", "Erlangen",
     date(2017, 11, 20), {"Python": EXP, "PostgreSQL": EXP, "AWS": INT}),
    ("E-1009", "Emma", "Koch", "Digital Industries", "QA Engineer", "Nuremberg",
     date(2024, 1, 8), {"TypeScript": BEG}),
    ("E-1010", "Paul", "Richter", "Smart Infrastructure", "Working Student", None,
     None, {}),
]  # fmt: skip


def seed() -> None:
    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine) as session, session.begin():
            _insert(session)
    finally:
        engine.dispose()


def _insert(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Employee)):
        print("Database already has employees, nothing to do.")
        return

    needed = {name for *_, levels in EMPLOYEES for name in levels}
    catalogue = {
        skill.key: skill
        for skill in session.scalars(
            select(Skill).where(Skill.key.in_([name_key(name) for name in needed]))
        )
    }
    skills = {name: catalogue.get(name_key(name)) or Skill(name=name) for name in needed}
    departments = {row[3]: Department(name=row[3]) for row in EMPLOYEES}
    locations = {row[5]: Location(name=row[5]) for row in EMPLOYEES if row[5]}
    for number, first, last, department, title, location, hired, levels in EMPLOYEES:
        employee = Employee(
            employee_number=number,
            first_name=first,
            last_name=last,
            email=f"{first}.{last}@siemens.com".lower().replace("ü", "ue"),
            department=departments[department],
            job_title=title,
            location=locations[location] if location else None,
            hire_date=hired,
            skills=[EmployeeSkill(skill=skills[s], level=lvl) for s, lvl in levels.items()],
        )
        session.add(employee)
    print(f"Seeded {len(EMPLOYEES)} employees, adding {len(needed) - len(catalogue)} skills.")


if __name__ == "__main__":
    seed()
