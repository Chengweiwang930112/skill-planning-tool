import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Employee, EmployeeSkill, ProficiencyLevel, Skill
from tests.factories import make_employee


def test_migrations_match_the_models(alembic_config: Config, migrated_database: None) -> None:
    command.check(alembic_config)


def test_proficiency_levels_are_ordered() -> None:
    assert (
        ProficiencyLevel.BEGINNER
        < ProficiencyLevel.INTERMEDIATE
        < ProficiencyLevel.ADVANCED
        < ProficiencyLevel.EXPERT
    )


def test_assigned_skill_round_trips_with_its_level(session: Session) -> None:
    employee = make_employee()
    employee.skills.append(
        EmployeeSkill(skill=Skill(name="Kubernetes"), level=ProficiencyLevel.ADVANCED)
    )
    session.add(employee)
    session.flush()
    session.expunge_all()

    loaded = session.scalar(select(Employee).options(selectinload(Employee.skills)))

    assert loaded is not None
    assert [(s.skill.name, s.level) for s in loaded.skills] == [
        ("Kubernetes", ProficiencyLevel.ADVANCED)
    ]
    assert loaded.skills[0].level is ProficiencyLevel.ADVANCED


@pytest.mark.parametrize(
    "duplicate",
    [
        make_employee(employee_number="E-1001"),
        make_employee(email="anna.schmidt@example.com"),
    ],
    ids=["employee_number", "email"],
)
def test_employee_identifiers_are_unique(session: Session, duplicate: Employee) -> None:
    session.add(make_employee(employee_number="E-1001", email="anna.schmidt@example.com"))
    session.flush()

    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()


def test_skill_names_are_unique_regardless_of_case(session: Session) -> None:
    session.add(Skill(name="Kubernetes"))
    session.flush()

    session.add(Skill(name="kubernetes"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_database_rejects_levels_outside_the_scale(session: Session) -> None:
    employee, skill = make_employee(), Skill(name="Python")
    session.add_all([employee, skill])
    session.flush()

    with pytest.raises(IntegrityError, match="ck_employee_skill_level_range"):
        session.execute(
            text("INSERT INTO employee_skill (employee_id, skill_id, level) VALUES (:e, :s, 5)"),
            {"e": employee.id, "s": skill.id},
        )


def test_deleting_an_employee_removes_their_assignments(session: Session) -> None:
    employee = make_employee()
    employee.skills.append(EmployeeSkill(skill=Skill(name="Go"), level=ProficiencyLevel.BEGINNER))
    session.add(employee)
    session.flush()

    session.execute(text("DELETE FROM employee WHERE id = :id"), {"id": employee.id})

    assert session.scalar(select(func.count()).select_from(EmployeeSkill)) == 0
    assert session.scalar(select(func.count()).select_from(Skill)) == 1


def test_a_skill_in_use_cannot_be_deleted(session: Session) -> None:
    skill = Skill(name="Terraform")
    employee = make_employee()
    employee.skills.append(EmployeeSkill(skill=skill, level=ProficiencyLevel.EXPERT))
    session.add(employee)
    session.flush()

    with pytest.raises(IntegrityError, match="fk_employee_skill_skill_id_skill"):
        session.execute(text("DELETE FROM skill WHERE id = :id"), {"id": skill.id})
