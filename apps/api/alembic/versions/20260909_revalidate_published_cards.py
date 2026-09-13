"""Hold legacy published cards that fail current summary quality gates.

Revision ID: 20260909_revalidate_published_cards
Revises: f8665a62be73
Create Date: 2026-09-09
"""
from __future__ import annotations

import re
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260909_revalidate_published_cards"
down_revision: Union[str, Sequence[str], None] = "f8665a62be73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def upgrade() -> None:
    bind = op.get_bind()
    cards = sa.table(
        "cards",
        sa.column("id", sa.String()),
        sa.column("summary", sa.Text()),
        sa.column("verified_status", sa.String()),
        sa.column("published_at", sa.DateTime()),
    )
    review_queue = sa.table(
        "review_queue",
        sa.column("id", sa.String()),
        sa.column("card_id", sa.String()),
        sa.column("reasons", sa.JSON()),
        sa.column("source_excerpts", sa.Text()),
        sa.column("status", sa.String()),
    )

    rows = bind.execute(
        sa.select(cards.c.id, cards.c.summary).where(cards.c.verified_status == "published")
    )
    for card_id, summary in rows:
        count = _word_count(summary or "")
        if 150 <= count <= 200:
            continue
        bind.execute(
            cards.update()
            .where(cards.c.id == card_id)
            .values(verified_status="pending_review", published_at=None)
        )
        bind.execute(
            review_queue.insert().values(
                id=str(uuid.uuid4()),
                card_id=card_id,
                reasons=[f"legacy_summary_word_count:{count}"],
                source_excerpts="",
                status="pending",
            )
        )


def downgrade() -> None:
    # Legacy cards cannot be safely republished automatically after review state changes.
    pass
