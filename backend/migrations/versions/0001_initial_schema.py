"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-12 20:02:52.584969
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_number", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("job_title", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employee")),
        sa.UniqueConstraint("email", name=op.f("uq_employee_email")),
        sa.UniqueConstraint("employee_number", name=op.f("uq_employee_employee_number")),
    )
    op.create_table(
        "skill",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill")),
    )
    op.create_index("uq_skill_name_lower", "skill", [sa.literal_column("lower(name)")], unique=True)
    op.create_table(
        "employee_skill",
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("level BETWEEN 1 AND 4", name=op.f("ck_employee_skill_level_range")),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employee.id"],
            name=op.f("fk_employee_skill_employee_id_employee"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_employee_skill_skill_id_skill"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("employee_id", "skill_id", name=op.f("pk_employee_skill")),
    )
    op.create_index(
        "ix_employee_skill_skill_id_level", "employee_skill", ["skill_id", "level"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_employee_skill_skill_id_level", table_name="employee_skill")
    op.drop_table("employee_skill")
    op.drop_index("uq_skill_name_lower", table_name="skill")
    op.drop_table("skill")
    op.drop_table("employee")
