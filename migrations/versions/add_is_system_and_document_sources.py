# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""add is_system flag and document_sources table

Revision ID: a1b2c3d4e5f6
Revises: d21bc0582e47
Create Date: 2026-02-26 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d21bc0582e47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "document_sources",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("auth_method", sa.String(20), nullable=False),
        sa.Column("config_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("sync_cron", sa.String(100), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("document_sources")
    op.drop_column("workspaces", "is_system")
