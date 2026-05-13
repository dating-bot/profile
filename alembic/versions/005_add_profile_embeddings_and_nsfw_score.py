# pyright: reportUnusedCallResult=false
"""Add pgvector embeddings and nsfw_score.

Revision ID: 005
Revises: 004
Create Date: 2026-05-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | Sequence[str] | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.add_column(
        "photos",
        sa.Column("nsfw_score", sa.Float(), nullable=False, server_default=sa.text("0")),
    )

    op.execute(
        sa.text("""
            CREATE TABLE IF NOT EXISTS profile_embeddings (
                id BIGSERIAL PRIMARY KEY,
                profile_id BIGINT NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
                model VARCHAR(128) NOT NULL,
                embedding VECTOR(1536) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """),
    )
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_profile_embeddings_profile_id ON profile_embeddings(profile_id)"))
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_profile_embeddings_embedding_hnsw "
            "ON profile_embeddings USING hnsw (embedding vector_cosine_ops)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_profile_embeddings_embedding_hnsw"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_profile_embeddings_profile_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS profile_embeddings"))
    op.drop_column("photos", "nsfw_score")
