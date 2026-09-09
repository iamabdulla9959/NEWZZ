"""add user_preferences table and objective_score on cards

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import JSON

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to cards
    with op.batch_alter_table("cards") as batch_op:
        batch_op.add_column(
            sa.Column("objective_score", sa.Float(), nullable=False, server_default="0.0")
        )
        batch_op.add_column(
            sa.Column("impact_keywords_count", sa.Integer(), nullable=False, server_default="0")
        )

    # 2. Create user_preferences table
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("category_order", JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_user_preferences_device_id", "user_preferences", ["device_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_preferences_device_id", table_name="user_preferences")
    op.drop_table("user_preferences")

    with op.batch_alter_table("cards") as batch_op:
        batch_op.drop_column("impact_keywords_count")
        batch_op.drop_column("objective_score")
