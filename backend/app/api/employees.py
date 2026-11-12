from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import problem_response
from app.schemas import EmployeeQuery, EmployeeRead, Page
from app.services import employees as service

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
