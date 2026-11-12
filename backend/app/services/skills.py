from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill
from app.schemas import SkillQuery


async def list_skills(session: AsyncSession, query: SkillQuery) -> tuple[Sequence[Skill], int]:
    statement = select(Skill)
    if query.q:
        statement = statement.where(Skill.name.icontains(query.q, autoescape=True))
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    skills = await session.scalars(
        statement.order_by(func.lower(Skill.name))
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    )
    return skills.all(), total or 0


async def get_or_create_skill(session: AsyncSession, name: str) -> tuple[Skill, bool]:
    """Returns the skill with this name, ignoring case, and whether it was just created."""
    # ON CONFLICT instead of "select, then insert", which two concurrent requests
    # for the same new name would both pass before one of them hits the unique index.
    created_id = await session.scalar(
        insert(Skill)
        .values(name=name)
        .on_conflict_do_nothing(index_elements=[func.lower(Skill.name)])
        .returning(Skill.id)
    )
    await session.commit()
    skill = await session.scalar(select(Skill).where(func.lower(Skill.name) == name.lower()))
    assert skill is not None
    return skill, created_id is not None


async def get_skill(session: AsyncSession, skill_id: int) -> Skill | None:
    return await session.get(Skill, skill_id)
