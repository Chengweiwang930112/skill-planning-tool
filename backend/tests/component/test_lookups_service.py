from unittest.mock import MagicMock

from app.models import Department, Location
from app.schemas import NameQuery
from app.services.lookups_service import ids_by_key, list_names
from tests.component.conftest import sql


def test_lists_names_alphabetically_and_counts_all_matches(session: MagicMock) -> None:
    # Given
    mobility = Department(id=3, name="Mobility")
    session.scalar.return_value = 7
    session.scalars.return_value.all.return_value = [mobility]

    # When
    rows, total = list_names(session, Department, NameQuery(q="Mob.", page=2, page_size=5))

    # Then
    assert (rows, total) == ([mobility], 7)
    statement = sql(session.scalars.call_args.args[0])
    assert "department.key LIKE '%' || 'mob' || '%' ESCAPE '/'" in statement
    assert "ORDER BY lower(department.name) LIMIT 5 OFFSET 5" in statement


def test_adds_each_new_name_once_in_its_first_spelling(session: MagicMock) -> None:
    # Given
    session.execute.side_effect = [None, [("mobility", 3), ("digitalindustries", 4)]]

    # When
    ids = ids_by_key(session, Department, ["Mobility", "mobility", None, "Digital Industries"])

    # Then
    assert ids == {"mobility": 3, "digitalindustries": 4}
    insert, lookup = (sql(call.args[0]) for call in session.execute.call_args_list)
    assert insert == (
        "INSERT INTO department (name, key) VALUES ('Mobility', 'mobility'), "
        "('Digital Industries', 'digitalindustries') ON CONFLICT (key) DO NOTHING"
    )
    assert lookup.startswith("SELECT department.key, department.id FROM department")


def test_names_without_letters_or_digits_are_no_location(session: MagicMock) -> None:
    # When
    ids = ids_by_key(session, Location, ["-", "  ", None])

    # Then
    assert ids == {}
    session.execute.assert_not_called()
