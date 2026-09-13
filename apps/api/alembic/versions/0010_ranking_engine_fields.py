"""Add ranking engine fields to Card

Revision ID: 0010_ranking_engine_fields
Revises: f8665a62be73
Create Date: 2026-09-13 01:25:00.000000

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
    op.add_column('cards', sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('cards', sa.Column('urgency_score', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('cards', sa.Column('freshness_score', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('cards', sa.Column('verification_score', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('cards', sa.Column('personal_relevance_score', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('cards', sa.Column('final_feed_score', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('cards', sa.Column('priority_reason', sa.String(length=512), nullable=False, server_default=''))
    op.add_column('cards', sa.Column('impact_evidence', JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('cards', 'impact_evidence')
    op.drop_column('cards', 'priority_reason')
    op.drop_column('cards', 'final_feed_score')
    op.drop_column('cards', 'personal_relevance_score')
    op.drop_column('cards', 'verification_score')
    op.drop_column('cards', 'freshness_score')
    op.drop_column('cards', 'urgency_score')
    op.drop_column('cards', 'importance_score')
