from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
    computed_field,
)

from app.models import ImportStatus, ProficiencyLevel

LEVEL_NAMES = [level.name.lower() for level in ProficiencyLevel]


def _parse_level(value: Any) -> ProficiencyLevel:
    if isinstance(value, ProficiencyLevel):
        return value
    if isinstance(value, str) and value.lower() in LEVEL_NAMES:
        return ProficiencyLevel[value.upper()]
    raise ValueError(f"must be one of {', '.join(LEVEL_NAMES)}")


Level = Annotated[
    ProficiencyLevel,
    BeforeValidator(_parse_level),
    PlainSerializer(lambda level: level.name.lower(), return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "enum": LEVEL_NAMES,
            "description": "Ordered from lowest to highest.",
        }
    ),
]

EmployeeSort = Literal[
    "last_name",
    "-last_name",
    "first_name",
    "-first_name",
    "employee_number",
    "-employee_number",
    "department",
    "-department",
    "location",
    "-location",
    "hire_date",
    "-hire_date",
]


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(description="Number of matching items across all pages.", examples=[42])
    page: int = Field(examples=[1])
    page_size: int = Field(examples=[20])


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[7])
    name: str = Field(examples=["Kubernetes"])


SkillName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100),
    BeforeValidator(lambda name: " ".join(name.split()) if isinstance(name, str) else name),
    Field(examples=["Kubernetes"]),
]


class SkillCreate(BaseModel):
    name: SkillName = Field(
        description="Matched case-insensitively against existing skills; whitespace is collapsed."
    )


class SkillAssignmentWrite(BaseModel):
    level: Level = Field(examples=["advanced"])


class SkillAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: SkillRead
    level: Level


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    employee_number: str = Field(examples=["E-1001"])
    first_name: str = Field(examples=["Anna"])
    last_name: str = Field(examples=["Schmidt"])
    email: str = Field(examples=["anna.schmidt@example.com"])
    department: str | None = Field(examples=["Digital Industries"])
    job_title: str | None = Field(examples=["Senior Software Engineer"])
    location: str | None = Field(examples=["Munich"])
    hire_date: date | None = Field(examples=["2019-04-01"])
    skills: list[SkillAssignmentRead] = Field(description="Strongest skills first.")


class PageQuery(BaseModel):
    page: int = Field(1, ge=1, description="1-based page number.")
    page_size: int = Field(20, ge=1, le=100, description="Items per page (max 100).")


class SkillQuery(PageQuery):
    q: str | None = Field(
        None, min_length=1, max_length=100, description="Case-insensitive part of the name."
    )


class EmployeeQuery(PageQuery):
    q: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Case-insensitive match on full name, email or employee number.",
        examples=["schmidt"],
    )
    department: str | None = Field(
        None, description="Exact department, case-insensitive.", examples=["Digital Industries"]
    )
    sort: EmployeeSort = Field(
        "last_name", description="Field to sort by; prefix `-` for descending."
    )


class RowErrorRead(BaseModel):
    row: int = Field(description="Line in the file; the header is line 1.", examples=[3])
    field: str | None = Field(description="Column, if the problem is in one.", examples=["email"])
    message: str = Field(examples=["value is not a valid email address"])


class ImportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    filename: str = Field(examples=["employees.csv"])
    status: ImportStatus = Field(
        description="`failed` when no row could be imported, including unreadable files."
    )
    rows_succeeded: int = Field(description="Created + updated + unchanged.", examples=[11])
    rows_failed: int = Field(description="Rows with at least one error.", examples=[1])
    rows_created: int = Field(examples=[2])
    rows_updated: int = Field(examples=[1])
    rows_unchanged: int = Field(
        description="Rows identical to the stored employee, e.g. when a file is imported again.",
        examples=[8],
    )
    error: str | None = Field(
        description="Why the whole file was rejected, if it was.", examples=[None]
    )
    file_sha256: str
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rows_total(self) -> int:
        return self.rows_succeeded + self.rows_failed


class ImportRead(ImportSummary):
    row_errors: list[RowErrorRead] = Field(description="Ordered by row.")
