"""Add lease generation fencing and request retry columns

Revision ID: 0012_lease_fencing_and_retries
Revises: 0011_ingestion_coordination
Create Date: 2026-10-31 13:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0012_lease_fencing_and_retries'
down_revision: Union[str, Sequence[str], None] = '0011_ingestion_coordination'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("ingestion_leases"):
        lease_cols = {c["name"] for c in insp.get_columns("ingestion_leases")}
        if "lease_generation" not in lease_cols:
            op.add_column(
                "ingestion_leases",
                sa.Column("lease_generation", sa.Integer(), nullable=False, server_default="1"),
            )

    if insp.has_table("ingestion_requests"):
        req_cols = {c["name"] for c in insp.get_columns("ingestion_requests")}
        if "lease_generation" not in req_cols:
            op.add_column(
                "ingestion_requests",
                sa.Column("lease_generation", sa.Integer(), nullable=True),
            )
        if "attempt_count" not in req_cols:
            op.add_column(
                "ingestion_requests",
                sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            )
        if "last_heartbeat_at" not in req_cols:
            op.add_column(
                "ingestion_requests",
                sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # In SQLite, dropping columns is only supported in SQLite 3.35.0+ and batch mode
    # For safety across DB engines:
    try:
        with op.batch_alter_table("ingestion_requests") as batch_op:
            batch_op.drop_column("last_heartbeat_at")
            batch_op.drop_column("attempt_count")
            batch_op.drop_column("lease_generation")
    except Exception:
        pass

    try:
        with op.batch_alter_table("ingestion_leases") as batch_op:
            batch_op.drop_column("lease_generation")
    except Exception:
        pass

