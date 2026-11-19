"""drop the import's file hash

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-19 23:00:00

Every import stored the SHA-256 of its file, which nothing ever read. A downgrade puts
the column back with an empty hash for the imports so far, as their files are not kept.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("employee_import", "file_sha256")


def downgrade() -> None:
    op.add_column(
        "employee_import",
        sa.Column("file_sha256", sa.String(length=64), nullable=False, server_default=""),
    )
    op.alter_column("employee_import", "file_sha256", server_default=None)
