from collections.abc import Sequence

from sqlalchemy import Select, delete, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import InstrumentedAttribute, Session, selectinload

from app.models import (
    Department,
    Employee,
    EmployeeSkill,
    Location,
    ProficiencyLevel,
    Skill,
    name_key,
)
from app.schemas import EmployeeQuery, SkillLevelWrite

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


def assign_skill(
    session: Session, employee_id: int, skill_id: int, level: ProficiencyLevel
) -> bool:
    """Sets the employee's level for the skill; returns whether the assignment is new."""
    # xmax is 0 only for a row this statement inserted, not for one it updated.
    created = session.scalar(
        insert(EmployeeSkill)
        .values(employee_id=employee_id, skill_id=skill_id, level=level)
        .on_conflict_do_update(
            index_elements=[EmployeeSkill.employee_id, EmployeeSkill.skill_id],
            set_={"level": level, "updated_at": func.now()},
        )
        .returning(literal_column("xmax = 0"))
    )
    session.commit()
    return bool(created)


def remove_skill(session: Session, employee_id: int, skill_id: int) -> None:
    session.execute(
        delete(EmployeeSkill).where(
            EmployeeSkill.employee_id == employee_id, EmployeeSkill.skill_id == skill_id
        )
    )
    session.commit()


class UnknownSkillsError(Exception):
    def __init__(self, skill_ids: list[int]) -> None:
        super().__init__(f"Unknown skills: {', '.join(map(str, skill_ids))}")
        self.skill_ids = skill_ids


def replace_skills(session: Session, employee_id: int, skills: list[SkillLevelWrite]) -> None:
    """Makes `skills` the employee's complete set of skills, in one transaction. Only
    catalogue skills can be assigned; this never creates one."""
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
