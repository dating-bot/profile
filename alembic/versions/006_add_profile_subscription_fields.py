# pyright: reportUnusedCallResult=false
"""Add subscription fields to profiles.

Revision ID: 006
Revises: 005
Create Date: 2026-05-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | Sequence[str] | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("subscription_tier", sa.String(length=32), nullable=False, server_default="free"),
    )
    op.add_column(
        "profiles",
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("last_telegram_payment_charge_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("last_provider_payment_charge_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("last_invoice_payload", sa.Text(), nullable=True),
    )
    op.create_index("ix_profiles_subscription_tier", "profiles", ["subscription_tier"])
    op.create_index("ix_profiles_subscription_expires_at", "profiles", ["subscription_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_profiles_subscription_expires_at", table_name="profiles")
    op.drop_index("ix_profiles_subscription_tier", table_name="profiles")
    op.drop_column("profiles", "last_invoice_payload")
    op.drop_column("profiles", "last_provider_payment_charge_id")
    op.drop_column("profiles", "last_telegram_payment_charge_id")
    op.drop_column("profiles", "subscription_expires_at")
    op.drop_column("profiles", "subscription_tier")
