# pyright: reportUnusedCallResult=false
"""Add is_active and boost_expires_at to profiles.

Revision ID: 004
Revises: 003
Create Date: 2026-04-23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "profiles",
        sa.Column("boost_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_profiles_is_active", "profiles", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_profiles_is_active", table_name="profiles")
    op.drop_column("profiles", "boost_expires_at")
    op.drop_column("profiles", "is_active")
