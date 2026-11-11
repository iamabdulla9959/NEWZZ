"""Enforce NOT NULL constraint on timestamp columns across core models

Revision ID: 0013_enforce_timestamp_not_null
Revises: 0012_lease_fencing_and_retries
Create Date: 2026-11-07 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0013_enforce_timestamp_not_null'
down_revision: Union[str, Sequence[str], None] = '0012_lease_fencing_and_retries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enforce nullable=False on timestamp columns with batch_alter_table for SQLite compatibility
    with op.batch_alter_table("articles") as batch_op:
        batch_op.alter_column("ingested_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())

    with op.batch_alter_table("cards") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())

    with op.batch_alter_table("filtered_out") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())

    with op.batch_alter_table("review_queue") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())

    with op.batch_alter_table("sources") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())

    with op.batch_alter_table("story_clusters") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())

    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())
        batch_op.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())

    with op.batch_alter_table("worker_runs") as batch_op:
        batch_op.alter_column("timestamp", existing_type=sa.DateTime(), nullable=False, server_default=sa.func.now())


def downgrade() -> None:
    with op.batch_alter_table("articles") as batch_op:
        batch_op.alter_column("ingested_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())

    with op.batch_alter_table("cards") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())

    with op.batch_alter_table("filtered_out") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())

    with op.batch_alter_table("review_queue") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())

    with op.batch_alter_table("sources") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())

    with op.batch_alter_table("story_clusters") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())

    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())
        batch_op.alter_column("updated_at", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())

    with op.batch_alter_table("worker_runs") as batch_op:
        batch_op.alter_column("timestamp", existing_type=sa.DateTime(), nullable=True, server_default=sa.func.now())
