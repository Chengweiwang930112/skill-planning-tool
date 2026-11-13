from collections.abc import Sequence

from sqlalchemy import Select, delete, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from app.models import Employee, EmployeeSkill, ProficiencyLevel, Skill
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
    for criterion in query.skill_criteria:
        # Served by the (skill_id, level) index on employee_skill.
        statement = statement.where(
            Employee.id.in_(
                select(EmployeeSkill.employee_id)
                .join(Skill)
                .where(
                    func.lower(Skill.name) == criterion.name.lower(),
                    EmployeeSkill.level >= criterion.min_level,
                )
            )
        )
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


async def assign_skill(
    session: AsyncSession, employee_id: int, skill_id: int, level: ProficiencyLevel
) -> bool:
    """Sets the employee's level for the skill; returns whether the assignment is new."""
    # xmax is 0 only for a row this statement inserted, not for one it updated.
    created = await session.scalar(
        insert(EmployeeSkill)
        .values(employee_id=employee_id, skill_id=skill_id, level=level)
        .on_conflict_do_update(
            index_elements=[EmployeeSkill.employee_id, EmployeeSkill.skill_id],
            set_={"level": level, "updated_at": func.now()},
        )
        .returning(literal_column("xmax = 0"))
    )
    await session.commit()
    return bool(created)


async def remove_skill(session: AsyncSession, employee_id: int, skill_id: int) -> None:
    await session.execute(
        delete(EmployeeSkill).where(
            EmployeeSkill.employee_id == employee_id, EmployeeSkill.skill_id == skill_id
        )
    )
    await session.commit()
