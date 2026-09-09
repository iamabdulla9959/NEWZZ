"""add source_type on sources and provider, credits_used on worker_runs

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch_op:
        batch_op.add_column(
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="rss")
        )

    with op.batch_alter_table("worker_runs") as batch_op:
        batch_op.add_column(
            sa.Column("provider", sa.String(length=64), nullable=False, server_default="rss")
        )
        batch_op.add_column(
            sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("worker_runs") as batch_op:
        batch_op.drop_column("credits_used")
        batch_op.drop_column("provider")

    with op.batch_alter_table("sources") as batch_op:
        batch_op.drop_column("source_type")
