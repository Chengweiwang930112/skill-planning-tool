import pytest

from app.models import Department, Location, ProficiencyLevel, Skill, name_key


def test_proficiency_levels_are_ordered() -> None:
    # When
    levels = sorted(ProficiencyLevel, reverse=True)

    # Then
    assert levels == [
        ProficiencyLevel.EXPERT,
        ProficiencyLevel.ADVANCED,
        ProficiencyLevel.INTERMEDIATE,
        ProficiencyLevel.BEGINNER,
    ]


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Node.js", "nodejs"),
        ("node js", "nodejs"),
        ("CI/CD", "cicd"),
        ("C", "c"),
        ("C++", "cplusplus"),
        ("C#", "csharp"),
        ("Größe", "grösse"),
    ],
)
def test_a_skill_key_ignores_case_spaces_and_punctuation_but_not_plus_or_sharp(
    name: str, key: str
) -> None:
    # When
    result = name_key(name)

    # Then
    assert result == key


def test_a_skill_derives_its_key_from_its_name() -> None:
    # Given
    skill = Skill(name="Node.js")

    # When
    skill.name = "Kubernetes (K8s)"

    # Then
    assert skill.key == "kubernetesk8s"


@pytest.mark.parametrize("model", [Department, Location])
def test_departments_and_locations_are_keyed_like_skills(
    model: type[Department] | type[Location],
) -> None:
    # When
    entry = model(name="Smart  Infrastructure (SI)")

    # Then
    assert entry.key == "smartinfrastructuresi"
