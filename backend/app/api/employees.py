from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.errors import problem_response
from app.models import Skill
from app.schemas import (
    EmployeeQuery,
    EmployeeRead,
    EmployeeSkillsWrite,
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

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", summary="List employees")
def list_employees(
    session: SessionDep, query: Annotated[EmployeeQuery, Query()]
) -> Page[EmployeeRead]:
    """Employees with their assigned skills, filtered, sorted and paginated."""
    employees, total = service.list_employees(session, query)
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
def get_employee(session: SessionDep, employee_id: int) -> EmployeeRead:
    employee = service.get_employee(session, employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Employee {employee_id} does not exist")
    return EmployeeRead.model_validate(employee)


@router.put(
    "/{employee_id}/skills",
    summary="Replace all skills of an employee",
    responses={status.HTTP_404_NOT_FOUND: problem_response("Employee not found")},
)
def replace_skills(
    session: SessionDep, employee_id: int, body: EmployeeSkillsWrite
) -> EmployeeRead:
    """Sets the employee's complete set of skills in one transaction: listed skills are
    assigned at their level, all others are removed. Skills come from the catalogue
    (`GET /skills`); unknown ids are rejected. Either all changes apply or none."""
    if service.get_employee(session, employee_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Employee {employee_id} does not exist")
    try:
        service.replace_skills(session, employee_id, body.skills)
    except service.UnknownSkillsError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    # The existence check loaded the old skills into the session; read the new ones.
    session.expunge_all()
    employee = service.get_employee(session, employee_id)
    assert employee is not None
    return EmployeeRead.model_validate(employee)


def _existing_skill(session: Session, employee_id: int, skill_id: int) -> Skill:
    if service.get_employee(session, employee_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Employee {employee_id} does not exist")
    skill = skills_service.get_skill(session, skill_id)
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
def assign_skill(
    session: SessionDep,
    employee_id: int,
    skill_id: int,
    body: SkillAssignmentWrite,
    response: Response,
) -> SkillAssignmentRead:
    """Idempotent: 201 when the employee did not have the skill yet, 200 otherwise."""
    skill = _existing_skill(session, employee_id, skill_id)
    if not service.assign_skill(session, employee_id, skill_id, body.level):
        response.status_code = status.HTTP_200_OK
    return SkillAssignmentRead(skill=SkillRead.model_validate(skill), level=body.level)


@router.delete(
    "/{employee_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a skill from an employee",
    responses={status.HTTP_404_NOT_FOUND: problem_response("Employee or skill not found")},
)
def remove_skill(session: SessionDep, employee_id: int, skill_id: int) -> None:
    """Idempotent: removing a skill the employee does not have is not an error."""
    _existing_skill(session, employee_id, skill_id)
    service.remove_skill(session, employee_id, skill_id)
