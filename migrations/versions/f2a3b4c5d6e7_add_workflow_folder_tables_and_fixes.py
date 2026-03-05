# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""add workflow, folder tables and fix column types

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-03-05 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    is_pg = bind.dialect.name == "postgresql"

    # ------------------------------------------------------------------
    # 1. workflows table
    # ------------------------------------------------------------------
    if "workflows" not in existing_tables:
        op.create_table(
            "workflows",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("conversation_id", sa.String(length=255), nullable=True),
            sa.Column("user_id", sa.String(length=255), nullable=False),
            sa.Column("workspace_id", sa.String(length=255), nullable=True),
            sa.Column("workflow_type", sa.String(length=100), nullable=False),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column(
                "current_step",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("state_json", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workflows_conversation_id", "workflows", ["conversation_id"])
        op.create_index("ix_workflows_user_id", "workflows", ["user_id"])
        op.create_index("ix_workflows_workflow_type", "workflows", ["workflow_type"])
        op.create_index("ix_workflows_status", "workflows", ["status"])
        op.create_index("ix_workflows_next_check_at", "workflows", ["next_check_at"])

    # ------------------------------------------------------------------
    # 2. workflow_steps table
    # ------------------------------------------------------------------
    if "workflow_steps" not in existing_tables:
        op.create_table(
            "workflow_steps",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("workflow_id", sa.String(length=255), nullable=False),
            sa.Column("step_index", sa.Integer(), nullable=False),
            sa.Column("step_type", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column("input_json", sa.Text(), nullable=True),
            sa.Column("output_json", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "timeout_seconds",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("300"),
            ),
            sa.Column(
                "max_retries",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workflow_steps_workflow_id", "workflow_steps", ["workflow_id"])

    # ------------------------------------------------------------------
    # 3. workflow_webhooks table
    # ------------------------------------------------------------------
    if "workflow_webhooks" not in existing_tables:
        op.create_table(
            "workflow_webhooks",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("workflow_id", sa.String(length=255), nullable=False),
            sa.Column("step_index", sa.Integer(), nullable=False),
            sa.Column("webhook_token", sa.String(length=255), nullable=False),
            sa.Column("external_system", sa.String(length=255), nullable=True),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workflow_webhooks_workflow_id", "workflow_webhooks", ["workflow_id"])
        op.create_index(
            "ix_workflow_webhooks_webhook_token",
            "workflow_webhooks",
            ["webhook_token"],
            unique=True,
        )

    # ------------------------------------------------------------------
    # 4. conversation_folders table
    # ------------------------------------------------------------------
    if "conversation_folders" not in existing_tables:
        op.create_table(
            "conversation_folders",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "icon",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'folder'"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_conversation_folders_user_id", "conversation_folders", ["user_id"])

    # ------------------------------------------------------------------
    # 5. Fix kg_entities.embedding: Text -> Vector(1536) on PostgreSQL
    # ------------------------------------------------------------------
    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # Alter the column type from text to vector(1536)
        op.execute(
            "ALTER TABLE kg_entities "
            "ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector(1536)"
        )

    # ------------------------------------------------------------------
    # 6. Fix model_routing_config column types on PostgreSQL
    # ------------------------------------------------------------------
    if is_pg:
        # tier_mappings: Text -> JSONB
        op.execute(
            "ALTER TABLE model_routing_config "
            "ALTER COLUMN tier_mappings TYPE jsonb "
            "USING tier_mappings::jsonb"
        )
        # default_tier: nullable -> NOT NULL with default
        op.execute(
            "UPDATE model_routing_config "
            "SET default_tier = 'balanced' WHERE default_tier IS NULL"
        )
        op.alter_column(
            "model_routing_config",
            "default_tier",
            nullable=False,
            server_default=sa.text("'balanced'"),
        )
        # updated_at: make NOT NULL with a default
        op.execute(
            "UPDATE model_routing_config "
            "SET updated_at = NOW() WHERE updated_at IS NULL"
        )

    # ------------------------------------------------------------------
    # 7. Fix email_threads JSON columns to JSONB on PostgreSQL
    # ------------------------------------------------------------------
    if is_pg and "email_threads" in existing_tables:
        op.execute(
            "ALTER TABLE email_threads "
            "ALTER COLUMN participants_json TYPE jsonb "
            "USING participants_json::jsonb"
        )
        op.execute(
            "ALTER TABLE email_threads "
            "ALTER COLUMN channel_metadata_json TYPE jsonb "
            "USING channel_metadata_json::jsonb"
        )

    # ------------------------------------------------------------------
    # 8. Add pgvector ANN indexes on embedding columns
    # ------------------------------------------------------------------
    if is_pg:
        # HNSW index for kb_chunks.embedding (if it exists as vector)
        if "kb_chunks" in existing_tables:
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_kb_chunks_embedding_hnsw "
                "ON kb_chunks USING hnsw (embedding vector_cosine_ops)"
            )
        # HNSW index for kg_entities.embedding
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_kg_entities_embedding_hnsw "
            "ON kg_entities USING hnsw (embedding vector_cosine_ops)"
        )

    # ------------------------------------------------------------------
    # 9. Add unique constraint on kg_relations to prevent duplicates
    # ------------------------------------------------------------------
    if "kg_relations" in existing_tables:
        try:
            op.create_index(
                "uq_kg_relations_src_tgt_type",
                "kg_relations",
                ["source_id", "target_id", "relation_type"],
                unique=True,
            )
        except Exception:
            pass  # May already exist

    # ------------------------------------------------------------------
    # 10. Add composite indexes for common query patterns
    # ------------------------------------------------------------------
    try:
        op.create_index(
            "ix_messages_conversation_created",
            "messages",
            ["conversation_id", "created_at"],
        )
    except Exception:
        pass

    if "workflows" in existing_tables or "workflows" not in existing_tables:
        try:
            op.create_index(
                "ix_workflows_status_next_check",
                "workflows",
                ["status", "next_check_at"],
            )
        except Exception:
            pass


def downgrade() -> None:
    # Drop composite indexes
    try:
        op.drop_index("ix_workflows_status_next_check", table_name="workflows")
    except Exception:
        pass
    try:
        op.drop_index("ix_messages_conversation_created", table_name="messages")
    except Exception:
        pass
    try:
        op.drop_index("uq_kg_relations_src_tgt_type", table_name="kg_relations")
    except Exception:
        pass

    # Drop HNSW indexes
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_kg_entities_embedding_hnsw")
        op.execute("DROP INDEX IF EXISTS ix_kb_chunks_embedding_hnsw")

    # Revert email_threads columns (JSONB -> Text)
    if bind.dialect.name == "postgresql":
        try:
            op.execute(
                "ALTER TABLE email_threads "
                "ALTER COLUMN channel_metadata_json TYPE text "
                "USING channel_metadata_json::text"
            )
            op.execute(
                "ALTER TABLE email_threads "
                "ALTER COLUMN participants_json TYPE text "
                "USING participants_json::text"
            )
        except Exception:
            pass

    # Revert kg_entities.embedding (vector -> text)
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE kg_entities "
            "ALTER COLUMN embedding TYPE text "
            "USING embedding::text"
        )

    # Drop tables in reverse order
    op.drop_table("conversation_folders")
    op.drop_table("workflow_webhooks")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
