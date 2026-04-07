# pyright: reportUnusedCallResult=false
"""add latitude longitude to profiles

Revision ID: 002
Revises: 001
Create Date: 2026-04-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("profiles", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "longitude")
    op.drop_column("profiles", "latitude")
