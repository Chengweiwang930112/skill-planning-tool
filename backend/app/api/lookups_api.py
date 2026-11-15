from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.errors import problem_response
from app.models import Department, Location
from app.schemas import DepartmentRead, LocationRead, NameQuery, Page
from app.services import lookups_service

router = APIRouter(
    tags=["departments and locations"],
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: problem_response("Invalid parameters")},
)

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/departments", summary="List departments")
def list_departments(
    session: SessionDep, query: Annotated[NameQuery, Query()]
) -> Page[DepartmentRead]:
    """The departments employees have been imported with, alphabetically; `q` narrows them
    down, ignoring case, spaces and punctuation. For filtering employees by department."""
    departments, total = lookups_service.list_names(session, Department, query)
    return Page(
        items=[DepartmentRead.model_validate(department) for department in departments],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get("/locations", summary="List locations")
def list_locations(session: SessionDep, query: Annotated[NameQuery, Query()]) -> Page[LocationRead]:
    """The locations employees have been imported with, like `GET /departments`."""
    locations, total = lookups_service.list_names(session, Location, query)
    return Page(
        items=[LocationRead.model_validate(location) for location in locations],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
