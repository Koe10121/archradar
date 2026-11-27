"""Zero-AI deterministic architecture health, cycle, hotspot, and layer analyzer."""

from collections import deque
from typing import Literal

from app.parser.base import is_test_file
from app.schemas.repo import (
    ArchitectureHealthDTO,
    CycleFindingDTO,
    HotspotFindingDTO,
    LayerViolationDTO,
)
from app.services.blast_radius import (
    SENSITIVE_BOUNDARY_KEYWORDS,
    EdgeSnapshot,
    NodeSnapshot,
    has_test_importer,
)

ArchLayer = Literal["data", "service", "presentation"]

_DATA_SEGMENTS = frozenset(
    {"db", "database", "models", "entities", "migrations", "repositories_db", "persistence"}
)
_SERVICE_SEGMENTS = frozenset(
    {"services", "domain", "usecases", "parser", "workers"}
)
_PRESENTATION_SEGMENTS = frozenset(
    {"routes", "controllers", "handlers", "ui", "components", "pages", "views", "webhooks"}
)


def classify_arch_layer(path: str) -> ArchLayer | None:
    """Infer architectural layer tier from repository-relative directory segments."""
    parts = [p.lower() for p in path.replace("\\", "/").split("/")[:-1] if p]
    # Check deepest matching architectural folder first
    for seg in reversed(parts):
        if seg in _PRESENTATION_SEGMENTS:
            return "presentation"
        if seg in _DATA_SEGMENTS:
            return "data"
        if seg in _SERVICE_SEGMENTS:
            return "service"
    return None


def _reconstruct_cycle_ring(scc: list[str], adj: dict[str, list[str]]) -> list[str]:
    """Find a concrete shortest cycle ring `[start, ..., start]` inside a non-trivial SCC."""
    scc_set = set(scc)
    start = sorted(scc)[0]

    best_ring: list[str] | None = None
    for first_next in sorted(n for n in adj.get(start, []) if n in scc_set):
        if first_next == start:
            return [start, start]
        # Shortest path from first_next back to start within scc_set
        parent: dict[str, str] = {first_next: start}
        queue: deque[str] = deque([first_next])
        found = False
        while queue and not found:
            cur = queue.popleft()
            for nxt in sorted(n for n in adj.get(cur, []) if n in scc_set):
                if nxt == start:
                    ring = [start]
                    step = cur
                    chain: list[str] = []
                    while step != start:
                        chain.append(step)
                        step = parent[step]
                    chain.reverse()
                    ring.extend(chain)
                    ring.append(start)
                    if best_ring is None or len(ring) < len(best_ring):
                        best_ring = ring
                    found = True
                    break
                if nxt not in parent:
                    parent[nxt] = cur
                    queue.append(nxt)

    if best_ring is not None:
        return best_ring
    ordered = sorted(scc)
    return [*ordered, ordered[0]]


def _detect_cycles(
    prod_paths: list[str],
    edges: list[EdgeSnapshot],
) -> list[CycleFindingDTO]:
    """Run iterative/recursive Tarjan SCC over production files to detect dependency cycles."""
    prod_set = set(prod_paths)
    adj: dict[str, list[str]] = {p: [] for p in prod_paths}
    for edge in edges:
        if (
            edge.source_path in prod_set
            and edge.target_path in prod_set
            and edge.target_path not in adj[edge.source_path]
        ):
            adj[edge.source_path].append(edge.target_path)

    for p in adj:
        adj[p].sort()

    index_counter = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    sccs: list[list[str]] = []

    # Iterative Tarjan to avoid recursion-depth limits on 600-node graphs
    for root in sorted(prod_paths):
        if root in indices:
            continue
        call_stack: list[tuple[str, int]] = [(root, 0)]
        indices[root] = lowlink[root] = index_counter
        index_counter += 1
        stack.append(root)
        on_stack.add(root)

        while call_stack:
            v, neighbor_idx = call_stack[-1]
            neighbors = adj[v]
            if neighbor_idx < len(neighbors):
                call_stack[-1] = (v, neighbor_idx + 1)
                w = neighbors[neighbor_idx]
                if w not in indices:
                    indices[w] = lowlink[w] = index_counter
                    index_counter += 1
                    stack.append(w)
                    on_stack.add(w)
                    call_stack.append((w, 0))
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], indices[w])
            else:
                call_stack.pop()
                if call_stack:
                    parent_v, _ = call_stack[-1]
                    lowlink[parent_v] = min(lowlink[parent_v], lowlink[v])
                if lowlink[v] == indices[v]:
                    comp: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    if len(comp) >= 2 or (len(comp) == 1 and comp[0] in adj[comp[0]]):
                        sccs.append(comp)

    findings: list[CycleFindingDTO] = []
    for comp in sorted(sccs, key=lambda c: (-len(c), sorted(c)[0])):
        ring = _reconstruct_cycle_ring(comp, adj)
        unique_len = max(1, len(ring) - 1)
        severity: Literal["warning", "high"] = "high" if len(comp) >= 3 else "warning"
        findings.append(
            CycleFindingDTO(
                cycle_paths=ring,
                length=unique_len,
                severity=severity,
            )
        )
    return findings[:15]


def _detect_layer_violations(
    prod_set: set[str],
    edges: list[EdgeSnapshot],
) -> list[LayerViolationDTO]:
    violations: list[LayerViolationDTO] = []
    seen_pairs: set[tuple[str, str]] = set()

    for edge in sorted(edges, key=lambda e: (e.source_path, e.target_path)):
        src = edge.source_path
        dst = edge.target_path
        if src == dst or src not in prod_set or dst not in prod_set:
            continue
        if (src, dst) in seen_pairs:
            continue

        src_layer = classify_arch_layer(src)
        dst_layer = classify_arch_layer(dst)
        if src_layer is None or dst_layer is None or src_layer == dst_layer:
            continue

        reason: str | None = None
        if src_layer == "data" and dst_layer in {"service", "presentation"}:
            reason = (
                f"Persistence/data module imports upward from {dst_layer} layer "
                f"(`{dst}`), inverting dependency direction."
            )
        elif src_layer == "service" and dst_layer == "presentation":
            reason = (
                f"Service/domain module imports upward from presentation/API layer "
                f"(`{dst}`), coupling business logic to transport/UI."
            )

        if reason is not None:
            seen_pairs.add((src, dst))
            violations.append(
                LayerViolationDTO(
                    source_path=src,
                    target_path=dst,
                    source_layer=src_layer,
                    target_layer=dst_layer,
                    imported_symbols=list(edge.imported_symbols[:4]),
                    reason=reason,
                )
            )
    return violations[:20]


def _touches_sensitive(path: str) -> bool:
    parts = path.lower().replace(".", "/").split("/")
    return any(tok in SENSITIVE_BOUNDARY_KEYWORDS for tok in parts)


def compute_architecture_health(
    nodes: list[NodeSnapshot],
    edges: list[EdgeSnapshot],
) -> ArchitectureHealthDTO:
    """Compute zero-AI structural health metrics (cycles, layer violations, hotspots)."""
    prod_nodes = [n for n in nodes if not is_test_file(n.path)]
    prod_paths = [n.path for n in prod_nodes]
    prod_set = set(prod_paths)

    reverse_adj: dict[str, list[EdgeSnapshot]] = {}
    prod_in_degree: dict[str, int] = {p: 0 for p in prod_paths}
    for edge in edges:
        reverse_adj.setdefault(edge.target_path, []).append(edge)
        if edge.source_path in prod_set and edge.target_path in prod_set:
            prod_in_degree[edge.target_path] += 1

    cycles = _detect_cycles(prod_paths, edges)
    layer_violations = _detect_layer_violations(prod_set, edges)

    ranked_hotspots: list[tuple[int, HotspotFindingDTO]] = []
    untested_hub_count = 0
    any_test_in_repo = any(is_test_file(n.path) for n in nodes)

    for node in prod_nodes:
        fan_in = prod_in_degree.get(node.path, node.in_degree)
        sensitive = _touches_sensitive(node.path)
        has_tests = has_test_importer(node.path, reverse_adj, max_hops=2)
        if fan_in >= 3 and not has_tests:
            untested_hub_count += 1

        if fan_in < 3 and not (fan_in >= 2 and sensitive and node.loc >= 70):
            continue

        risk_pts = fan_in * 10 + min(25, node.loc // 12) + (15 if sensitive else 0)
        if any_test_in_repo and not has_tests:
            risk_pts += 12

        reasons: list[str] = [f"Imported by {fan_in} production modules"]
        if sensitive:
            reasons.append("sits on a sensitive boundary")
        if node.loc >= 180:
            reasons.append(f"large module ({node.loc} LOC)")
        if any_test_in_repo and not has_tests:
            reasons.append("no test coverage within 2 hops")

        ranked_hotspots.append(
            (
                risk_pts,
                HotspotFindingDTO(
                    path=node.path,
                    module_group=node.module_group,
                    in_degree=fan_in,
                    out_degree=node.out_degree,
                    loc=node.loc,
                    has_tests=has_tests,
                    touches_sensitive_boundary=sensitive,
                    reason="; ".join(reasons) + ".",
                ),
            )
        )

    ranked_hotspots.sort(key=lambda item: (-item[0], item[1].path))
    hotspots = [item[1] for item in ranked_hotspots[:8]]

    penalty = (
        min(45, len(cycles) * 15)
        + min(30, len(layer_violations) * 10)
        + (min(20, untested_hub_count * 5) if any_test_in_repo else 0)
    )
    health_score = max(0, 100 - penalty)
    grade: Literal["healthy", "watch", "at_risk"] = (
        "healthy" if health_score >= 80 else ("watch" if health_score >= 55 else "at_risk")
    )

    return ArchitectureHealthDTO(
        health_score=health_score,
        grade=grade,
        cycle_count=len(cycles),
        layer_violation_count=len(layer_violations),
        hotspot_count=len(hotspots),
        untested_hub_count=untested_hub_count if any_test_in_repo else 0,
        cycles=cycles,
        hotspots=hotspots,
        layer_violations=layer_violations,
    )
