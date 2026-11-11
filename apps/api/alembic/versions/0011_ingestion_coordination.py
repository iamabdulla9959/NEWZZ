"""Add ingestion requests and leases tables for cross-process coordination

Revision ID: 0011_ingestion_coordination
Revises: 0010_ranking_engine_fields
Create Date: 2026-10-31 12:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import JSON

# revision identifiers, used by Alembic.
revision: str = '0011_ingestion_coordination'
down_revision: Union[str, Sequence[str], None] = '0010_ranking_engine_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("ingestion_requests"):
        op.create_table(
            "ingestion_requests",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("trigger_origin", sa.String(length=64), nullable=False, server_default="manual_api"),
            sa.Column("worker_id", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("result_summary", JSON(), nullable=True),
        )

    if not insp.has_table("ingestion_leases"):
        op.create_table(
            "ingestion_leases",
            sa.Column("lease_name", sa.String(length=64), primary_key=True),
            sa.Column("holder_id", sa.String(length=128), nullable=True),
            sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("ingestion_leases"):
        op.drop_table("ingestion_leases")

    if insp.has_table("ingestion_requests"):
        op.drop_table("ingestion_requests")

