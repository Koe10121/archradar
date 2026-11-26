"""Pydantic schemas for deterministic blast-radius and grounded AI PR reports."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

RiskLevel = Literal["low", "medium", "high", "critical"]


class ImpactedFlow(BaseModel):
    """A downstream execution or API flow impacted by a PR."""

    title: str
    severity: RiskLevel
    entry_file: str
    affected_files: list[str]
    explanation: str
    suggested_test: str


class DocDriftAlert(BaseModel):
    """Detected documentation staleness with a suggested Markdown patch."""

    doc_file: str
    section: str
    reason: str
    suggested_markdown_patch: str


class BlastRadiusReport(BaseModel):
    """Strict structured LLM output matching docs/ARCHITECTURE.md."""

    overall_risk: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
    executive_summary: str
    breaking_change_detected: bool
    impacted_flows: list[ImpactedFlow]
    doc_drift_alerts: list[DocDriftAlert]
    reviewer_checklist: list[str]


class ImpactedEdgeDetail(BaseModel):
    """Edge traversed during reverse-BFS blast-radius calculation."""

    source: str
    target: str
    edge_type: str
    imported_symbols: list[str]
    symbol_match: bool


class BlastRadiusResult(BaseModel):
    """Deterministic blast-radius output computed prior to any LLM call."""

    direct: list[str]
    hop_1: list[str]
    hop_2: list[str]
    hop_3: list[str]
    score: int = Field(ge=0, le=100)
    deterministic_risk: RiskLevel
    max_in_degree: int
    sensitive_boundaries_touched: list[str]
    symbol_matched_files: list[str]
    impacted_edges: list[ImpactedEdgeDetail]


class CitationValidationTelemetry(BaseModel):
    """Telemetry recorded by the Post-LLM Citation Verification Gate."""

    total_cited_paths: int
    valid_cited_paths: int
    hallucination_caught: int
    stripped_paths: list[str]


class AnalyzePRRequest(BaseModel):
    """Request body for POST /api/repos/{repo_id}/analyze-pr."""

    pr_url: str | None = None
    raw_diff: str | None = None
    pr_title: str = "Ad-hoc PR Analysis"
    pr_description: str = ""
    pr_number: int | None = None
    doc_context: dict[str, str] = Field(default_factory=dict)
    run_ai: bool = True

    @model_validator(mode="after")
    def _validate_diff_source(self) -> "AnalyzePRRequest":
        has_url = bool(self.pr_url and self.pr_url.strip())
        has_diff = bool(self.raw_diff and self.raw_diff.strip())
        if not has_url and not has_diff:
            raise ValueError("Either pr_url or raw_diff must be provided.")
        return self


class PRAnalysisResponse(BaseModel):
    """Full persisted PR analysis response."""

    id: UUID
    repository_id: UUID
    snapshot_id: UUID
    pr_number: int | None
    pr_title: str
    changed_files: list[str]
    blast_radius: BlastRadiusResult
    ai_report: BlastRadiusReport | None
    citation_telemetry: CitationValidationTelemetry | None
    model_used: str | None
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    created_at: datetime
