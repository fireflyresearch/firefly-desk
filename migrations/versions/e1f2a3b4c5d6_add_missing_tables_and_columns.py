# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""add missing tables, columns, and indexes

Revision ID: e1f2a3b4c5d6
Revises: c5d6e7f8a9b0
Create Date: 2026-03-05 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # ------------------------------------------------------------------
    # 1. system_tags
    # ------------------------------------------------------------------
    if "system_tags" not in existing_tables:
        op.create_table(
            "system_tags",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("color", sa.String(length=7), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    # ------------------------------------------------------------------
    # 2. system_tag_associations
    # ------------------------------------------------------------------
    if "system_tag_associations" not in existing_tables:
        op.create_table(
            "system_tag_associations",
            sa.Column("system_id", sa.String(length=255), nullable=False),
            sa.Column("tag_id", sa.String(length=255), nullable=False),
            sa.PrimaryKeyConstraint("system_id", "tag_id"),
        )

    # ------------------------------------------------------------------
    # 3. system_documents
    # ------------------------------------------------------------------
    if "system_documents" not in existing_tables:
        op.create_table(
            "system_documents",
            sa.Column("system_id", sa.String(length=255), nullable=False),
            sa.Column("document_id", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=50), nullable=False, server_default=sa.text("'reference'")),
            sa.PrimaryKeyConstraint("system_id", "document_id"),
        )

    # ------------------------------------------------------------------
    # 4. notification_dismissals
    # ------------------------------------------------------------------
    if "notification_dismissals" not in existing_tables:
        op.create_table(
            "notification_dismissals",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("notification_id", sa.String(length=255), nullable=False),
            sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_notification_dismissals_notification_id"),
            "notification_dismissals",
            ["notification_id"],
            unique=True,
        )

    # ------------------------------------------------------------------
    # 5. email_threads
    # ------------------------------------------------------------------
    if "email_threads" not in existing_tables:
        op.create_table(
            "email_threads",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("conversation_id", sa.String(length=255), nullable=False),
            sa.Column("email_message_id", sa.String(length=500), nullable=False),
            sa.Column("thread_root_id", sa.String(length=500), nullable=True),
            sa.Column("subject", sa.Text(), nullable=True),
            sa.Column("participants_json", sa.Text(), nullable=True),
            sa.Column("channel_metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_email_threads_conversation_id"),
            "email_threads",
            ["conversation_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_email_threads_email_message_id"),
            "email_threads",
            ["email_message_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_email_threads_thread_root_id"),
            "email_threads",
            ["thread_root_id"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 6. model_routing_config
    # ------------------------------------------------------------------
    if "model_routing_config" not in existing_tables:
        op.create_table(
            "model_routing_config",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("classifier_model", sa.String(length=255), nullable=True),
            sa.Column("default_tier", sa.String(length=50), nullable=True),
            sa.Column("tier_mappings", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # ------------------------------------------------------------------
    # 7. dead_letter_entries
    # ------------------------------------------------------------------
    if "dead_letter_entries" not in existing_tables:
        op.create_table(
            "dead_letter_entries",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("source_type", sa.String(length=50), nullable=False),
            sa.Column("source_id", sa.String(length=255), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    # ------------------------------------------------------------------
    # 8. cache_entries
    # ------------------------------------------------------------------
    if "cache_entries" not in existing_tables:
        op.create_table(
            "cache_entries",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("namespace", sa.String(length=50), nullable=False),
            sa.Column("cache_key", sa.String(length=255), nullable=False),
            sa.Column("value_json", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("namespace", "cache_key", name="uq_cache_ns_key"),
        )
        op.create_index(
            op.f("ix_cache_entries_expires_at"),
            "cache_entries",
            ["expires_at"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 9. Column: conversations.channel
    # ------------------------------------------------------------------
    try:
        op.add_column(
            "conversations",
            sa.Column(
                "channel",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'chat'"),
            ),
        )
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 10. Columns on workflow_steps: timeout_seconds, max_retries,
    #     retry_count
    #     NOTE: workflow_steps table is now created by migration
    #     f2a3b4c5d6e7 with these columns included.  The ADD COLUMN
    #     calls below are kept for backwards compatibility with
    #     deployments that already have a workflow_steps table.
    # ------------------------------------------------------------------
    if "workflow_steps" in existing_tables:
        try:
            op.add_column(
                "workflow_steps",
                sa.Column(
                    "timeout_seconds",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("300"),
                ),
            )
        except Exception:
            pass

        try:
            op.add_column(
                "workflow_steps",
                sa.Column(
                    "max_retries",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )
        except Exception:
            pass

        try:
            op.add_column(
                "workflow_steps",
                sa.Column(
                    "retry_count",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 11. Index: ix_kb_documents_status
    # ------------------------------------------------------------------
    try:
        op.create_index(
            op.f("ix_kb_documents_status"),
            "kb_documents",
            ["status"],
            unique=False,
        )
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 12. Index: ix_conversations_deleted_at
    # ------------------------------------------------------------------
    try:
        op.create_index(
            op.f("ix_conversations_deleted_at"),
            "conversations",
            ["deleted_at"],
            unique=False,
        )
    except Exception:
        pass


def downgrade() -> None:
    # Reverse order: indexes, columns, then tables.

    # 12. Drop index ix_conversations_deleted_at
    try:
        op.drop_index(op.f("ix_conversations_deleted_at"), table_name="conversations")
    except Exception:
        pass

    # 11. Drop index ix_kb_documents_status
    try:
        op.drop_index(op.f("ix_kb_documents_status"), table_name="kb_documents")
    except Exception:
        pass

    # 10. Drop workflow_steps columns
    try:
        op.drop_column("workflow_steps", "retry_count")
    except Exception:
        pass
    try:
        op.drop_column("workflow_steps", "max_retries")
    except Exception:
        pass
    try:
        op.drop_column("workflow_steps", "timeout_seconds")
    except Exception:
        pass

    # 9. Drop conversations.channel
    try:
        op.drop_column("conversations", "channel")
    except Exception:
        pass

    # 8. cache_entries
    try:
        op.drop_index(op.f("ix_cache_entries_expires_at"), table_name="cache_entries")
    except Exception:
        pass
    op.drop_table("cache_entries")

    # 7. dead_letter_entries
    op.drop_table("dead_letter_entries")

    # 6. model_routing_config
    op.drop_table("model_routing_config")

    # 5. email_threads
    try:
        op.drop_index(op.f("ix_email_threads_thread_root_id"), table_name="email_threads")
    except Exception:
        pass
    try:
        op.drop_index(op.f("ix_email_threads_email_message_id"), table_name="email_threads")
    except Exception:
        pass
    try:
        op.drop_index(op.f("ix_email_threads_conversation_id"), table_name="email_threads")
    except Exception:
        pass
    op.drop_table("email_threads")

    # 4. notification_dismissals
    try:
        op.drop_index(
            op.f("ix_notification_dismissals_notification_id"),
            table_name="notification_dismissals",
        )
    except Exception:
        pass
    op.drop_table("notification_dismissals")

    # 3. system_documents
    op.drop_table("system_documents")

    # 2. system_tag_associations
    op.drop_table("system_tag_associations")

    # 1. system_tags
    op.drop_table("system_tags")
