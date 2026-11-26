"""Pure service computing structural and centrality diffs between two snapshots."""

from uuid import UUID

from app.models.entities import DependencyEdge, FileNode, GraphSnapshot
from app.schemas.repo import (
    CentralityDeltaDTO,
    SnapshotDiffEdgeDTO,
    SnapshotDiffResponse,
    SnapshotSummary,
)


def _to_snapshot_summary(snapshot: GraphSnapshot) -> SnapshotSummary:
    return SnapshotSummary(
        id=snapshot.id,
        repository_id=snapshot.repository_id,
        commit_sha=snapshot.commit_sha,
        file_count=snapshot.file_count,
        edge_count=snapshot.edge_count,
        status=snapshot.status,
        created_at=snapshot.created_at,
    )


def _edge_map(
    nodes: list[FileNode],
    edges: list[DependencyEdge],
) -> dict[tuple[str, str, str], list[str]]:
    path_by_id = {node.id: node.path for node in nodes}
    mapped: dict[tuple[str, str, str], list[str]] = {}
    for edge in edges:
        src = path_by_id.get(edge.source_node_id)
        dst = path_by_id.get(edge.target_node_id)
        if not src or not dst:
            continue
        mapped[(src, dst, edge.edge_type)] = list(edge.imported_symbols)
    return mapped


def compute_snapshot_diff(
    *,
    repository_id: UUID,
    from_snapshot: GraphSnapshot,
    to_snapshot: GraphSnapshot,
    from_nodes: list[FileNode],
    from_edges: list[DependencyEdge],
    to_nodes: list[FileNode],
    to_edges: list[DependencyEdge],
) -> SnapshotDiffResponse:
    """Compare two graph snapshots for file, edge, and centrality (in_degree) deltas."""
    from_by_path = {node.path: node for node in from_nodes}
    to_by_path = {node.path: node for node in to_nodes}

    from_paths = set(from_by_path)
    to_paths = set(to_by_path)
    added_files = sorted(to_paths - from_paths)
    removed_files = sorted(from_paths - to_paths)

    from_edge_map = _edge_map(from_nodes, from_edges)
    to_edge_map = _edge_map(to_nodes, to_edges)

    added_edges = [
        SnapshotDiffEdgeDTO(
            source_path=src,
            target_path=dst,
            edge_type=edge_type,
            imported_symbols=to_edge_map[(src, dst, edge_type)],
        )
        for src, dst, edge_type in sorted(set(to_edge_map) - set(from_edge_map))
    ]
    removed_edges = [
        SnapshotDiffEdgeDTO(
            source_path=src,
            target_path=dst,
            edge_type=edge_type,
            imported_symbols=from_edge_map[(src, dst, edge_type)],
        )
        for src, dst, edge_type in sorted(set(from_edge_map) - set(to_edge_map))
    ]

    centrality_deltas: list[CentralityDeltaDTO] = []
    for path in sorted(from_paths | to_paths):
        prev_node = from_by_path.get(path)
        next_node = to_by_path.get(path)

        from_in = prev_node.in_degree if prev_node is not None else 0
        to_in = next_node.in_degree if next_node is not None else 0
        from_out = prev_node.out_degree if prev_node is not None else 0
        to_out = next_node.out_degree if next_node is not None else 0
        in_delta = to_in - from_in
        out_delta = to_out - from_out

        if prev_node is None and next_node is not None:
            delta_status: str = "added"
            ref_node = next_node
        elif next_node is None and prev_node is not None:
            delta_status = "removed"
            ref_node = prev_node
        elif in_delta != 0 or out_delta != 0:
            delta_status = "changed"
            assert next_node is not None
            ref_node = next_node
        else:
            continue

        centrality_deltas.append(
            CentralityDeltaDTO(
                path=path,
                module_group=ref_node.module_group,
                language=ref_node.language,
                from_in_degree=from_in,
                to_in_degree=to_in,
                in_degree_delta=in_delta,
                from_out_degree=from_out,
                to_out_degree=to_out,
                out_degree_delta=out_delta,
                status="added"
                if delta_status == "added"
                else ("removed" if delta_status == "removed" else "changed"),
            )
        )

    centrality_deltas.sort(
        key=lambda d: (-abs(d.in_degree_delta), -abs(d.out_degree_delta), d.path)
    )

    return SnapshotDiffResponse(
        repository_id=repository_id,
        from_snapshot=_to_snapshot_summary(from_snapshot),
        to_snapshot=_to_snapshot_summary(to_snapshot),
        added_files=added_files,
        removed_files=removed_files,
        added_edges=added_edges,
        removed_edges=removed_edges,
        centrality_deltas=centrality_deltas,
        file_count_delta=to_snapshot.file_count - from_snapshot.file_count,
        edge_count_delta=to_snapshot.edge_count - from_snapshot.edge_count,
    )
