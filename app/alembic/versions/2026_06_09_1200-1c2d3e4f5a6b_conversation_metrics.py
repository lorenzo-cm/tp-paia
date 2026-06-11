"""Conversation metrics

Revision ID: 1c2d3e4f5a6b
Revises: 6f51c0ad8b52
Create Date: 2026-06-09 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "1c2d3e4f5a6b"
down_revision: str | None = "6f51c0ad8b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_metrics",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("lead_quality", sa.String(length=6), nullable=True),
        sa.Column("qualification_reason", sa.String(length=255), nullable=True),
        sa.Column("final_outcome", sa.String(length=8), nullable=True),
        sa.Column("used_human_transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("response_time_min_ms", sa.Integer(), nullable=True),
        sa.Column("response_time_max_ms", sa.Integer(), nullable=True),
        sa.Column("response_time_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_usage", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "lead_quality IN ('low', 'medium', 'high')",
            name="ck_conversation_metrics_lead_quality",
        ),
        sa.CheckConstraint(
            "final_outcome IN ('retained', 'handoff', 'dropped')",
            name="ck_conversation_metrics_final_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id"),
    )
    op.create_index(
        op.f("ix_conversation_metrics_conversation_id"),
        "conversation_metrics",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_metrics_final_outcome"),
        "conversation_metrics",
        ["final_outcome"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_metrics_id"),
        "conversation_metrics",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_metrics_lead_quality"),
        "conversation_metrics",
        ["lead_quality"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_metrics_lead_quality"), table_name="conversation_metrics")
    op.drop_index(op.f("ix_conversation_metrics_id"), table_name="conversation_metrics")
    op.drop_index(op.f("ix_conversation_metrics_final_outcome"), table_name="conversation_metrics")
    op.drop_index(op.f("ix_conversation_metrics_conversation_id"), table_name="conversation_metrics")
    op.drop_table("conversation_metrics")
