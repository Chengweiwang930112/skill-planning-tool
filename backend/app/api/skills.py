from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import problem_response
from app.schemas import Page, SkillCreate, SkillQuery, SkillRead
from app.services import skills as service

router = APIRouter(
    prefix="/skills",
    tags=["skills"],
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: problem_response("Invalid parameters")},
)

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", summary="List skills")
async def list_skills(session: Session, query: Annotated[SkillQuery, Query()]) -> Page[SkillRead]:
    """The skill catalogue, alphabetically; `q` narrows it down for autocompletion."""
    skills, total = await service.list_skills(session, query)
    return Page(
        items=[SkillRead.model_validate(skill) for skill in skills],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a skill, or get the existing one",
    responses={
        status.HTTP_200_OK: {"model": SkillRead, "description": "The skill already existed"}
    },
)
async def create_skill(session: Session, body: SkillCreate, response: Response) -> SkillRead:
    """Names are unique regardless of case: asking for `kubernetes` when `Kubernetes`
    exists returns the existing skill with 200 instead of creating a near-duplicate."""
    skill, created = await service.get_or_create_skill(session, body.name)
    if not created:
        response.status_code = status.HTTP_200_OK
    return SkillRead.model_validate(skill)
