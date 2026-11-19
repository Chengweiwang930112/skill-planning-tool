from pathlib import Path

from scripts.add_skills import read_names


def test_reads_one_name_per_line_skipping_blanks_and_comments(tmp_path: Path) -> None:
    # Given
    file = tmp_path / "skills.txt"
    file.write_text("\ufeff# Cloud\n  Kubernetes \n\nAWS\n", encoding="utf-8")

    # When
    names = read_names(file)

    # Then
    assert names == ["Kubernetes", "AWS"]


def test_the_starter_catalogue_has_44_distinct_skills() -> None:
    # When
    names = read_names(Path(__file__).parents[3] / "samples" / "skills.txt")

    # Then
    assert len(names) == len(set(names)) == 44
