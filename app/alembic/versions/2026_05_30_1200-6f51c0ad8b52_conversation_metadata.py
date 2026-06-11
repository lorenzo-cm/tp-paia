"""Conversation metadata

Revision ID: 6f51c0ad8b52
Revises: 2d7d9b3f0e1a
Create Date: 2026-05-30 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "6f51c0ad8b52"
down_revision: str | None = "2d7d9b3f0e1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("metadata", sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("conversations", "metadata")
