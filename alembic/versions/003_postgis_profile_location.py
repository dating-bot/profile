# pyright: reportUnusedCallResult=false
"""PostGIS geography for profile location (replaces float lat/lon).

Revision ID: 003
Revises: 002
Create Date: 2026-04-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
    op.execute(
        sa.text("""
            ALTER TABLE profiles
            ADD COLUMN location geography(Point, 4326)
        """),
    )
    op.execute(
        sa.text("""
            UPDATE profiles SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """),
    )
    op.drop_column("profiles", "latitude")
    op.drop_column("profiles", "longitude")
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_profiles_location ON profiles USING GIST (location)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_profiles_location"))
    op.add_column("profiles", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("profiles", sa.Column("longitude", sa.Float(), nullable=True))
    op.execute(
        sa.text("""
            UPDATE profiles SET
                latitude = ST_Y(location::geometry),
                longitude = ST_X(location::geometry)
            WHERE location IS NOT NULL
        """),
    )
    op.drop_column("profiles", "location")
