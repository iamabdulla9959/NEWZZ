"""enable pgvector extension and convert embedding to vector(768)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Enable pgvector extension in PostgreSQL / Supabase
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        # Alter column type to vector(768)
        op.execute(
            "ALTER TABLE articles ALTER COLUMN embedding TYPE vector(768) USING "
            "CASE WHEN embedding IS NOT NULL THEN embedding::text::vector(768) ELSE NULL END;"
        )
        # Add HNSW cosine similarity index
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_embedding ON articles "
            "USING hnsw (embedding vector_cosine_ops);"
        )
    else:
        # SQLite / local dev: embedding remains JSON
        pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS idx_articles_embedding;")
        op.execute(
            "ALTER TABLE articles ALTER COLUMN embedding TYPE json USING "
            "CASE WHEN embedding IS NOT NULL THEN to_json(embedding) ELSE NULL END;"
        )
        op.execute("DROP EXTENSION IF EXISTS vector;")
    else:
        pass
