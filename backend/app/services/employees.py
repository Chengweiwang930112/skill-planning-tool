from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from app.models import Employee
from app.schemas import EmployeeQuery

SORTABLE: dict[str, InstrumentedAttribute[object]] = {
    "last_name": Employee.last_name,
    "first_name": Employee.first_name,
    "employee_number": Employee.employee_number,
    "department": Employee.department,
    "location": Employee.location,
    "hire_date": Employee.hire_date,
}


def _filtered(query: EmployeeQuery) -> Select[Employee]:
    statement = select(Employee)
    if query.q:
        full_name = func.concat(Employee.first_name, " ", Employee.last_name)
        statement = statement.where(
            or_(
                *(
                    column.icontains(query.q, autoescape=True)
                    for column in (full_name, Employee.email, Employee.employee_number)
                )
            )
        )
    if query.department:
        statement = statement.where(func.lower(Employee.department) == query.department.lower())
    return statement


async def list_employees(
    session: AsyncSession, query: EmployeeQuery
) -> tuple[Sequence[Employee], int]:
    statement = _filtered(query)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))

    column = SORTABLE[query.sort.removeprefix("-")]
    order = column.desc() if query.sort.startswith("-") else column.asc()
    employees = await session.scalars(
        statement.options(selectinload(Employee.skills))
        .order_by(order.nulls_last(), Employee.id)
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    )
    return employees.all(), total or 0


async def get_employee(session: AsyncSession, employee_id: int) -> Employee | None:
    return await session.get(Employee, employee_id, options=[selectinload(Employee.skills)])
