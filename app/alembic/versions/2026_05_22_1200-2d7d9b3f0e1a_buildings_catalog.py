"""Buildings catalog

Revision ID: 2d7d9b3f0e1a
Revises: da485244e2ca
Create Date: 2026-05-22 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2d7d9b3f0e1a"
down_revision: Union[str, Sequence[str], None] = "da485244e2ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "buildings",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("information", sa.Text(), nullable=False),
        sa.Column("photos_url", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("videos_url", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "documents_url", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("source_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "extraction_version", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_buildings_id"), "buildings", ["id"], unique=False)
    op.create_index(op.f("ix_buildings_name"), "buildings", ["name"], unique=False)
    op.create_index(
        op.f("ix_buildings_source_url"), "buildings", ["source_url"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_buildings_source_url"), table_name="buildings")
    op.drop_index(op.f("ix_buildings_name"), table_name="buildings")
    op.drop_index(op.f("ix_buildings_id"), table_name="buildings")
    op.drop_table("buildings")
