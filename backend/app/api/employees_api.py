from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.errors import problem_response
from app.schemas import EmployeeQuery, EmployeeRead, EmployeeSkillsWrite, Page
from app.services import employees_service

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
    employees, total = employees_service.list_employees(session, query)
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
def get_employee(session: SessionDep, employee_id: int, response: Response) -> EmployeeRead:
    """With its version in the `ETag` header, which changing its skills requires."""
    employee = employees_service.get_employee(session, employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Employee {employee_id} does not exist")
    response.headers["ETag"] = employees_service.etag(employee)
    return EmployeeRead.model_validate(employee)


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an employee",
    responses={status.HTTP_404_NOT_FOUND: problem_response("Employee not found")},
)
def delete_employee(session: SessionDep, employee_id: int) -> None:
    """Deletes the employee with their skills. Needs no version: if their skills are
    being changed at the same moment, the deletion happens once that change is saved.
    An import with the employee in it later adds them again."""
    try:
        employees_service.delete_employee(session, employee_id)
    except employees_service.EmployeeNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from None


@router.put(
    "/{employee_id}/skills",
    summary="Replace all skills of an employee",
    responses={
        status.HTTP_404_NOT_FOUND: problem_response("Employee not found"),
        status.HTTP_412_PRECONDITION_FAILED: problem_response(
            "The employee has changed since it was loaded"
        ),
        status.HTTP_428_PRECONDITION_REQUIRED: problem_response("If-Match is missing"),
    },
)
def replace_skills(
    session: SessionDep,
    employee_id: int,
    body: EmployeeSkillsWrite,
    response: Response,
    if_match: Annotated[
        str | None, Header(description="The `ETag` of the employee as it was loaded.")
    ] = None,
) -> EmployeeRead:
    """Sets the employee's complete set of skills in one transaction: listed skills are
    assigned at their level, all others are removed. Skills come from the catalogue
    (`GET /skills`); unknown ids are rejected. Either all changes apply or none.

    Only for the version of the employee that was loaded (`If-Match`), so that changes
    someone else saved in the meantime are not overwritten unseen; the response has the
    new version."""
    if if_match is None:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "Send the ETag of the employee as it was loaded in If-Match",
        )
    try:
        employee = employees_service.replace_skills(session, employee_id, body.skills, if_match)
    except employees_service.EmployeeNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from None
    except employees_service.EmployeeChangedError as error:
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, str(error)) from None
    except employees_service.UnknownSkillsError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    response.headers["ETag"] = employees_service.etag(employee)
    return EmployeeRead.model_validate(employee)
