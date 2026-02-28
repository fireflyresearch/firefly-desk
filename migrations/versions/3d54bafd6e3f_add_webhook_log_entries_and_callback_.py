# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""add webhook_log_entries and callback_deliveries tables

Revision ID: 3d54bafd6e3f
Revises: b3c4d5e6f7a8
Create Date: 2026-02-28 19:28:04.006267
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision: str = '3d54bafd6e3f'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_log_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("from_address", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("payload_preview", sa.Text(), nullable=False),
        sa.Column("processing_ms", sa.Float(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_log_entries_provider"), "webhook_log_entries", ["provider"], unique=False)
    op.create_index(op.f("ix_webhook_log_entries_status"), "webhook_log_entries", ["status"], unique=False)
    op.create_index(op.f("ix_webhook_log_entries_created_at"), "webhook_log_entries", ["created_at"], unique=False)

    op.create_table(
        "callback_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("callback_id", sa.String(length=36), nullable=False),
        sa.Column("event", sa.String(length=100), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.Text(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_callback_deliveries_callback_id"), "callback_deliveries", ["callback_id"], unique=False)
    op.create_index(op.f("ix_callback_deliveries_event"), "callback_deliveries", ["event"], unique=False)
    op.create_index(op.f("ix_callback_deliveries_status"), "callback_deliveries", ["status"], unique=False)
    op.create_index(op.f("ix_callback_deliveries_created_at"), "callback_deliveries", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_callback_deliveries_created_at"), table_name="callback_deliveries")
    op.drop_index(op.f("ix_callback_deliveries_status"), table_name="callback_deliveries")
    op.drop_index(op.f("ix_callback_deliveries_event"), table_name="callback_deliveries")
    op.drop_index(op.f("ix_callback_deliveries_callback_id"), table_name="callback_deliveries")
    op.drop_table("callback_deliveries")

    op.drop_index(op.f("ix_webhook_log_entries_created_at"), table_name="webhook_log_entries")
    op.drop_index(op.f("ix_webhook_log_entries_status"), table_name="webhook_log_entries")
    op.drop_index(op.f("ix_webhook_log_entries_provider"), table_name="webhook_log_entries")
    op.drop_table("webhook_log_entries")
