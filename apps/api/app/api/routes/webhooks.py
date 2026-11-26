"""GitHub webhook receiver with strict constant-time HMAC-SHA256 verification."""

import json
import logging
from typing import cast

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.entities import FileNode, PRAnalysis, Repository
from app.schemas.analysis import (
    BlastRadiusReport,
    BlastRadiusResult,
    CitationValidationTelemetry,
    PRAnalysisResponse,
)
from app.services.citation_validator import validate_report_citations
from app.services.github import verify_github_webhook_signature
from app.services.pr_commenter import format_pending_pr_comment, render_pr_comment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


async def _build_dry_run_comment_preview(
    request: Request,
    repo_name: str,
    pr_number: int | None,
    action: str,
) -> str:
    engine = cast(AsyncEngine | None, getattr(request.app.state, "db_engine", None))
    if engine is None or "/" not in repo_name:
        return format_pending_pr_comment(repo_name, pr_number, action)

    owner, name = repo_name.split("/", 1)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        repo_result = await session.execute(
            select(Repository).where(Repository.owner == owner, Repository.name == name)
        )
        repo = repo_result.scalar_one_or_none()
        if repo is None:
            return format_pending_pr_comment(repo_name, pr_number, action)

        query = select(PRAnalysis).where(PRAnalysis.repository_id == repo.id)
        if pr_number is not None:
            matched_result = await session.execute(
                query.where(PRAnalysis.pr_number == pr_number)
                .order_by(desc(PRAnalysis.created_at))
                .limit(1)
            )
            record = matched_result.scalar_one_or_none()
        else:
            record = None

        if record is None:
            latest_result = await session.execute(
                query.order_by(desc(PRAnalysis.created_at)).limit(1)
            )
            record = latest_result.scalar_one_or_none()

        if record is None:
            return format_pending_pr_comment(repo_name, pr_number, action)

        nodes_result = await session.execute(
            select(FileNode.path).where(FileNode.snapshot_id == record.snapshot_id)
        )
        valid_paths = set(nodes_result.scalars().all())

    blast_radius = BlastRadiusResult.model_validate(record.blast_radius_json)
    ai_report = (
        BlastRadiusReport.model_validate(record.ai_report_json)
        if record.ai_report_json is not None
        else None
    )
    if record.citation_telemetry_json is not None:
        telemetry: CitationValidationTelemetry | None = (
            CitationValidationTelemetry.model_validate(record.citation_telemetry_json)
        )
    elif ai_report is not None:
        telemetry = validate_report_citations(ai_report, valid_paths)[1]
    else:
        telemetry = None

    analysis = PRAnalysisResponse(
        id=record.id,
        repository_id=record.repository_id,
        snapshot_id=record.snapshot_id,
        pr_number=record.pr_number,
        pr_title=record.pr_title,
        changed_files=list(record.changed_files),
        blast_radius=blast_radius,
        ai_report=ai_report,
        citation_telemetry=telemetry,
        model_used=record.model_used,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        estimated_cost_usd=float(record.estimated_cost_usd),
        latency_ms=record.latency_ms,
        created_at=record.created_at,
    )
    return render_pr_comment(analysis)


@router.post("/github")
async def receive_github_webhook(request: Request, response: Response) -> dict[str, object]:
    """Verify X-Hub-Signature-256 HMAC and accept GitHub pull_request events."""
    settings = cast(Settings, request.app.state.settings)
    raw_body = await request.body()

    if not settings.github_webhook_secret:
        logger.error("GitHub webhook received while GITHUB_WEBHOOK_SECRET is unconfigured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured",
        )

    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_webhook_signature(raw_body, signature, settings.github_webhook_secret):
        logger.warning("Rejected GitHub webhook due to invalid or missing HMAC signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON webhook payload: {exc}",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be a JSON object",
        )

    event = request.headers.get("X-GitHub-Event", "unknown")
    if event == "ping":
        return {"status": "pong"}

    if event == "pull_request":
        action = str(payload.get("action") or "")
        if action in {"opened", "synchronize", "reopened"}:
            repo_obj = payload.get("repository")
            pr_obj = payload.get("pull_request")
            repo_name = (
                str(repo_obj.get("full_name"))
                if isinstance(repo_obj, dict) and repo_obj.get("full_name")
                else ""
            )
            raw_pr_num = pr_obj.get("number") if isinstance(pr_obj, dict) else None
            pr_number = raw_pr_num if isinstance(raw_pr_num, int) else None
            dry_run = (
                bool(payload.get("dry_run"))
                or request.headers.get("X-ArchRadar-Dry-Run", "").lower() == "true"
            )
            result: dict[str, object] = {
                "status": "accepted",
                "event": "pull_request",
                "action": action,
                "pr_number": pr_number,
                "repository": repo_name,
                "comment_mode": "dry_run",
                "comment_posted": False,
            }
            if dry_run:
                preview = await _build_dry_run_comment_preview(
                    request=request,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    action=action,
                )
                result["comment_preview"] = preview
                result["comment_character_count"] = len(preview)
            response.status_code = status.HTTP_202_ACCEPTED
            return result

    return {"status": "ignored", "event": event}
