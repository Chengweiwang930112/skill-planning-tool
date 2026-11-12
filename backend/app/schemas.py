from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema

from app.models import ProficiencyLevel

Level = Annotated[
    ProficiencyLevel,
    PlainSerializer(lambda level: level.name.lower(), return_type=str),
    WithJsonSchema(
        {
            "type": "string",
            "enum": [level.name.lower() for level in ProficiencyLevel],
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


class EmployeeQuery(BaseModel):
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
    page: int = Field(1, ge=1, description="1-based page number.")
    page_size: int = Field(20, ge=1, le=100, description="Items per page (max 100).")
