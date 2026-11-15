from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.imports_api import MAX_UPLOAD_BYTES
from app.core.database import get_session
from app.core.errors import problem_response
from app.models import Skill
from app.schemas import Page, SkillImportResult, SkillQuery, SkillRead, SkillWithUsage, SkillWrite
from app.services import skills_service
from app.services.csv_parsing import CsvFileError

router = APIRouter(
    prefix="/skills",
    tags=["skills"],
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: problem_response("Invalid parameters")},
)

SessionDep = Annotated[Session, Depends(get_session)]
Responses = dict[int | str, dict[str, Any]]
DUPLICATE: Responses = {status.HTTP_409_CONFLICT: problem_response("A skill with this name exists")}
NOT_FOUND: Responses = {status.HTTP_404_NOT_FOUND: problem_response("Skill not found")}


def _conflict(error: skills_service.DuplicateSkillError) -> HTTPException:
    detail = f"The catalogue already has {error.existing.name} (skill {error.existing.id})"
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def _existing(session: Session, skill_id: int) -> Skill:
    skill = skills_service.get_skill(session, skill_id)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Skill {skill_id} does not exist")
    return skill


@router.get("", summary="List the skill catalogue")
def list_skills(session: SessionDep, query: Annotated[SkillQuery, Query()]) -> Page[SkillWithUsage]:
    """Alphabetically, with how many employees have each skill; `q` narrows the list down,
    e.g. for autocompletion, ignoring case, spaces and punctuation."""
    rows, total = skills_service.list_skills(session, query)
    return Page(
        items=[
            SkillWithUsage(id=skill.id, name=skill.name, employee_count=count)
            for skill, count in rows
        ],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Add a skill", responses=DUPLICATE)
def create_skill(session: SessionDep, body: SkillWrite) -> SkillRead:
    """Names must be unique ignoring case, spaces and punctuation, so that the catalogue
    does not end up with Node.js next to NodeJS."""
    try:
        return SkillRead.model_validate(skills_service.create_skill(session, body.name))
    except skills_service.DuplicateSkillError as error:
        raise _conflict(error) from None


@router.patch("/{skill_id}", summary="Rename a skill", responses={**NOT_FOUND, **DUPLICATE})
def rename_skill(session: SessionDep, skill_id: int, body: SkillWrite) -> SkillRead:
    """Every employee with the skill shows the new name."""
    skill = _existing(session, skill_id)
    try:
        return SkillRead.model_validate(skills_service.rename_skill(session, skill, body.name))
    except skills_service.DuplicateSkillError as error:
        raise _conflict(error) from None


@router.delete(
    "/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a skill nobody has",
    responses={
        **NOT_FOUND,
        status.HTTP_409_CONFLICT: problem_response("Employees have the skill"),
    },
)
def delete_skill(session: SessionDep, skill_id: int) -> None:
    skill = _existing(session, skill_id)
    try:
        skills_service.delete_skill(session, skill)
    except skills_service.SkillInUseError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None


@router.post(
    "/import",
    summary="Add skills from a CSV file",
    responses={status.HTTP_413_CONTENT_TOO_LARGE: problem_response("File larger than 10 MB")},
)
def import_skills(
    session: SessionDep,
    file: Annotated[
        UploadFile, File(description="CSV with a `name` column; UTF-8 or Windows-1252.")
    ],
) -> SkillImportResult:
    """Adds every name not yet in the catalogue; importing the same file again changes
    nothing. Meant for moving an existing list of skills in at once."""
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The file is larger than 10 MB")
    try:
        return skills_service.import_skills(session, content)
    except CsvFileError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
