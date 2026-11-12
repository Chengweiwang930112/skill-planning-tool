from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import problem_response
from app.models import Skill
from app.schemas import (
    EmployeeQuery,
    EmployeeRead,
    Page,
    SkillAssignmentRead,
    SkillAssignmentWrite,
    SkillRead,
)
from app.services import employees as service
from app.services import skills as skills_service

router = APIRouter(
    prefix="/employees",
    tags=["employees"],
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: problem_response("Invalid parameters")},
)

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", summary="List employees")
async def list_employees(
    session: Session, query: Annotated[EmployeeQuery, Query()]
) -> Page[EmployeeRead]:
    """Employees with their assigned skills, filtered, sorted and paginated."""
    employees, total = await service.list_employees(session, query)
    return Page(
        items=[EmployeeRead.model_validate(employee) for employee in employees],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get(
    "/{employee_id}",
    summary="Get an employee",
    responses={status.HTTP_404_NOT_FOUND: problem_response("Employee not found")},
)
async def get_employee(session: Session, employee_id: int) -> EmployeeRead:
    employee = await service.get_employee(session, employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Employee {employee_id} does not exist")
    return EmployeeRead.model_validate(employee)


async def _existing_skill(session: AsyncSession, employee_id: int, skill_id: int) -> Skill:
    if await service.get_employee(session, employee_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Employee {employee_id} does not exist")
    skill = await skills_service.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Skill {skill_id} does not exist")
    return skill


@router.put(
    "/{employee_id}/skills/{skill_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Assign a skill or change its level",
    responses={
        status.HTTP_200_OK: {"model": SkillAssignmentRead, "description": "Level changed"},
        status.HTTP_404_NOT_FOUND: problem_response("Employee or skill not found"),
    },
)
async def assign_skill(
    session: Session,
    employee_id: int,
    skill_id: int,
    body: SkillAssignmentWrite,
    response: Response,
) -> SkillAssignmentRead:
    """Idempotent: 201 when the employee did not have the skill yet, 200 otherwise."""
    skill = await _existing_skill(session, employee_id, skill_id)
    if not await service.assign_skill(session, employee_id, skill_id, body.level):
        response.status_code = status.HTTP_200_OK
    return SkillAssignmentRead(skill=SkillRead.model_validate(skill), level=body.level)


@router.delete(
    "/{employee_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a skill from an employee",
    responses={status.HTTP_404_NOT_FOUND: problem_response("Employee or skill not found")},
)
async def remove_skill(session: Session, employee_id: int, skill_id: int) -> None:
    """Idempotent: removing a skill the employee does not have is not an error."""
    await _existing_skill(session, employee_id, skill_id)
    await service.remove_skill(session, employee_id, skill_id)
