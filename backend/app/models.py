from datetime import UTC, date, datetime
from enum import IntEnum, StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Dialect,
    ForeignKey,
    Index,
    MetaData,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates
from sqlalchemy.types import TypeDecorator


class ProficiencyLevel(IntEnum):
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4


class ImportStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


# Stored as an integer rather than a native Postgres enum, so that "at least
# ADVANCED" is a plain `level >= 3` and adding a level needs no type migration.
class ProficiencyLevelType(TypeDecorator[ProficiencyLevel]):
    impl = SmallInteger
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> int | None:
        return None if value is None else int(ProficiencyLevel(value))

    def process_result_value(self, value: Any, dialect: Dialect) -> ProficiencyLevel | None:
        return None if value is None else ProficiencyLevel(value)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def name_key(name: str) -> str:
    """What makes two names the same name, for skills, departments and locations: case,
    spaces and punctuation do not count, so Node.js, NodeJS and node js are one skill. + and
    # are spelled out first, so that C, C++ and C# stay three skills."""
    spelled = name.casefold().replace("+", "plus").replace("#", "sharp")
    return "".join(character for character in spelled if character.isalnum())


class _Named:
    """A name that exists once, whatever its spelling, as told by its key."""

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    key: Mapped[str] = mapped_column(unique=True)

    @validates("name")
    def _derive_key(self, _: str, name: str) -> str:
        self.key = name_key(name)
        return name


class Department(_Named, Base):
    __tablename__ = "department"


class Location(_Named, Base):
    __tablename__ = "location"


class Employee(Base):
    __tablename__ = "employee"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_number: Mapped[str] = mapped_column(unique=True)
    first_name: Mapped[str]
    last_name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("department.id"), index=True)
    job_title: Mapped[str | None]
    location_id: Mapped[int | None] = mapped_column(ForeignKey("location.id"), index=True)
    hire_date: Mapped[date | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    department: Mapped[Department | None] = relationship(lazy="joined")
    location: Mapped[Location | None] = relationship(lazy="joined")
    skills: Mapped[list["EmployeeSkill"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: (EmployeeSkill.level.desc(), EmployeeSkill.skill_id),
    )


class Skill(_Named, Base):
    __tablename__ = "skill"


class EmployeeSkill(Base):
    __tablename__ = "employee_skill"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 4", name="level_range"),
        Index("ix_employee_skill_skill_id_level", "skill_id", "level"),
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skill.id", ondelete="RESTRICT"), primary_key=True
    )
    level: Mapped[ProficiencyLevel] = mapped_column(ProficiencyLevelType())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    employee: Mapped[Employee] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship(lazy="joined")


class EmployeeImport(Base):
    __tablename__ = "employee_import"
    __table_args__ = (
        CheckConstraint(
            "status IN ('succeeded', 'partially_succeeded', 'failed')", name="status_values"
        ),
        CheckConstraint(
            "rows_succeeded = rows_created + rows_updated + rows_unchanged",
            name="succeeded_breakdown",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    file_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[ImportStatus] = mapped_column(String)
    rows_succeeded: Mapped[int]
    rows_failed: Mapped[int]
    rows_created: Mapped[int]
    rows_updated: Mapped[int]
    rows_unchanged: Mapped[int]
    error: Mapped[str | None]
    row_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    # Set in Python so the value is known right after the insert, without a refresh.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
