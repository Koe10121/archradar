"""Telemetry and cost analytics aggregation API endpoint."""

import math
import statistics
from collections import defaultdict
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import create_session_factory
from app.models.entities import PRAnalysis
from app.schemas.telemetry import (
    ModelUsageBreakdown,
    RiskLevelCounts,
    TelemetrySummaryResponse,
)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

_VALID_RISKS = {"low", "medium", "high", "critical"}


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(pct * len(ordered)) - 1))
    return float(ordered[idx])


def _extract_risk(record: PRAnalysis) -> str:
    if isinstance(record.ai_report_json, dict):
        risk = record.ai_report_json.get("overall_risk")
        if isinstance(risk, str) and risk in _VALID_RISKS:
            return risk
    if isinstance(record.blast_radius_json, dict):
        risk = record.blast_radius_json.get("deterministic_risk")
        if isinstance(risk, str) and risk in _VALID_RISKS:
            return risk
    return "low"


def _extract_citation_counts(record: PRAnalysis) -> tuple[int, int, int]:
    if isinstance(record.citation_telemetry_json, dict):
        total = int(cast(int, record.citation_telemetry_json.get("total_cited_paths", 0) or 0))
        valid = int(cast(int, record.citation_telemetry_json.get("valid_cited_paths", 0) or 0))
        caught = int(cast(int, record.citation_telemetry_json.get("hallucination_caught", 0) or 0))
        return total, valid, caught

    if isinstance(record.ai_report_json, dict):
        flows = record.ai_report_json.get("impacted_flows")
        if isinstance(flows, list):
            count = 0
            for flow in flows:
                if not isinstance(flow, dict):
                    continue
                if isinstance(flow.get("entry_file"), str):
                    count += 1
                affected = flow.get("affected_files")
                if isinstance(affected, list):
                    count += len(affected)
            return count, count, 0

    return 0, 0, 0


@router.get("/summary", response_model=TelemetrySummaryResponse)
async def get_telemetry_summary(
    request: Request,
    repo_id: Annotated[UUID | None, Query()] = None,
) -> TelemetrySummaryResponse:
    """Aggregate latency, token cost, risk counts, and citation-gate intercepts."""
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        stmt = select(PRAnalysis)
        if repo_id is not None:
            stmt = stmt.where(PRAnalysis.repository_id == repo_id)
        records = list((await session.execute(stmt)).scalars().all())

    total_analyses = len(records)
    if total_analyses == 0:
        return TelemetrySummaryResponse(
            total_analyses=0,
            ai_enabled_analyses=0,
            deterministic_only_analyses=0,
            risk_counts=RiskLevelCounts(low=0, medium=0, high=0, critical=0),
            median_latency_ms=0.0,
            p95_latency_ms=0.0,
            avg_prompt_tokens=0.0,
            avg_completion_tokens=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_cost_usd=0.0,
            avg_cost_per_pr_usd=0.0,
            projected_cost_per_1000_prs_usd=0.0,
            total_cited_paths=0,
            valid_cited_paths=0,
            citation_gate_intercepts=0,
            models=[],
        )

    risk_map: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    latencies: list[int] = []
    ai_enabled = 0
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0
    total_cited = 0
    valid_cited = 0
    intercepts = 0
    by_model: dict[str, list[PRAnalysis]] = defaultdict(list)

    for rec in records:
        risk_map[_extract_risk(rec)] += 1
        latencies.append(rec.latency_ms)
        if rec.ai_report_json is not None:
            ai_enabled += 1
        total_prompt += rec.prompt_tokens
        total_completion += rec.completion_tokens
        total_cost += float(rec.estimated_cost_usd)

        c_total, c_valid, c_caught = _extract_citation_counts(rec)
        total_cited += c_total
        valid_cited += c_valid
        intercepts += c_caught

        model_key = rec.model_used or "deterministic-only"
        by_model[model_key].append(rec)

    avg_cost = total_cost / total_analyses
    models = [
        ModelUsageBreakdown(
            model=model_name,
            analyses_count=len(group),
            avg_prompt_tokens=round(sum(r.prompt_tokens for r in group) / len(group), 1),
            avg_completion_tokens=round(sum(r.completion_tokens for r in group) / len(group), 1),
            total_cost_usd=round(sum(float(r.estimated_cost_usd) for r in group), 6),
            avg_latency_ms=round(sum(r.latency_ms for r in group) / len(group), 1),
        )
        for model_name, group in sorted(
            by_model.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )
    ]

    return TelemetrySummaryResponse(
        total_analyses=total_analyses,
        ai_enabled_analyses=ai_enabled,
        deterministic_only_analyses=total_analyses - ai_enabled,
        risk_counts=RiskLevelCounts(
            low=risk_map["low"],
            medium=risk_map["medium"],
            high=risk_map["high"],
            critical=risk_map["critical"],
        ),
        median_latency_ms=round(float(statistics.median(latencies)), 2),
        p95_latency_ms=round(_percentile(latencies, 0.95), 2),
        avg_prompt_tokens=round(total_prompt / total_analyses, 1),
        avg_completion_tokens=round(total_completion / total_analyses, 1),
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_cost_usd=round(total_cost, 6),
        avg_cost_per_pr_usd=round(avg_cost, 6),
        projected_cost_per_1000_prs_usd=round(avg_cost * 1000.0, 4),
        total_cited_paths=total_cited,
        valid_cited_paths=valid_cited,
        citation_gate_intercepts=intercepts,
        models=models,
    )
