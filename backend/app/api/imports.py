from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import problem_response
from app.schemas import ImportRead, ImportSummary, Page, PageQuery
from app.services import employee_import as service
from app.services.csv_parsing import OPTIONAL_COLUMNS, REQUIRED_COLUMNS

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

router = APIRouter(
    prefix="/imports",
    tags=["imports"],
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: problem_response("Invalid parameters")},
)

Session = Annotated[AsyncSession, Depends(get_session)]

UPLOAD_DESCRIPTION = f"""CSV with a header row. Required columns: {", ".join(REQUIRED_COLUMNS)};
optional: {", ".join(OPTIONAL_COLUMNS)}. Comma, semicolon or tab separated; UTF-8 or
Windows-1252; dates as YYYY-MM-DD or DD.MM.YYYY. At most 5 MB."""


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Import employees from a CSV file",
    responses={status.HTTP_413_CONTENT_TOO_LARGE: problem_response("File larger than 5 MB")},
)
async def create_import(
    session: Session, file: Annotated[UploadFile, File(description=UPLOAD_DESCRIPTION)]
) -> ImportRead:
    """Creates or updates employees by `employee_number`, so importing a file again is safe.

    Valid rows are imported even if other rows fail; every upload is recorded, including
    files that are rejected as a whole, and the response is that record.
    """
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The file is larger than 5 MB")
    record = await service.import_employees(session, file.filename or "upload.csv", content)
    return ImportRead.model_validate(record)


@router.get("", summary="List imports, newest first")
async def list_imports(
    session: Session, query: Annotated[PageQuery, Query()]
) -> Page[ImportSummary]:
    imports, total = await service.list_imports(session, query.page, query.page_size)
    return Page(
        items=[ImportSummary.model_validate(record) for record in imports],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


@router.get(
    "/{import_id}",
    summary="Get an import with its row errors",
    responses={status.HTTP_404_NOT_FOUND: problem_response("Import not found")},
)
async def get_import(session: Session, import_id: int) -> ImportRead:
    record = await service.get_import(session, import_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Import {import_id} does not exist")
    return ImportRead.model_validate(record)
