"""Core database ORM entities matching docs/ARCHITECTURE.md."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class Repository(Base):
    """Tracked GitHub repository."""

    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_indexed_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list["GraphSnapshot"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class GraphSnapshot(Base):
    """Point-in-time dependency graph snapshot for a repository commit."""

    __tablename__ = "graph_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    repository: Mapped[Repository] = relationship(back_populates="snapshots")
    file_nodes: Mapped[list["FileNode"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    dependency_edges: Mapped[list["DependencyEdge"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )
    documents: Mapped[list["SnapshotDocument"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class FileNode(Base):
    """Indexed source file node inside a graph snapshot."""

    __tablename__ = "file_nodes"
    __table_args__ = (
        Index("ix_file_nodes_snapshot_path", "snapshot_id", "path", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("graph_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    module_group: Mapped[str] = mapped_column(String(255), nullable=False, default="root")
    loc: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exports_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSONVariant, nullable=False, default=list
    )
    in_degree: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    out_degree: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot: Mapped[GraphSnapshot] = relationship(back_populates="file_nodes")


class DependencyEdge(Base):
    """Directed import or re-export edge between two file nodes."""

    __tablename__ = "dependency_edges"
    __table_args__ = (
        Index("ix_dependency_edges_snapshot_id", "snapshot_id"),
        Index("ix_dependency_edges_target_node_id", "target_node_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("graph_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False, default="import")
    imported_symbols: Mapped[list[str]] = mapped_column(
        JSONVariant, nullable=False, default=list
    )

    snapshot: Mapped[GraphSnapshot] = relationship(back_populates="dependency_edges")


class SnapshotDocument(Base):
    """Indexed repository Markdown or OpenAPI documentation file for doc-drift detection."""

    __tablename__ = "snapshot_documents"
    __table_args__ = (
        Index("ix_snapshot_documents_snapshot_path", "snapshot_id", "path", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("graph_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped[GraphSnapshot] = relationship(back_populates="documents")


class PRAnalysis(Base):
    """Stored PR blast-radius calculation and grounded AI report."""

    __tablename__ = "pr_analyses"
    __table_args__ = (
        Index("ix_pr_analyses_repository_id", "repository_id"),
        Index("ix_pr_analyses_snapshot_id", "snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("graph_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_title: Mapped[str] = mapped_column(Text, nullable=False)
    changed_files: Mapped[list[str]] = mapped_column(JSONVariant, nullable=False, default=list)
    blast_radius_json: Mapped[dict[str, object]] = mapped_column(
        JSONVariant, nullable=False, default=dict
    )
    ai_report_json: Mapped[dict[str, object] | None] = mapped_column(JSONVariant, nullable=True)
    citation_telemetry_json: Mapped[dict[str, object] | None] = mapped_column(
        JSONVariant, nullable=True
    )
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, default=Decimal("0.000000")
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
