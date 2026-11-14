from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmployeeSkill, Skill, skill_key
from app.schemas import RowErrorRead, SkillImportResult, SkillQuery
from app.services.csv_parsing import parse_skill_csv


class DuplicateSkillError(Exception):
    def __init__(self, existing: Skill) -> None:
        super().__init__(f"{existing.name} is already in the catalogue")
        self.existing = existing


class SkillInUseError(Exception):
    def __init__(self, employee_count: int) -> None:
        super().__init__(f"The skill is assigned to {employee_count} employees")
        self.employee_count = employee_count


async def list_skills(
    session: AsyncSession, query: SkillQuery
) -> tuple[Sequence[tuple[Skill, int]], int]:
    """Skills alphabetically, each with the number of employees who have it."""
    statement = select(Skill)
    if query.q:
        key = skill_key(query.q)
        statement = statement.where(
            Skill.key.contains(key, autoescape=True)
            if key
            else Skill.name.icontains(query.q, autoescape=True)
        )
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = await session.execute(
        statement.add_columns(func.count(EmployeeSkill.employee_id))
        .outerjoin(EmployeeSkill)
        .group_by(Skill.id)
        .order_by(func.lower(Skill.name))
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    )
    return [(skill, count) for skill, count in rows], total or 0


async def create_skill(session: AsyncSession, name: str) -> Skill:
    # ON CONFLICT instead of "select, then insert", which two concurrent requests
    # for the same new name would both pass before one of them hits the unique key.
    skill_id = await session.scalar(
        insert(Skill)
        .values(name=name, key=skill_key(name))
        .on_conflict_do_nothing(index_elements=[Skill.key])
        .returning(Skill.id)
    )
    await session.commit()
    if skill_id is None:
        raise DuplicateSkillError(await _by_key(session, skill_key(name)))
    skill = await session.get(Skill, skill_id)
    assert skill is not None
    return skill


async def rename_skill(session: AsyncSession, skill: Skill, name: str) -> Skill:
    existing = await session.scalar(select(Skill).where(Skill.key == skill_key(name)))
    if existing is not None and existing.id != skill.id:
        raise DuplicateSkillError(existing)
    skill.name = name
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DuplicateSkillError(await _by_key(session, skill_key(name))) from None
    return skill


async def delete_skill(session: AsyncSession, skill: Skill) -> None:
    employee_count = await session.scalar(
        select(func.count()).where(EmployeeSkill.skill_id == skill.id)
    )
    if employee_count:
        raise SkillInUseError(employee_count)
    await session.delete(skill)
    await session.commit()


async def import_skills(session: AsyncSession, content: bytes) -> SkillImportResult:
    """Adds the names in a CSV to the catalogue; names it already has are left alone."""
    names, errors = parse_skill_csv(content)
    unique = {skill_key(parsed.name): parsed.name for parsed in reversed(names)}
    created: Sequence[int] = []
    if unique:
        created = (
            await session.scalars(
                insert(Skill)
                .values([{"name": name, "key": key} for key, name in unique.items()])
                .on_conflict_do_nothing(index_elements=[Skill.key])
                .returning(Skill.id)
            )
        ).all()
        await session.commit()
    return SkillImportResult(
        rows_created=len(created),
        rows_existing=len(names) - len(created),
        row_errors=[RowErrorRead(row=e.row, field=e.field, message=e.message) for e in errors],
    )


async def get_skill(session: AsyncSession, skill_id: int) -> Skill | None:
    return await session.get(Skill, skill_id)


async def _by_key(session: AsyncSession, key: str) -> Skill:
    skill = await session.scalar(select(Skill).where(Skill.key == key))
    assert skill is not None
    return skill
