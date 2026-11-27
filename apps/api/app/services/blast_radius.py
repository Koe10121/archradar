"""Deterministic reverse-BFS blast-radius calculator with symbol & test intelligence."""

import posixpath
import re
from collections import deque
from dataclasses import dataclass

from app.parser.base import is_test_file, normalize_repo_path
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
_TYPE_EXPORT_KINDS = frozenset(
    {"interface", "type", "struct", "enum", "trait", "class", "record"}
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


def has_test_importer(
    path: str,
    reverse_adj: dict[str, list[EdgeSnapshot]],
    max_hops: int = 2,
) -> bool:
    """Check whether any automated test file imports `path` within `max_hops`."""
    visited: set[str] = {path}
    queue: deque[tuple[str, int]] = deque([(path, 0)])
    while queue:
        cur, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for edge in reverse_adj.get(cur, ()):
            caller = edge.source_path
            if is_test_file(caller):
                return True
            if caller not in visited:
                visited.add(caller)
                queue.append((caller, depth + 1))
    return False


def build_suggested_test_command(test_files: list[str]) -> str | None:
    """Build a ready-to-copy CLI command for the affected test files."""
    if not test_files:
        return None

    py_tests = [p for p in test_files if p.endswith(".py")]
    ts_tests = [
        p for p in test_files if p.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"))
    ]
    go_tests = [p for p in test_files if p.endswith(".go")]
    rs_tests = [p for p in test_files if p.endswith(".rs")]
    java_tests = [p for p in test_files if p.endswith(".java")]

    commands: list[str] = []
    if py_tests:
        commands.append(f"uv run pytest {' '.join(py_tests[:6])}")
    if ts_tests:
        commands.append(f"npx vitest run {' '.join(ts_tests[:6])}")
    if go_tests:
        pkg_dirs: list[str] = []
        for p in go_tests:
            d = posixpath.dirname(p)
            pkg = f"./{d}" if d else "."
            if pkg not in pkg_dirs:
                pkg_dirs.append(pkg)
        commands.append(f"go test {' '.join(pkg_dirs[:6])}")
    if rs_tests:
        commands.append("cargo test")
    if java_tests:
        stems = [posixpath.basename(p)[: -len(".java")] for p in java_tests[:6]]
        commands.append(f"mvn test -Dtest={','.join(stems)}")

    return " && ".join(commands) if commands else None


class BlastRadiusCalculator:
    """Computes symbol-aware downstream dependents, test suite split, and risk score."""

    def calculate(
        self,
        nodes: list[NodeSnapshot],
        edges: list[EdgeSnapshot],
        changed_files: list[str],
        changed_symbols_by_file: dict[str, set[str]] | None = None,
        max_depth: int = 3,
        *,
        top_level_edited_files: set[str] | None = None,
        candidate_doc_files: list[str] | None = None,
    ) -> BlastRadiusResult:
        """Run symbol-propagating reverse BFS from changed files and score blast radius."""
        node_map = {n.path: n for n in nodes}
        changed_symbols = changed_symbols_by_file or {}
        top_level_edits = top_level_edited_files or set()

        # Reverse adjacency: if target changes, all sources importing target may be impacted
        reverse_adj: dict[str, list[EdgeSnapshot]] = {}
        for edge in edges:
            reverse_adj.setdefault(edge.target_path, []).append(edge)

        direct: list[str] = []
        seen: set[str] = set()
        # None = module-wide impact (all importers hard-impacted); set[str] = specific symbols
        active_symbols_by_node: dict[str, set[str] | None] = {}

        for raw_path in changed_files:
            try:
                norm_path = normalize_repo_path(raw_path)
            except ValueError:
                continue
            if norm_path in node_map and norm_path not in seen:
                seen.add(norm_path)
                direct.append(norm_path)
                raw_syms = changed_symbols.get(norm_path, set())
                if norm_path in top_level_edits or not raw_syms:
                    active_symbols_by_node[norm_path] = None
                else:
                    active_symbols_by_node[norm_path] = self._expand_intra_file_type_deps(
                        raw_syms,
                        node_map[norm_path].exports,
                    )

        hops: dict[int, list[str]] = {1: [], 2: [], 3: []}
        impacted_edges: list[ImpactedEdgeDetail] = []
        symbol_matched_files: set[str] = set()
        co_located_candidates: set[str] = set()
        impacted_test_set: set[str] = set()

        queue: deque[tuple[str, int]] = deque((path, 0) for path in direct)
        while queue:
            current_path, depth = queue.popleft()
            if depth >= max_depth:
                continue

            active_syms = active_symbols_by_node.get(current_path)
            explicit_syms_for_match = (
                active_syms
                if active_syms is not None
                else changed_symbols.get(current_path, set())
            )

            for rev_edge in sorted(
                reverse_adj.get(current_path, []),
                key=lambda item: (item.source_path, item.edge_type),
            ):
                dependent = rev_edge.source_path
                if dependent not in node_map:
                    continue

                sym_match = self._symbols_overlap(
                    explicit_syms_for_match, rev_edge.imported_symbols
                )
                is_disjoint_named_import = (
                    active_syms is not None
                    and len(active_syms) > 0
                    and len(rev_edge.imported_symbols) > 0
                    and "*" not in rev_edge.imported_symbols
                    and not sym_match
                )

                if is_disjoint_named_import:
                    co_located_candidates.add(dependent)
                    impacted_edges.append(
                        ImpactedEdgeDetail(
                            source=dependent,
                            target=current_path,
                            edge_type=rev_edge.edge_type,
                            imported_symbols=list(rev_edge.imported_symbols),
                            symbol_match=False,
                            impact_tier="co_located",
                        )
                    )
                    continue

                if sym_match and not is_test_file(dependent):
                    symbol_matched_files.add(dependent)

                impacted_edges.append(
                    ImpactedEdgeDetail(
                        source=dependent,
                        target=current_path,
                        edge_type=rev_edge.edge_type,
                        imported_symbols=list(rev_edge.imported_symbols),
                        symbol_match=sym_match,
                        impact_tier="hard",
                    )
                )

                # Separate downstream automated test files from production blast radius
                if is_test_file(dependent):
                    impacted_test_set.add(dependent)
                    continue

                propagated_syms = self._propagated_symbols_for_dependent(active_syms, rev_edge)
                if dependent in seen:
                    # Upgrade narrowed barrel symbols if a second incoming edge widens impact
                    prev_syms = active_symbols_by_node.get(dependent)
                    if prev_syms is not None:
                        if propagated_syms is None:
                            active_symbols_by_node[dependent] = None
                            queue.append((dependent, depth + 1))
                        elif not propagated_syms.issubset(prev_syms):
                            active_symbols_by_node[dependent] = prev_syms | propagated_syms
                            queue.append((dependent, depth + 1))
                    continue

                next_depth = depth + 1
                seen.add(dependent)
                active_symbols_by_node[dependent] = propagated_syms
                if next_depth in hops:
                    hops[next_depth].append(dependent)
                queue.append((dependent, next_depth))

        co_located_only = sorted(co_located_candidates - seen - impacted_test_set)
        prod_direct = [p for p in direct if not is_test_file(p)]
        prod_impacted_all = sorted(p for p in seen if not is_test_file(p))

        # Check coverage gaps across direct + 1-hop production files
        uncovered_files = sorted(
            p
            for p in {*prod_direct, *hops[1]}
            if not is_test_file(p) and not has_test_importer(p, reverse_adj, max_hops=2)
        )

        # Also include directly edited test files in suggested test command
        all_relevant_tests = sorted(
            impacted_test_set | {p for p in direct if is_test_file(p)}
        )
        suggested_cmd = build_suggested_test_command(all_relevant_tests)

        prod_node_count = sum(1 for n in nodes if not is_test_file(n.path))
        effective_repo_files = max(prod_node_count or len(nodes), 1)

        if prod_impacted_all:
            max_in_degree = max(
                (node_map[p].in_degree for p in prod_impacted_all if p in node_map),
                default=0,
            )
            sensitive_boundaries = self._find_sensitive_boundaries(prod_impacted_all)
            score = self._compute_score(
                total_repo_files=effective_repo_files,
                direct_count=len(prod_direct) or len(direct),
                hop_1_count=len(hops[1]),
                hop_2_count=len(hops[2]),
                hop_3_count=len(hops[3]),
                max_in_degree=max_in_degree,
                symbol_match_count=len(symbol_matched_files),
                boundary_count=len(sensitive_boundaries),
            )
        elif direct:
            # Test-only PR change: keep deterministic risk low
            max_in_degree = max(
                (node_map[p].in_degree for p in direct if p in node_map),
                default=0,
            )
            sensitive_boundaries = []
            score = min(18, max(4, round((len(direct) / max(len(nodes), 1)) * 40)))
        else:
            max_in_degree = 0
            sensitive_boundaries = []
            score = 0

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
            co_located_files=co_located_only,
            impacted_test_files=sorted(impacted_test_set),
            uncovered_files=uncovered_files,
            candidate_doc_files=sorted(set(candidate_doc_files or [])),
            suggested_test_command=suggested_cmd,
        )

    def _expand_intra_file_type_deps(
        self,
        modified_syms: set[str],
        exports: list[dict[str, object]],
    ) -> set[str] | None:
        """Propagate modified type/interface names to same-file functions referencing them."""
        expanded = set(modified_syms)
        export_by_name = {
            str(item["name"]): item
            for item in exports
            if isinstance(item.get("name"), str)
        }
        modified_types = {
            sym
            for sym in modified_syms
            if str(export_by_name.get(sym, {}).get("kind", "")) in _TYPE_EXPORT_KINDS
        }
        if not modified_types:
            return expanded

        referenced_any = False
        for exp in exports:
            exp_name = exp.get("name")
            sig = exp.get("signature")
            if not isinstance(exp_name, str) or not isinstance(sig, str) or exp_name in expanded:
                continue
            for type_name in modified_types:
                if re.search(rf"\b{re.escape(type_name)}\b", sig):
                    expanded.add(exp_name)
                    referenced_any = True
        # If a type/interface changed and no export signature mentioned it explicitly
        # (e.g. return type inferred or multi-line signature truncated), stay conservative.
        if not referenced_any:
            return None
        return expanded

    def _propagated_symbols_for_dependent(
        self,
        active_syms: set[str] | None,
        rev_edge: EdgeSnapshot,
    ) -> set[str] | None:
        """Preserve narrowed symbol sets through barrel re-exports (`re_export`)."""
        if rev_edge.edge_type != "re_export":
            return None
        if active_syms is None:
            if rev_edge.imported_symbols and "*" not in rev_edge.imported_symbols:
                return set(rev_edge.imported_symbols)
            return None
        if "*" in rev_edge.imported_symbols or not rev_edge.imported_symbols:
            return set(active_syms)
        overlap = active_syms.intersection(rev_edge.imported_symbols)
        return overlap if overlap else None

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
