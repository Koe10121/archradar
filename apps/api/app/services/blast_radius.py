"""Deterministic reverse-BFS blast-radius calculator."""

from collections import deque
from dataclasses import dataclass

from app.parser.base import normalize_repo_path
from app.schemas.analysis import BlastRadiusResult, ImpactedEdgeDetail, RiskLevel

SENSITIVE_BOUNDARY_KEYWORDS = frozenset(
    {
        "auth",
        "webhook",
        "webhooks",
        "db",
        "database",
        "schema",
        "schemas",
        "middleware",
        "security",
        "billing",
        "payment",
        "migrations",
    }
)


@dataclass(frozen=True)
class NodeSnapshot:
    """Minimal node representation required for blast-radius traversal."""

    path: str
    language: str
    module_group: str
    loc: int
    in_degree: int
    out_degree: int
    exports: list[dict[str, object]]


@dataclass(frozen=True)
class EdgeSnapshot:
    """Minimal directed edge representation (source imports target)."""

    source_path: str
    target_path: str
    edge_type: str
    imported_symbols: list[str]


class BlastRadiusCalculator:
    """Computes multi-hop downstream dependents and deterministic risk score."""

    def calculate(
        self,
        nodes: list[NodeSnapshot],
        edges: list[EdgeSnapshot],
        changed_files: list[str],
        changed_symbols_by_file: dict[str, set[str]] | None = None,
        max_depth: int = 3,
    ) -> BlastRadiusResult:
        """Run reverse BFS from changed files and score architectural blast radius."""
        node_map = {n.path: n for n in nodes}
        changed_symbols = changed_symbols_by_file or {}

        # Reverse adjacency: if target changes, all sources importing target are impacted
        reverse_adj: dict[str, list[EdgeSnapshot]] = {}
        for edge in edges:
            reverse_adj.setdefault(edge.target_path, []).append(edge)

        direct: list[str] = []
        seen: set[str] = set()
        for raw_path in changed_files:
            try:
                norm_path = normalize_repo_path(raw_path)
            except ValueError:
                continue
            if norm_path in node_map and norm_path not in seen:
                seen.add(norm_path)
                direct.append(norm_path)

        hops: dict[int, list[str]] = {1: [], 2: [], 3: []}
        impacted_edges: list[ImpactedEdgeDetail] = []
        symbol_matched_files: set[str] = set()

        queue: deque[tuple[str, int]] = deque((path, 0) for path in direct)
        while queue:
            current_path, depth = queue.popleft()
            if depth >= max_depth:
                continue

            modified_syms = changed_symbols.get(current_path, set())
            for rev_edge in sorted(
                reverse_adj.get(current_path, []),
                key=lambda item: (item.source_path, item.edge_type),
            ):
                dependent = rev_edge.source_path
                sym_match = self._symbols_overlap(modified_syms, rev_edge.imported_symbols)
                if sym_match:
                    symbol_matched_files.add(dependent)

                impacted_edges.append(
                    ImpactedEdgeDetail(
                        source=dependent,
                        target=current_path,
                        edge_type=rev_edge.edge_type,
                        imported_symbols=list(rev_edge.imported_symbols),
                        symbol_match=sym_match,
                    )
                )

                if dependent in seen or dependent not in node_map:
                    continue

                next_depth = depth + 1
                seen.add(dependent)
                if next_depth in hops:
                    hops[next_depth].append(dependent)
                queue.append((dependent, next_depth))

        impacted_all = sorted(seen)
        max_in_degree = max(
            (node_map[p].in_degree for p in impacted_all if p in node_map),
            default=0,
        )
        sensitive_boundaries = self._find_sensitive_boundaries(impacted_all)
        score = self._compute_score(
            total_repo_files=max(len(nodes), 1),
            direct_count=len(direct),
            hop_1_count=len(hops[1]),
            hop_2_count=len(hops[2]),
            hop_3_count=len(hops[3]),
            max_in_degree=max_in_degree,
            symbol_match_count=len(symbol_matched_files),
            boundary_count=len(sensitive_boundaries),
        )

        return BlastRadiusResult(
            direct=sorted(direct),
            hop_1=sorted(hops[1]),
            hop_2=sorted(hops[2]),
            hop_3=sorted(hops[3]),
            score=score,
            deterministic_risk=self._score_to_risk(score),
            max_in_degree=max_in_degree,
            sensitive_boundaries_touched=sensitive_boundaries,
            symbol_matched_files=sorted(symbol_matched_files),
            impacted_edges=impacted_edges,
        )

    def _symbols_overlap(self, modified_syms: set[str], imported_syms: list[str]) -> bool:
        if not modified_syms or not imported_syms:
            return False
        if "*" in imported_syms:
            return True
        return bool(modified_syms.intersection(imported_syms))

    def _find_sensitive_boundaries(self, paths: list[str]) -> list[str]:
        matched: set[str] = set()
        for path in paths:
            parts = path.lower().replace(".", "/").split("/")
            for token in parts:
                if token in SENSITIVE_BOUNDARY_KEYWORDS:
                    matched.add(token)
        return sorted(matched)

    def _compute_score(
        self,
        *,
        total_repo_files: int,
        direct_count: int,
        hop_1_count: int,
        hop_2_count: int,
        hop_3_count: int,
        max_in_degree: int,
        symbol_match_count: int,
        boundary_count: int,
    ) -> int:
        impacted_total = direct_count + hop_1_count + hop_2_count + hop_3_count
        if impacted_total == 0:
            return 0
        ratio_pts = min(35, round((impacted_total / total_repo_files) * 60) + hop_1_count * 2)
        hub_pts = min(25, max_in_degree * 5)
        symbol_pts = min(20, symbol_match_count * 7)
        boundary_pts = min(20, boundary_count * 10)
        return min(100, ratio_pts + hub_pts + symbol_pts + boundary_pts)

    def _score_to_risk(self, score: int) -> RiskLevel:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        return "low"
