"""Pydantic schemas for repository indexing and graph retrieval."""

from datetime import datetime
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
    start_line: int | None = None
    end_line: int | None = None


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
    is_test: bool = False


class GraphEdgeDTO(BaseModel):
    """Directed dependency edge between two graph file nodes."""

    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    source_path: str
    target_path: str
    edge_type: str
    imported_symbols: list[str] = Field(default_factory=list)


class CycleFindingDTO(BaseModel):
    """Circular dependency loop detected via Tarjan Strongly Connected Components."""

    cycle_paths: list[str]
    length: int
    severity: Literal["warning", "high"]


class HotspotFindingDTO(BaseModel):
    """High-coupling or single-point-of-failure module identified deterministically."""

    path: str
    module_group: str
    in_degree: int
    out_degree: int
    loc: int
    has_tests: bool
    touches_sensitive_boundary: bool
    reason: str


class LayerViolationDTO(BaseModel):
    """Upward architectural dependency violating clean layering."""

    source_path: str
    target_path: str
    source_layer: str
    target_layer: str
    imported_symbols: list[str] = Field(default_factory=list)
    reason: str


class ArchitectureHealthDTO(BaseModel):
    """Zero-AI deterministic structural health summary for a graph snapshot."""

    health_score: int = Field(ge=0, le=100)
    grade: Literal["healthy", "watch", "at_risk"]
    cycle_count: int
    layer_violation_count: int
    hotspot_count: int
    untested_hub_count: int
    cycles: list[CycleFindingDTO] = Field(default_factory=list)
    hotspots: list[HotspotFindingDTO] = Field(default_factory=list)
    layer_violations: list[LayerViolationDTO] = Field(default_factory=list)


class GraphResponse(BaseModel):
    """Full repository dependency graph payload."""

    repository_id: UUID
    snapshot_id: UUID
    commit_sha: str
    file_count: int
    edge_count: int
    nodes: list[GraphNodeDTO]
    edges: list[GraphEdgeDTO]
    arch_health: ArchitectureHealthDTO | None = None


class GitHubPRSummaryDTO(BaseModel):
    """Summary of an open or recent Pull Request on a GitHub repository."""

    number: int
    title: str
    state: str
    author: str
    html_url: str
    updated_at: str
    draft: bool = False


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
