"""Add ranking engine fields to Card

Revision ID: 0010_ranking_engine_fields
Revises: 20260909_revalidate_published_cards
Create Date: 2026-09-13 01:25:00.000000

MIGRATION ROLLBACK SAFETY NOTICE:
Automated downgrade of this revision is NOT considered safe in production.
Because ranking engine columns may have pre-existed in historical databases
prior to Alembic reconciliation, Alembic cannot determine whether columns were
pre-existing or newly provisioned by this migration. In production, rolling back
must be executed by restoring from a verified pre-migration database backup,
never by running 'alembic downgrade -1'.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import JSON

# revision identifiers, used by Alembic.
revision: str = '0010_ranking_engine_fields'
down_revision: Union[str, Sequence[str], None] = '20260909_revalidate_published_cards'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_columns = {col["name"] for col in insp.get_columns("cards")}

    columns = [
        ("importance_score", sa.Column("importance_score", sa.Float(), nullable=False, server_default="0.0")),
        ("urgency_score", sa.Column("urgency_score", sa.Float(), nullable=False, server_default="0.0")),
        ("freshness_score", sa.Column("freshness_score", sa.Float(), nullable=False, server_default="0.0")),
        ("verification_score", sa.Column("verification_score", sa.Float(), nullable=False, server_default="0.0")),
        ("personal_relevance_score", sa.Column("personal_relevance_score", sa.Float(), nullable=False, server_default="0.0")),
        ("final_feed_score", sa.Column("final_feed_score", sa.Float(), nullable=False, server_default="0.0")),
        ("priority_reason", sa.Column("priority_reason", sa.String(length=512), nullable=False, server_default="")),
        ("impact_evidence", sa.Column("impact_evidence", JSON(), nullable=True)),
    ]

    for col_name, col_obj in columns:
        if col_name not in existing_columns:
            op.add_column("cards", col_obj)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_columns = {col["name"] for col in insp.get_columns("cards")}

    columns_to_drop = [
        "impact_evidence",
        "priority_reason",
        "final_feed_score",
        "personal_relevance_score",
        "verification_score",
        "freshness_score",
        "urgency_score",
        "importance_score",
    ]

    for col_name in columns_to_drop:
        if col_name in existing_columns:
            op.drop_column("cards", col_name)
