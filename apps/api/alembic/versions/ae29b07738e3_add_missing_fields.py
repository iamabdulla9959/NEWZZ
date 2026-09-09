"""Add missing fields

Revision ID: ae29b07738e3
Revises: 1fe485538d78
Create Date: 2026-09-09 00:30:33.255292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae29b07738e3'
down_revision: Union[str, Sequence[str], None] = '1fe485538d78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('cards') as batch_op:
        batch_op.add_column(sa.Column('priority_score', sa.Integer(), server_default='5', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('cards') as batch_op:
        batch_op.drop_column('priority_score')
