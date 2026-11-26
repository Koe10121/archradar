"""Initial ArchRadar schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("last_indexed_sha", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )

    op.create_table(
        "graph_snapshots",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "file_nodes",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("module_group", sa.String(length=255), nullable=False),
        sa.Column("loc", sa.Integer(), nullable=False),
        sa.Column("exports_json", JSONVariant, nullable=False),
        sa.Column("in_degree", sa.Integer(), nullable=False),
        sa.Column("out_degree", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["graph_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_file_nodes_snapshot_path",
        "file_nodes",
        ["snapshot_id", "path"],
        unique=True,
    )

    op.create_table(
        "dependency_edges",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_node_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("target_node_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("edge_type", sa.String(length=32), nullable=False),
        sa.Column("imported_symbols", JSONVariant, nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["graph_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["file_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["file_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dependency_edges_snapshot_id", "dependency_edges", ["snapshot_id"])
    op.create_index(
        "ix_dependency_edges_target_node_id",
        "dependency_edges",
        ["target_node_id"],
    )

    op.create_table(
        "pr_analyses",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("repository_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("pr_title", sa.Text(), nullable=False),
        sa.Column("changed_files", JSONVariant, nullable=False),
        sa.Column("blast_radius_json", JSONVariant, nullable=False),
        sa.Column("ai_report_json", JSONVariant, nullable=True),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["graph_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pr_analyses_repository_id", "pr_analyses", ["repository_id"])
    op.create_index("ix_pr_analyses_snapshot_id", "pr_analyses", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_pr_analyses_snapshot_id", table_name="pr_analyses")
    op.drop_index("ix_pr_analyses_repository_id", table_name="pr_analyses")
    op.drop_table("pr_analyses")
    op.drop_index("ix_dependency_edges_target_node_id", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_snapshot_id", table_name="dependency_edges")
    op.drop_table("dependency_edges")
    op.drop_index("ix_file_nodes_snapshot_path", table_name="file_nodes")
    op.drop_table("file_nodes")
    op.drop_table("graph_snapshots")
    op.drop_table("repositories")
