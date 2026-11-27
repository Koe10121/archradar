"""Add snapshot_documents table for automatic repository doc-drift retrieval.

Revision ID: 0003_add_snapshot_documents
Revises: 0002_add_citation_telemetry
Create Date: 2026-11-27 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_snapshot_documents"
down_revision: str | Sequence[str] | None = "0002_add_citation_telemetry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snapshot_documents",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["graph_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_snapshot_documents_snapshot_path",
        "snapshot_documents",
        ["snapshot_id", "path"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_snapshot_documents_snapshot_path", table_name="snapshot_documents")
    op.drop_table("snapshot_documents")
