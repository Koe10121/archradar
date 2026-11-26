"""Repository indexing and graph retrieval API endpoints."""

from pathlib import Path
from typing import Annotated, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.entities import DependencyEdge, FileNode, GraphSnapshot, Repository
from app.schemas.repo import (
    ExportedSymbolDTO,
    GraphEdgeDTO,
    GraphNodeDTO,
    GraphResponse,
    RepoIndexRequest,
    RepoIndexResponse,
    RepositorySummary,
    SnapshotDiffResponse,
    SnapshotSummary,
)
from app.services.indexer import RepoIndexer, parse_github_repo_url
from app.services.snapshot_diff import compute_snapshot_diff

router = APIRouter(prefix="/api/repos", tags=["repositories"])


@router.post("/index", response_model=RepoIndexResponse, status_code=status.HTTP_201_CREATED)
async def index_repository(
    payload: RepoIndexRequest,
    request: Request,
) -> RepoIndexResponse:
    """Index a GitHub repository URL or local directory into a dependency graph snapshot."""
    settings = cast(Settings, request.app.state.settings)
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)
    indexer = RepoIndexer()

    async with session_factory() as session:
        try:
            if payload.local_path:
                local_dir = Path(payload.local_path).resolve()
                repo_name = local_dir.name or "local-repo"
                repo_url = (payload.repo_url or f"local://{repo_name}").strip()
                repo, snapshot = await indexer.index_local_directory(
                    session=session,
                    repo_root=local_dir,
                    owner="local",
                    name=repo_name,
                    url=repo_url,
                    commit_sha="local-head",
                    default_branch=payload.branch or "main",
                    is_demo=payload.is_demo,
                )
            else:
                assert payload.repo_url is not None
                parse_github_repo_url(payload.repo_url)
                repo, snapshot = await indexer.index_github_repository(
                    session=session,
                    repo_url=payload.repo_url,
                    branch=payload.branch,
                    github_token=settings.github_token,
                    is_demo=payload.is_demo,
                )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch GitHub repository: {exc}",
            ) from exc

    return RepoIndexResponse(
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        commit_sha=snapshot.commit_sha,
        status=snapshot.status,
        file_count=snapshot.file_count,
        edge_count=snapshot.edge_count,
    )


@router.get("", response_model=list[RepositorySummary])
async def list_repositories(request: Request) -> list[RepositorySummary]:
    """List all indexed repositories with their latest ready snapshot metrics."""
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repos_result = await session.execute(
            select(Repository).order_by(desc(Repository.created_at))
        )
        repos = list(repos_result.scalars().all())

        summaries: list[RepositorySummary] = []
        for repo in repos:
            snap_result = await session.execute(
                select(GraphSnapshot)
                .where(
                    GraphSnapshot.repository_id == repo.id,
                    GraphSnapshot.status == "ready",
                )
                .order_by(desc(GraphSnapshot.created_at))
                .limit(1)
            )
            latest = snap_result.scalar_one_or_none()
            summaries.append(
                RepositorySummary(
                    id=repo.id,
                    owner=repo.owner,
                    name=repo.name,
                    url=repo.url,
                    default_branch=repo.default_branch,
                    is_demo=repo.is_demo,
                    last_indexed_sha=repo.last_indexed_sha,
                    latest_snapshot_id=latest.id if latest else None,
                    file_count=latest.file_count if latest else 0,
                    edge_count=latest.edge_count if latest else 0,
                    created_at=repo.created_at,
                )
            )
        return summaries


@router.get("/{repo_id}/graph", response_model=GraphResponse)
async def get_repository_graph(
    repo_id: UUID,
    request: Request,
    snapshot_id: Annotated[UUID | None, Query()] = None,
) -> GraphResponse:
    """Return file nodes and dependency edges for a specific or latest ready snapshot."""
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

        if snapshot_id is not None:
            snap_result = await session.execute(
                select(GraphSnapshot).where(
                    GraphSnapshot.id == snapshot_id,
                    GraphSnapshot.repository_id == repo.id,
                    GraphSnapshot.status == "ready",
                )
            )
        else:
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
            select(FileNode).where(FileNode.snapshot_id == snapshot.id).order_by(FileNode.path)
        )
        nodes = list(nodes_result.scalars().all())
        path_by_id = {node.id: node.path for node in nodes}

        edges_result = await session.execute(
            select(DependencyEdge).where(DependencyEdge.snapshot_id == snapshot.id)
        )
        edges = list(edges_result.scalars().all())

    node_dtos = [
        GraphNodeDTO(
            id=node.id,
            path=node.path,
            language=node.language,
            module_group=node.module_group,
            loc=node.loc,
            exports=[ExportedSymbolDTO.model_validate(item) for item in node.exports_json],
            in_degree=node.in_degree,
            out_degree=node.out_degree,
        )
        for node in nodes
    ]
    edge_dtos = [
        GraphEdgeDTO(
            id=edge.id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            source_path=path_by_id.get(edge.source_node_id, ""),
            target_path=path_by_id.get(edge.target_node_id, ""),
            edge_type=edge.edge_type,
            imported_symbols=list(edge.imported_symbols),
        )
        for edge in edges
    ]

    return GraphResponse(
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        commit_sha=snapshot.commit_sha,
        file_count=snapshot.file_count,
        edge_count=snapshot.edge_count,
        nodes=node_dtos,
        edges=edge_dtos,
    )


@router.get("/{repo_id}/snapshots", response_model=list[SnapshotSummary])
async def list_repository_snapshots(repo_id: UUID, request: Request) -> list[SnapshotSummary]:
    """List ready graph snapshots for a repository in chronological order."""
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo_result = await session.execute(select(Repository).where(Repository.id == repo_id))
        if repo_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        snaps_result = await session.execute(
            select(GraphSnapshot)
            .where(
                GraphSnapshot.repository_id == repo_id,
                GraphSnapshot.status == "ready",
            )
            .order_by(asc(GraphSnapshot.created_at), asc(GraphSnapshot.id))
        )
        snapshots = list(snaps_result.scalars().all())

    return [
        SnapshotSummary(
            id=snap.id,
            repository_id=snap.repository_id,
            commit_sha=snap.commit_sha,
            file_count=snap.file_count,
            edge_count=snap.edge_count,
            status=snap.status,
            created_at=snap.created_at,
        )
        for snap in snapshots
    ]


@router.get("/{repo_id}/snapshots/diff", response_model=SnapshotDiffResponse)
async def diff_repository_snapshots(
    repo_id: UUID,
    request: Request,
    from_snapshot_id: Annotated[UUID, Query()],
    to_snapshot_id: Annotated[UUID, Query()],
) -> SnapshotDiffResponse:
    """Compute added/removed files, edges, and centrality deltas between two snapshots."""
    engine = cast(AsyncEngine, request.app.state.db_engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo_result = await session.execute(select(Repository).where(Repository.id == repo_id))
        if repo_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )

        from_res = await session.execute(
            select(GraphSnapshot).where(
                GraphSnapshot.id == from_snapshot_id,
                GraphSnapshot.repository_id == repo_id,
                GraphSnapshot.status == "ready",
            )
        )
        from_snap = from_res.scalar_one_or_none()
        if from_snap is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source snapshot not found for repository",
            )

        to_res = await session.execute(
            select(GraphSnapshot).where(
                GraphSnapshot.id == to_snapshot_id,
                GraphSnapshot.repository_id == repo_id,
                GraphSnapshot.status == "ready",
            )
        )
        to_snap = to_res.scalar_one_or_none()
        if to_snap is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target snapshot not found for repository",
            )

        from_nodes = list(
            (
                await session.execute(
                    select(FileNode).where(FileNode.snapshot_id == from_snap.id)
                )
            )
            .scalars()
            .all()
        )
        from_edges = list(
            (
                await session.execute(
                    select(DependencyEdge).where(DependencyEdge.snapshot_id == from_snap.id)
                )
            )
            .scalars()
            .all()
        )
        to_nodes = list(
            (
                await session.execute(
                    select(FileNode).where(FileNode.snapshot_id == to_snap.id)
                )
            )
            .scalars()
            .all()
        )
        to_edges = list(
            (
                await session.execute(
                    select(DependencyEdge).where(DependencyEdge.snapshot_id == to_snap.id)
                )
            )
            .scalars()
            .all()
        )

    return compute_snapshot_diff(
        repository_id=repo_id,
        from_snapshot=from_snap,
        to_snapshot=to_snap,
        from_nodes=from_nodes,
        from_edges=from_edges,
        to_nodes=to_nodes,
        to_edges=to_edges,
    )
