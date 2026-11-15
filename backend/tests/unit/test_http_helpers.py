import json

import pytest

from app.core.errors import InvalidParam, problem
from app.core.frontend import HASHED_FILE


def test_builds_a_problem_details_response() -> None:
    # When
    response = problem(404, "Employee 42 does not exist", headers={"Retry-After": "1"})

    # Then
    assert response.status_code == 404
    assert response.media_type == "application/problem+json"
    assert response.headers["retry-after"] == "1"
    assert json.loads(bytes(response.body)) == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Employee 42 does not exist",
    }


def test_a_problem_lists_the_invalid_parameters() -> None:
    # Given
    errors = [InvalidParam(name="page_size", reason="Input should be less than or equal to 100")]

    # When
    response = problem(422, "Invalid request parameters", errors)

    # Then
    assert json.loads(bytes(response.body))["errors"] == [
        {"name": "page_size", "reason": "Input should be less than or equal to 100"}
    ]


@pytest.mark.parametrize(
    ("path", "hashed"),
    [
        ("main-AB12cd_3.js", True),
        ("styles-5INURTSO.css", True),
        ("media/font-ZXY12345.woff2", True),
        ("index.html", False),
        ("favicon.svg", False),
        ("main.js", False),
    ],
)
def test_recognises_files_with_a_content_hash(path: str, hashed: bool) -> None:
    # When
    matched = HASHED_FILE.search(path) is not None

    # Then
    assert matched is hashed
