from datetime import date
from pathlib import Path

import pytest

from app.services import csv_parsing
from app.services.csv_parsing import CsvFileError, parse_employee_csv

SAMPLES = Path(__file__).parents[2] / "samples"
HEADER = "employee_number,first_name,last_name,email"


def test_parses_the_sample_file() -> None:
    parsed = parse_employee_csv((SAMPLES / "employees.csv").read_bytes())

    assert parsed.errors == []
    assert len(parsed.rows) == 12
    last = parsed.rows[-1]
    assert (last.row, last.employee.job_title) == (13, "Security Engineer, Cloud")
    assert last.employee.hire_date == date(2021, 3, 15)


def test_parses_a_german_excel_export() -> None:
    parsed = parse_employee_csv((SAMPLES / "employees-excel-de.csv").read_bytes())

    assert parsed.errors == []
    assert [(r.employee.first_name, r.employee.last_name) for r in parsed.rows] == [
        ("Jürgen", "Weiß"),
        ("Özlem", "Yildiz"),
        ("François", "Dupont"),
        ("Käthe", "Groß"),
    ]
    first, last = parsed.rows[0].employee, parsed.rows[-1].employee
    assert (first.location, first.hire_date) == ("München", date(2015, 9, 1))
    assert last.hire_date is None


def test_reports_invalid_rows_with_their_line_numbers() -> None:
    parsed = parse_employee_csv((SAMPLES / "employees-with-errors.csv").read_bytes())

    assert [(e.row, e.field) for e in parsed.errors] == [
        (3, "first_name"),
        (4, "email"),
        (5, "hire_date"),
        (9, None),
    ]
    assert parsed.errors[0].message == "is required"
    assert parsed.errors[3].message == "Expected 8 values, found 9"
    assert [r.row for r in parsed.rows] == [2, 6, 7, 8, 10]


def test_normalises_values() -> None:
    content = f"{HEADER},department\n  E-1  , Anna ,Schmidt, Anna.Schmidt@Example.COM ,  \n"

    [row] = parse_employee_csv(content.encode()).rows

    assert row.employee.employee_number == "E-1"
    assert row.employee.first_name == "Anna"
    assert row.employee.email == "anna.schmidt@example.com"
    assert row.employee.department is None


def test_accepts_tab_separated_files() -> None:
    content = "employee_number\tfirst_name\tlast_name\temail\nE-1\tAnna\tSchmidt\ta@example.com\n"

    assert len(parse_employee_csv(content.encode()).rows) == 1


def test_rejects_impossible_dates() -> None:
    content = f"{HEADER},hire_date\nE-1,Anna,Schmidt,a@example.com,31.02.2020\n"

    [error] = parse_employee_csv(content.encode()).errors

    assert (error.row, error.field) == (2, "hire_date")


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "The file is empty"),
        (b"employee_number,first_name\nE-1,Anna\n", "Missing required columns: last_name, email"),
        (f"{HEADER},email\n".encode(), "Duplicate columns: email"),
        (f"{HEADER}\n\n".encode(), "The file has no data rows"),
        (b"\x81\x8d\x8f", "The file is neither UTF-8 nor Windows-1252 text"),
    ],
    ids=["empty", "missing-columns", "duplicate-columns", "no-rows", "binary"],
)
def test_rejects_unusable_files(content: bytes, message: str) -> None:
    with pytest.raises(CsvFileError, match=f"^{message}$"):
        parse_employee_csv(content)


def test_rejects_files_with_too_many_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(csv_parsing, "MAX_ROWS", 2)
    rows = "".join(f"E-{n},Anna,Schmidt,a{n}@example.com\n" for n in range(3))

    with pytest.raises(CsvFileError, match="more than 2 rows"):
        parse_employee_csv(f"{HEADER}\n{rows}".encode())
