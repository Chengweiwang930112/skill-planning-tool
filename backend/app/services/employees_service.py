import hashlib
from collections.abc import Sequence

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import InstrumentedAttribute, Session, selectinload

from app.models import (
    Department,
    Employee,
    EmployeeSkill,
    Location,
    Skill,
    name_key,
)
from app.schemas import EmployeeQuery, EmployeeRead, SkillLevelWrite

SORTABLE: dict[str, InstrumentedAttribute[object]] = {
    "last_name": Employee.last_name,
    "first_name": Employee.first_name,
    "employee_number": Employee.employee_number,
    "department": Department.name,
    "location": Location.name,
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
        keys = [name_key(name) for name in query.department]
        statement = statement.where(Employee.department.has(Department.key.in_(keys)))
    if query.location:
        keys = [name_key(name) for name in query.location]
        statement = statement.where(Employee.location.has(Location.key.in_(keys)))
    for criterion in query.skill_criteria:
        # Served by the (skill_id, level) index on employee_skill.
        statement = statement.where(
            Employee.id.in_(
                select(EmployeeSkill.employee_id)
                .join(Skill)
                .where(
                    Skill.key == name_key(criterion.name),
                    EmployeeSkill.level >= criterion.min_level,
                )
            )
        )
    return statement


def list_employees(session: Session, query: EmployeeQuery) -> tuple[Sequence[Employee], int]:
    statement = _filtered(query)
    total = session.scalar(select(func.count()).select_from(statement.subquery()))

    column = SORTABLE[query.sort.removeprefix("-")]
    order = column.desc() if query.sort.startswith("-") else column.asc()
    employees = session.scalars(
        # Joined for sorting by their names; employees without one stay in, sorted last.
        statement.outerjoin(Department, Employee.department_id == Department.id)
        .outerjoin(Location, Employee.location_id == Location.id)
        .options(selectinload(Employee.skills))
        .order_by(order.nulls_last(), Employee.id)
        .limit(query.page_size)
        .offset((query.page - 1) * query.page_size)
    )
    return employees.all(), total or 0


def get_employee(session: Session, employee_id: int) -> Employee | None:
    return session.get(Employee, employee_id, options=[selectinload(Employee.skills)])


class EmployeeNotFoundError(Exception):
    def __init__(self, employee_id: int) -> None:
        super().__init__(f"Employee {employee_id} does not exist")


class EmployeeChangedError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The employee has changed since it was loaded; load it again and redo the changes"
        )


class UnknownSkillsError(Exception):
    def __init__(self, skill_ids: list[int]) -> None:
        super().__init__(f"Unknown skills: {', '.join(map(str, skill_ids))}")
        self.skill_ids = skill_ids


def etag(employee: Employee) -> str:
    """The version of the employee as the API shows it: whatever changes what it shows
    changes the version, so a client can tell that what it loaded is out of date."""
    shown = EmployeeRead.model_validate(employee).model_dump_json()
    return f'"{hashlib.sha256(shown.encode()).hexdigest()[:32]}"'


def replace_skills(
    session: Session, employee_id: int, skills: list[SkillLevelWrite], if_match: str
) -> Employee:
    """Makes `skills` the employee's complete set of skills, in one transaction, if the
    employee is still at the version `if_match` names, and returns it as stored. Only
    catalogue skills can be assigned; this never creates one."""
    # Locked until the commit, so that of two concurrent requests from the same version,
    # the second one waits, then sees the first one's change and is refused.
    employee = session.scalar(
        select(Employee)
        .where(Employee.id == employee_id)
        .options(selectinload(Employee.skills))
        .with_for_update(of=Employee)
    )
    if employee is None:
        raise EmployeeNotFoundError(employee_id)
    if etag(employee) != if_match:
        raise EmployeeChangedError()
    ids = [skill.skill_id for skill in skills]
    known = set(session.scalars(select(Skill.id).where(Skill.id.in_(ids))))
    if unknown := sorted(set(ids) - known):
        raise UnknownSkillsError(unknown)

    session.execute(
        delete(EmployeeSkill).where(
            EmployeeSkill.employee_id == employee_id, EmployeeSkill.skill_id.not_in(ids)
        )
    )
    if skills:
        statement = insert(EmployeeSkill).values(
            [{"employee_id": employee_id, "skill_id": s.skill_id, "level": s.level} for s in skills]
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[EmployeeSkill.employee_id, EmployeeSkill.skill_id],
                set_={"level": statement.excluded.level, "updated_at": func.now()},
                where=EmployeeSkill.level != statement.excluded.level,
            )
        )
    session.commit()
    # The statements above bypassed the session, which still holds the skills as loaded.
    stored = session.get(
        Employee, employee_id, options=[selectinload(Employee.skills)], populate_existing=True
    )
    assert stored is not None
    return stored
