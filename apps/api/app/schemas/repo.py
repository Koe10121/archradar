"""Pydantic schemas for repository indexing and graph retrieval."""

from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class RepoIndexRequest(BaseModel):
    """Request body for POST /api/repos/index."""

    repo_url: str | None = None
    local_path: str | None = None
    branch: str | None = None
    is_demo: bool = False

    @model_validator(mode="after")
    def _validate_source(self) -> "RepoIndexRequest":
        has_url = bool(self.repo_url and self.repo_url.strip())
        has_local = bool(self.local_path and self.local_path.strip())
        if not has_url and not has_local:
            raise ValueError("Either repo_url or local_path must be provided.")
        if has_local and self.local_path is not None:
            resolved = Path(self.local_path).resolve()
            if not resolved.is_dir():
                raise ValueError(f"local_path does not exist or is not a directory: {resolved}")
        return self


class RepoIndexResponse(BaseModel):
    """Response returned after indexing a repository snapshot."""

    repository_id: UUID
    snapshot_id: UUID
    commit_sha: str
    status: str
    file_count: int
    edge_count: int


class RepositorySummary(BaseModel):
    """Repository summary with latest indexed snapshot statistics."""

    id: UUID
    owner: str
    name: str
    url: str
    default_branch: str
    is_demo: bool
    last_indexed_sha: str | None
    latest_snapshot_id: UUID | None
    file_count: int
    edge_count: int
    created_at: datetime


class ExportedSymbolDTO(BaseModel):
    """Exported symbol metadata attached to a graph file node."""

    name: str
    kind: str
    signature: str


class GraphNodeDTO(BaseModel):
    """Graph file node returned for React Flow visualization."""

    id: UUID
    path: str
    language: str
    module_group: str
    loc: int
    exports: list[ExportedSymbolDTO] = Field(default_factory=list)
    in_degree: int
    out_degree: int


class GraphEdgeDTO(BaseModel):
    """Directed dependency edge between two graph file nodes."""

    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    source_path: str
    target_path: str
    edge_type: str
    imported_symbols: list[str] = Field(default_factory=list)


class GraphResponse(BaseModel):
    """Full repository dependency graph payload."""

    repository_id: UUID
    snapshot_id: UUID
    commit_sha: str
    file_count: int
    edge_count: int
    nodes: list[GraphNodeDTO]
    edges: list[GraphEdgeDTO]


class SnapshotSummary(BaseModel):
    """Summary metadata for a single historical GraphSnapshot."""

    id: UUID
    repository_id: UUID
    commit_sha: str
    file_count: int
    edge_count: int
    status: str
    created_at: datetime


class SnapshotDiffEdgeDTO(BaseModel):
    """Added or removed directed dependency edge between two snapshots."""

    source_path: str
    target_path: str
    edge_type: str
    imported_symbols: list[str] = Field(default_factory=list)


class CentralityDeltaDTO(BaseModel):
    """In-degree and out-degree delta for a file across two snapshots."""

    path: str
    module_group: str
    language: str
    from_in_degree: int
    to_in_degree: int
    in_degree_delta: int
    from_out_degree: int
    to_out_degree: int
    out_degree_delta: int
    status: Literal["added", "removed", "changed"]


class SnapshotDiffResponse(BaseModel):
    """Architectural diff comparing two GraphSnapshots of a repository."""

    repository_id: UUID
    from_snapshot: SnapshotSummary
    to_snapshot: SnapshotSummary
    added_files: list[str]
    removed_files: list[str]
    added_edges: list[SnapshotDiffEdgeDTO]
    removed_edges: list[SnapshotDiffEdgeDTO]
    centrality_deltas: list[CentralityDeltaDTO]
    file_count_delta: int
    edge_count_delta: int
