import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    ValidationError,
)

REQUIRED_COLUMNS = ("employee_number", "first_name", "last_name", "email")
OPTIONAL_COLUMNS = ("department", "job_title", "location", "hire_date")
MAX_ROWS = 10_000


class CsvFileError(Exception):
    """The file as a whole cannot be imported."""


@dataclass(frozen=True)
class RowError:
    row: int
    field: str | None
    message: str


@dataclass(frozen=True)
class ParsedRow:
    row: int
    employee: "EmployeeRow"


@dataclass(frozen=True)
class ParsedFile:
    rows: list[ParsedRow]
    errors: list[RowError]


def _blank_to_none(value: Any) -> Any:
    return None if isinstance(value, str) and not value.strip() else value


def _german_date(value: Any) -> Any:
    value = _blank_to_none(value)
    if isinstance(value, str) and re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", value.strip()):
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    return value


OptionalText = Annotated[
    Annotated[str, StringConstraints(max_length=200)] | None, BeforeValidator(_blank_to_none)
]


class EmployeeRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    employee_number: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: Annotated[EmailStr, AfterValidator(str.lower)]
    department: OptionalText = None
    job_title: OptionalText = None
    location: OptionalText = None
    # ISO dates and the DD.MM.YYYY format that a German Excel writes.
    hire_date: Annotated[date | None, BeforeValidator(_german_date)] = None


def parse_employee_csv(content: bytes) -> ParsedFile:
    reader = csv.reader(io.StringIO(_decode(content), newline=""), delimiter=_delimiter(content))
    columns = _columns(next(reader, None))

    rows: list[ParsedRow] = []
    errors: list[RowError] = []
    seen = 0
    for values in reader:
        if not any(value.strip() for value in values):
            continue
        seen += 1
        if seen > MAX_ROWS:
            raise CsvFileError(f"The file has more than {MAX_ROWS} rows")
        if len(values) != len(columns):
            errors.append(
                RowError(
                    reader.line_num, None, f"Expected {len(columns)} values, found {len(values)}"
                )
            )
            continue
        record = dict(zip(columns, values, strict=True))
        try:
            rows.append(ParsedRow(reader.line_num, EmployeeRow.model_validate(record)))
        except ValidationError as exc:
            errors.extend(_row_errors(reader.line_num, record, exc))
    if seen == 0:
        raise CsvFileError("The file has no data rows")
    return ParsedFile(rows, errors)


def _decode(content: bytes) -> str:
    # Excel saves "CSV UTF-8" with a BOM and plain "CSV" in the Windows code page.
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvFileError("The file is neither UTF-8 nor Windows-1252 text")


def _delimiter(content: bytes) -> str:
    # A German Excel separates with ";" because "," is its decimal separator.
    header = content.split(b"\n", 1)[0]
    return max((",", ";", "\t"), key=lambda candidate: header.count(candidate.encode()))


def _columns(header: list[str] | None) -> list[str]:
    if header is None or not any(name.strip() for name in header):
        raise CsvFileError("The file is empty")
    columns = [re.sub(r"[\s-]+", "_", name.strip().lower()) for name in header]
    if missing := [name for name in REQUIRED_COLUMNS if name not in columns]:
        raise CsvFileError(f"Missing required columns: {', '.join(missing)}")
    if duplicates := sorted({name for name in columns if columns.count(name) > 1}):
        raise CsvFileError(f"Duplicate columns: {', '.join(duplicates)}")
    return columns


def _row_errors(row: int, record: dict[str, str], exc: ValidationError) -> list[RowError]:
    errors = []
    for error in exc.errors():
        field = str(error["loc"][0])
        blank = not record.get(field, "").strip()
        message = "is required" if blank and field in REQUIRED_COLUMNS else error["msg"]
        errors.append(RowError(row, field, message))
    return errors
