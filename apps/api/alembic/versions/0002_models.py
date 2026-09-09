"""create core tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("rss_url", sa.String(1024), nullable=True),
        sa.Column("trust_tier", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "story_clusters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title_hint", sa.String(1024), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("flagged_conflict", sa.Boolean(), nullable=False),
        sa.Column("conflict_notes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("cluster_id", sa.String(36), sa.ForeignKey("story_clusters.id"), nullable=True),
        sa.UniqueConstraint("url", name="uq_articles_url"),
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cluster_id", sa.String(36), sa.ForeignKey("story_clusters.id"), nullable=False),
        sa.Column("headline", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("verified_status", sa.String(32), nullable=False),
        sa.Column("district", sa.String(128), nullable=True),
        sa.Column("state", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "card_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("trust_tier", sa.Integer(), nullable=False),
    )
    op.create_table(
        "review_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id"), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("source_excerpts", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("review_queue")
    op.drop_table("card_sources")
    op.drop_table("cards")
    op.drop_table("articles")
    op.drop_table("story_clusters")
    op.drop_table("sources")
