"""departments and locations

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15 22:00:00

Departments and locations become records of their own, which employees refer to, so that
they can be offered for filtering. Spellings that differ only in case, spaces or
punctuation become one, named as most employees spelled it; names without a letter or
digit, such as "-", become no department or location. A downgrade restores the names
in their merged spelling.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("department", "location")


def _key(name: str) -> str:
    # A frozen copy of app.models.name_key: a migration must not change with the app.
    spelled = name.casefold().replace("+", "plus").replace("#", "sharp")
    return "".join(character for character in spelled if character.isalnum())


def upgrade() -> None:
    connection = op.get_bind()
    for table in TABLES:
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
            sa.UniqueConstraint("key", name=f"uq_{table}_key"),
        )
        op.add_column("employee", sa.Column(f"{table}_id", sa.Integer(), nullable=True))

        spellings: dict[str, list[tuple[str, int]]] = {}
        counts = connection.execute(
            sa.text(f"SELECT {table}, count(*) FROM employee WHERE {table} IS NOT NULL GROUP BY 1")
        )
        for name, count in counts:
            if key := _key(name):
                spellings.setdefault(key, []).append((name, count))
        for key, names in spellings.items():
            most_common = min(names, key=lambda spelling: (-spelling[1], spelling[0]))[0]
            new_id = connection.execute(
                sa.text(f"INSERT INTO {table} (name, key) VALUES (:name, :key) RETURNING id"),
                {"name": most_common, "key": key},
            ).scalar_one()
            for name, _ in names:
                connection.execute(
                    sa.text(f"UPDATE employee SET {table}_id = :id WHERE {table} = :name"),
                    {"id": new_id, "name": name},
                )

        op.create_foreign_key(
            f"fk_employee_{table}_id_{table}", "employee", table, [f"{table}_id"], ["id"]
        )
        op.create_index(f"ix_employee_{table}_id", "employee", [f"{table}_id"])
        op.drop_column("employee", table)


def downgrade() -> None:
    for table in TABLES:
        op.add_column("employee", sa.Column(table, sa.String(), nullable=True))
        op.execute(
            f"UPDATE employee SET {table} = {table}.name FROM {table} "
            f"WHERE employee.{table}_id = {table}.id"
        )
        op.drop_index(f"ix_employee_{table}_id", table_name="employee")
        op.drop_constraint(f"fk_employee_{table}_id_{table}", "employee", type_="foreignkey")
        op.drop_column("employee", f"{table}_id")
        op.drop_table(table)
