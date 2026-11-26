"""PR blast-radius and grounded AI analysis API endpoints."""

from decimal import Decimal
from typing import cast
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.entities import DependencyEdge, FileNode, GraphSnapshot, PRAnalysis, Repository
from app.schemas.analysis import (
    AnalyzePRRequest,
    BlastRadiusReport,
    BlastRadiusResult,
    CitationValidationTelemetry,
    PRAnalysisResponse,
)
from app.services.ai_analyzer import AIAnalyzer, GeminiLLMProvider, LLMProvider
from app.services.blast_radius import BlastRadiusCalculator, EdgeSnapshot, NodeSnapshot
from app.services.citation_validator import validate_report_citations
from app.services.github import fetch_github_pr_diff, parse_unified_diff

router = APIRouter(prefix="/api", tags=["analyses"])


@router.post(
    "/repos/{repo_id}/analyze-pr",
    response_model=PRAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_pull_request(
    repo_id: UUID,
    payload: AnalyzePRRequest,
    request: Request,
) -> PRAnalysisResponse:
    """Compute deterministic blast radius and optional grounded AI risk report for a PR."""
    settings = cast(Settings, request.app.state.settings)
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo_result = await session.execute(select(Repository).where(Repository.id == repo_id))
        repo = repo_result.scalar_one_or_none()
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        snap_result = await session.execute(
            select(GraphSnapshot)
            .where(
                GraphSnapshot.repository_id == repo.id,
                GraphSnapshot.status == "ready",
            )
            .order_by(desc(GraphSnapshot.created_at))
            .limit(1)
        )
        snapshot = snap_result.scalar_one_or_none()
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No ready graph snapshot found for repository",
            )

        nodes_result = await session.execute(
            select(FileNode).where(FileNode.snapshot_id == snapshot.id)
        )
        db_nodes = list(nodes_result.scalars().all())
        path_by_id = {n.id: n.path for n in db_nodes}

        edges_result = await session.execute(
            select(DependencyEdge).where(DependencyEdge.snapshot_id == snapshot.id)
        )
        db_edges = list(edges_result.scalars().all())

        node_snapshots = [
            NodeSnapshot(
                path=n.path,
                language=n.language,
                module_group=n.module_group,
                loc=n.loc,
                in_degree=n.in_degree,
                out_degree=n.out_degree,
                exports=list(n.exports_json),
            )
            for n in db_nodes
        ]
        edge_snapshots = [
            EdgeSnapshot(
                source_path=path_by_id[e.source_node_id],
                target_path=path_by_id[e.target_node_id],
                edge_type=e.edge_type,
                imported_symbols=list(e.imported_symbols),
            )
            for e in db_edges
            if e.source_node_id in path_by_id and e.target_node_id in path_by_id
        ]

        pr_title = payload.pr_title
        pr_description = payload.pr_description
        pr_number = payload.pr_number

        if payload.raw_diff:
            raw_diff = payload.raw_diff
        else:
            assert payload.pr_url is not None
            try:
                pr_title, pr_description, pr_number, raw_diff = await fetch_github_pr_diff(
                    payload.pr_url,
                    github_token=settings.github_token,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to fetch GitHub PR diff: {exc}",
                ) from exc

        in_degree_by_file = {n.path: n.in_degree for n in node_snapshots}
        try:
            parsed_diff = parse_unified_diff(raw_diff, in_degree_by_file=in_degree_by_file)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse unified diff: {exc}",
            ) from exc

        calculator = BlastRadiusCalculator()
        blast_radius = calculator.calculate(
            nodes=node_snapshots,
            edges=edge_snapshots,
            changed_files=parsed_diff.changed_files,
            changed_symbols_by_file=parsed_diff.changed_symbols_by_file,
        )

        ai_report: BlastRadiusReport | None = None
        citation_telemetry: CitationValidationTelemetry | None = None
        model_used: str | None = None
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = Decimal("0.000000")
        latency_ms = 0

        if payload.run_ai:
            injected_provider = cast(
                LLMProvider | None,
                getattr(request.app.state, "llm_provider", None),
            )
            try:
                provider = injected_provider or GeminiLLMProvider(
                    api_key=settings.gemini_api_key,
                    model=settings.gemini_model,
                )
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{exc} Configure GEMINI_API_KEY or set run_ai=false.",
                ) from exc

            analyzer = AIAnalyzer(provider=provider)
            try:
                ai_result = await analyzer.analyze(
                    pr_title=pr_title,
                    pr_description=pr_description,
                    truncated_diff=parsed_diff.truncated_diff,
                    nodes=node_snapshots,
                    blast_radius=blast_radius,
                    doc_context=payload.doc_context or None,
                    raw_diff=raw_diff,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc

            ai_report = ai_result.report
            citation_telemetry = ai_result.citation_telemetry
            model_used = ai_result.model_used
            prompt_tokens = ai_result.prompt_tokens
            completion_tokens = ai_result.completion_tokens
            estimated_cost_usd = ai_result.estimated_cost_usd
            latency_ms = ai_result.latency_ms

        record = PRAnalysis(
            repository_id=repo.id,
            snapshot_id=snapshot.id,
            pr_number=pr_number,
            pr_title=pr_title,
            changed_files=parsed_diff.changed_files,
            blast_radius_json=blast_radius.model_dump(),
            ai_report_json=ai_report.model_dump() if ai_report is not None else None,
            citation_telemetry_json=(
                citation_telemetry.model_dump() if citation_telemetry is not None else None
            ),
            model_used=model_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost_usd,
            latency_ms=latency_ms,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)

    return PRAnalysisResponse(
        id=record.id,
        repository_id=record.repository_id,
        snapshot_id=record.snapshot_id,
        pr_number=record.pr_number,
        pr_title=record.pr_title,
        changed_files=list(record.changed_files),
        blast_radius=blast_radius,
        ai_report=ai_report,
        citation_telemetry=citation_telemetry,
        model_used=record.model_used,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        estimated_cost_usd=float(record.estimated_cost_usd),
        latency_ms=record.latency_ms,
        created_at=record.created_at,
    )


@router.get("/repos/{repo_id}/analyses", response_model=list[PRAnalysisResponse])
async def list_repository_analyses(
    repo_id: UUID,
    request: Request,
) -> list[PRAnalysisResponse]:
    """List persisted PR blast-radius analyses for a repository, newest first."""
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo_result = await session.execute(select(Repository).where(Repository.id == repo_id))
        if repo_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        records_result = await session.execute(
            select(PRAnalysis)
            .where(PRAnalysis.repository_id == repo_id)
            .order_by(desc(PRAnalysis.created_at))
        )
        records = list(records_result.scalars().all())
        if not records:
            return []

        snapshot_ids = {record.snapshot_id for record in records}
        paths_by_snapshot: dict[UUID, set[str]] = {sid: set() for sid in snapshot_ids}
        nodes_result = await session.execute(
            select(FileNode.snapshot_id, FileNode.path).where(
                FileNode.snapshot_id.in_(snapshot_ids)
            )
        )
        for snapshot_id, path in nodes_result.all():
            paths_by_snapshot.setdefault(snapshot_id, set()).add(path)

    responses: list[PRAnalysisResponse] = []
    for record in records:
        blast_radius = BlastRadiusResult.model_validate(record.blast_radius_json)
        ai_report = (
            BlastRadiusReport.model_validate(record.ai_report_json)
            if record.ai_report_json is not None
            else None
        )
        valid_paths = paths_by_snapshot.get(record.snapshot_id, set())
        if record.citation_telemetry_json is not None:
            telemetry: CitationValidationTelemetry | None = (
                CitationValidationTelemetry.model_validate(record.citation_telemetry_json)
            )
        elif ai_report is not None:
            telemetry = validate_report_citations(ai_report, valid_paths)[1]
        else:
            telemetry = None
        responses.append(
            PRAnalysisResponse(
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
        )
    return responses


@router.get("/analyses/{analysis_id}", response_model=PRAnalysisResponse)
async def get_analysis(analysis_id: UUID, request: Request) -> PRAnalysisResponse:
    """Retrieve a persisted PR blast-radius and AI analysis report by ID."""
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        result = await session.execute(select(PRAnalysis).where(PRAnalysis.id == analysis_id))
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found",
            )

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

    return PRAnalysisResponse(
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
