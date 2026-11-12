"""employee import

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12 21:40:49.770165
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_import",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rows_succeeded", sa.Integer(), nullable=False),
        sa.Column("rows_failed", sa.Integer(), nullable=False),
        sa.Column("rows_created", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("rows_unchanged", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("row_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'partially_succeeded', 'failed')",
            name=op.f("ck_employee_import_status_values"),
        ),
        sa.CheckConstraint(
            "rows_succeeded = rows_created + rows_updated + rows_unchanged",
            name=op.f("ck_employee_import_succeeded_breakdown"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee_import")),
    )


def downgrade() -> None:
    op.drop_table("employee_import")
