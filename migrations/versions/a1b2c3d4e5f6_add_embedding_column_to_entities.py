# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""add embedding column to entities

Revision ID: a1b2c3d4e5f6
Revises: 3d54bafd6e3f
Create Date: 2026-03-01 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3d54bafd6e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # For PostgreSQL with pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "kg_entities",
        sa.Column("embedding", sa.Text(), nullable=True),
    )
    # On PostgreSQL, alter the column type to vector(1536):
    # ALTER TABLE kg_entities ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536);


def downgrade() -> None:
    op.drop_column("kg_entities", "embedding")
