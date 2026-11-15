from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import EmployeeSkill, Skill, name_key
from app.schemas import NameQuery, RowErrorRead, SkillImportResult
from app.services.csv_parsing import parse_skill_csv


class DuplicateSkillError(Exception):
    def __init__(self, existing: Skill) -> None:
        super().__init__(f"{existing.name} is already in the catalogue")
        self.existing = existing


class SkillInUseError(Exception):
    def __init__(self, employee_count: int) -> None:
        super().__init__(f"The skill is assigned to {employee_count} employees")
        self.employee_count = employee_count


def list_skills(session: Session, query: NameQuery) -> tuple[Sequence[tuple[Skill, int]], int]:
    """Skills alphabetically, each with the number of employees who have it."""
    statement = select(Skill)
    if query.q:
        key = name_key(query.q)
        statement = statement.where(
            Skill.key.contains(key, autoescape=True)
            if key
            else Skill.name.icontains(query.q, autoescape=True)
        )
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = session.execute(
        statement.add_columns(func.count(EmployeeSkill.employee_id))
        .outerjoin(EmployeeSkill)
        .group_by(Skill.id)
        .order_by(func.lower(Skill.name))
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    )
    return [(skill, count) for skill, count in rows], total or 0


def create_skill(session: Session, name: str) -> Skill:
    # ON CONFLICT instead of "select, then insert", which two concurrent requests
    # for the same new name would both pass before one of them hits the unique key.
    skill_id = session.scalar(
        insert(Skill)
        .values(name=name, key=name_key(name))
        .on_conflict_do_nothing(index_elements=[Skill.key])
        .returning(Skill.id)
    )
    session.commit()
    if skill_id is None:
        raise DuplicateSkillError(_by_key(session, name_key(name)))
    skill = session.get(Skill, skill_id)
    assert skill is not None
    return skill


def rename_skill(session: Session, skill: Skill, name: str) -> Skill:
    existing = session.scalar(select(Skill).where(Skill.key == name_key(name)))
    if existing is not None and existing.id != skill.id:
        raise DuplicateSkillError(existing)
    skill.name = name
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateSkillError(_by_key(session, name_key(name))) from None
    return skill


def delete_skill(session: Session, skill: Skill) -> None:
    employee_count = session.scalar(select(func.count()).where(EmployeeSkill.skill_id == skill.id))
    if employee_count:
        raise SkillInUseError(employee_count)
    session.delete(skill)
    session.commit()


def import_skills(session: Session, content: bytes) -> SkillImportResult:
    """Adds the names in a CSV to the catalogue; names it already has are left alone."""
    names, errors = parse_skill_csv(content)
    unique = {name_key(parsed.name): parsed.name for parsed in reversed(names)}
    created: Sequence[int] = []
    if unique:
        created = session.scalars(
            insert(Skill)
            .values([{"name": name, "key": key} for key, name in unique.items()])
            .on_conflict_do_nothing(index_elements=[Skill.key])
            .returning(Skill.id)
        ).all()
        session.commit()
    return SkillImportResult(
        rows_created=len(created),
        rows_existing=len(names) - len(created),
        row_errors=[RowErrorRead(row=e.row, field=e.field, message=e.message) for e in errors],
    )


def get_skill(session: Session, skill_id: int) -> Skill | None:
    return session.get(Skill, skill_id)


def _by_key(session: Session, key: str) -> Skill:
    skill = session.scalar(select(Skill).where(Skill.key == key))
    assert skill is not None
    return skill
