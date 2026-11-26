"""Pydantic schemas for telemetry & cost analytics endpoints."""

from pydantic import BaseModel


class RiskLevelCounts(BaseModel):
    """Counts of persisted PR analyses grouped by risk classification."""

    low: int
    medium: int
    high: int
    critical: int


class ModelUsageBreakdown(BaseModel):
    """Aggregated token, latency, and USD cost metrics per model."""

    model: str
    analyses_count: int
    avg_prompt_tokens: float
    avg_completion_tokens: float
    total_cost_usd: float
    avg_latency_ms: float


class TelemetrySummaryResponse(BaseModel):
    """Aggregate telemetry, latency, cost, and citation-gate summary."""

    total_analyses: int
    ai_enabled_analyses: int
    deterministic_only_analyses: int
    risk_counts: RiskLevelCounts
    median_latency_ms: float
    p95_latency_ms: float
    avg_prompt_tokens: float
    avg_completion_tokens: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    avg_cost_per_pr_usd: float
    projected_cost_per_1000_prs_usd: float
    total_cited_paths: int
    valid_cited_paths: int
    citation_gate_intercepts: int
    models: list[ModelUsageBreakdown]
