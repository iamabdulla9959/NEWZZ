"""risk review updates: verification rules, translation fields, filtered_out, worker_runs

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update sources & card_sources trust_tier to String
    with op.batch_alter_table("sources") as batch_op:
        batch_op.alter_column("trust_tier", existing_type=sa.Integer(), type_=sa.String(32))

    with op.batch_alter_table("card_sources") as batch_op:
        batch_op.alter_column("trust_tier", existing_type=sa.Integer(), type_=sa.String(32))

    # Add verification_type to cards
    with op.batch_alter_table("cards") as batch_op:
        batch_op.add_column(sa.Column("verification_type", sa.String(32), nullable=True))

    # Add translation and sharding fields to articles
    with op.batch_alter_table("articles") as batch_op:
        batch_op.add_column(sa.Column("original_language", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("original_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("translated_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("translation_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("category", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("district", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("state", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("embedding", sa.JSON(), nullable=True))

    # Create filtered_out table for keyword audit window
    op.create_table(
        "filtered_out",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_article_id", sa.String(36), nullable=False),
        sa.Column("comparison_article_id", sa.String(36), nullable=True),
        sa.Column("shared_keywords_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(255), nullable=False, server_default="insufficient_keyword_overlap"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create worker_runs table for health logging
    op.create_table(
        "worker_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sources_polled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_ingested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0.0"),
    )


def downgrade() -> None:
    op.drop_table("worker_runs")
    op.drop_table("filtered_out")

    with op.batch_alter_table("articles") as batch_op:
        batch_op.drop_column("embedding")
        batch_op.drop_column("state")
        batch_op.drop_column("district")
        batch_op.drop_column("category")
        batch_op.drop_column("translation_confidence")
        batch_op.drop_column("translated_text")
        batch_op.drop_column("original_text")
        batch_op.drop_column("original_language")

    with op.batch_alter_table("cards") as batch_op:
        batch_op.drop_column("verification_type")

    with op.batch_alter_table("card_sources") as batch_op:
        batch_op.alter_column("trust_tier", existing_type=sa.String(32), type_=sa.Integer())

    with op.batch_alter_table("sources") as batch_op:
        batch_op.alter_column("trust_tier", existing_type=sa.String(32), type_=sa.Integer())
