import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Employee, EmployeeSkill, ProficiencyLevel, Skill
from tests.factories import make_employee


def test_migrations_match_the_models(alembic_config: Config, migrated_database: None) -> None:
    # When / Then
    command.check(alembic_config)


def test_an_assigned_skill_round_trips_with_its_level(session: Session) -> None:
    # Given
    employee = make_employee({Skill(name="Kubernetes"): ProficiencyLevel.ADVANCED})
    session.add(employee)
    session.flush()
    session.expunge_all()

    # When
    loaded = session.scalar(select(Employee).options(selectinload(Employee.skills)))

    # Then
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
    # Given
    session.add(make_employee(employee_number="E-1001", email="anna.schmidt@example.com"))
    session.flush()

    # When
    session.add(duplicate)

    # Then
    with pytest.raises(IntegrityError):
        session.flush()


def test_skill_keys_are_unique(session: Session) -> None:
    # Given
    session.add(Skill(name="Node.js"))
    session.flush()

    # When
    session.add(Skill(name="NODEJS"))

    # Then
    with pytest.raises(IntegrityError, match="uq_skill_key"):
        session.flush()


def test_the_database_rejects_levels_outside_the_scale(session: Session) -> None:
    # Given
    employee, skill = make_employee(), Skill(name="Python")
    session.add_all([employee, skill])
    session.flush()

    # When / Then
    with pytest.raises(IntegrityError, match="ck_employee_skill_level_range"):
        session.execute(
            text("INSERT INTO employee_skill (employee_id, skill_id, level) VALUES (:e, :s, 5)"),
            {"e": employee.id, "s": skill.id},
        )


def test_deleting_an_employee_removes_their_assignments(session: Session) -> None:
    # Given
    employee = make_employee({Skill(name="Go"): ProficiencyLevel.BEGINNER})
    session.add(employee)
    session.flush()

    # When
    session.execute(text("DELETE FROM employee WHERE id = :id"), {"id": employee.id})

    # Then
    assert session.scalar(select(func.count()).select_from(EmployeeSkill)) == 0
    assert session.scalar(select(func.count()).select_from(Skill)) == 1


def test_a_skill_in_use_cannot_be_deleted(session: Session) -> None:
    # Given
    skill = Skill(name="Terraform")
    session.add(make_employee({skill: ProficiencyLevel.EXPERT}))
    session.flush()

    # When / Then
    with pytest.raises(IntegrityError, match="fk_employee_skill_skill_id_skill"):
        session.execute(text("DELETE FROM skill WHERE id = :id"), {"id": skill.id})
