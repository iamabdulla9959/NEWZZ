"""add card image fields

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cards") as batch_op:
        batch_op.add_column(sa.Column("image_url", sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column("image_author", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("image_author_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cards") as batch_op:
        batch_op.drop_column("image_author_url")
        batch_op.drop_column("image_author")
        batch_op.drop_column("image_url")
