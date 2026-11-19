from app.models import Employee, ProficiencyLevel, Skill
from app.services.employees_service import etag
from tests.factories import make_employee

GO = Skill(id=7, name="Go")


def anna(skills: dict[Skill, ProficiencyLevel], **overrides: object) -> Employee:
    fixed = {"last_name": "Schmidt", "email": "anna@example.com", "employee_number": "E-1"}
    return make_employee(skills, id=1, **(fixed | overrides))


def test_the_same_employee_has_the_same_version_however_often_it_is_loaded() -> None:
    # When
    first = etag(anna({GO: ProficiencyLevel.ADVANCED}))
    second = etag(anna({GO: ProficiencyLevel.ADVANCED}))

    # Then
    assert first == second
    assert first.startswith('"') and first.endswith('"')


def test_any_change_the_api_shows_is_a_new_version() -> None:
    # Given
    version = etag(anna({GO: ProficiencyLevel.ADVANCED}))

    # When
    versions = {
        etag(anna({GO: ProficiencyLevel.EXPERT})),
        etag(anna({})),
        etag(anna({GO: ProficiencyLevel.ADVANCED}, job_title="Architect")),
    }

    # Then
    assert version not in versions
    assert len(versions) == 3
