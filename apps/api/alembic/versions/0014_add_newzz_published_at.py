"""Add newzz_published_at column to Card model to separate editorial publication time from original source publication date.

Revision ID: 0014_add_newzz_published_at
Revises: 0013_enforce_timestamp_not_null
Create Date: 2026-11-08 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0014_add_newzz_published_at'
down_revision: Union[str, Sequence[str], None] = '0013_enforce_timestamp_not_null'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_columns = {col["name"] for col in insp.get_columns("cards")}

    if "newzz_published_at" not in existing_columns:
        with op.batch_alter_table("cards") as batch_op:
            batch_op.add_column(sa.Column("newzz_published_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_columns = {col["name"] for col in insp.get_columns("cards")}

    if "newzz_published_at" in existing_columns:
        with op.batch_alter_table("cards") as batch_op:
            batch_op.drop_column("newzz_published_at")
