"""skill key

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14 14:10:00

Skill names become unique ignoring case, spaces and punctuation, not only case.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _key(name: str) -> str:
    # A frozen copy of app.models.skill_key: a migration must not change with the app.
    spelled = name.casefold().replace("+", "plus").replace("#", "sharp")
    return "".join(character for character in spelled if character.isalnum())


def upgrade() -> None:
    op.add_column("skill", sa.Column("key", sa.String(), nullable=True))
    connection = op.get_bind()
    skills = connection.execute(sa.text("SELECT id, name FROM skill")).all()

    names_by_key: dict[str, list[str]] = {}
    for _, name in skills:
        names_by_key.setdefault(_key(name), []).append(name)
    if clashes := [names for names in names_by_key.values() if len(names) > 1]:
        listed = "; ".join(" = ".join(names) for names in clashes)
        message = f"These skills would become duplicates, rename or remove them first: {listed}"
        raise RuntimeError(message)

    for skill_id, name in skills:
        connection.execute(
            sa.text("UPDATE skill SET key = :key WHERE id = :id"),
            {"key": _key(name), "id": skill_id},
        )
    op.alter_column("skill", "key", nullable=False)
    op.drop_index("uq_skill_name_lower", table_name="skill")
    op.create_unique_constraint(op.f("uq_skill_key"), "skill", ["key"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_skill_key"), "skill", type_="unique")
    op.create_index("uq_skill_name_lower", "skill", [sa.literal_column("lower(name)")], unique=True)
    op.drop_column("skill", "key")
