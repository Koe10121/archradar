"""Deterministic GitHub Markdown PR comment renderer for ArchRadar analyses."""

from __future__ import annotations

from app.schemas.analysis import BlastRadiusResult, PRAnalysisResponse, PRCommentResponse

_MAX_FILES_PER_TIER = 8
_MAX_MERMAID_EDGES = 20
_MAX_FLOWS = 5


def _format_file_list(paths: list[str], limit: int = _MAX_FILES_PER_TIER) -> str:
    if not paths:
        return "—"
    shown = [f"`{p}`" for p in paths[:limit]]
    remainder = len(paths) - limit
    if remainder > 0:
        shown.append(f"*(+{remainder} more)*")
    return ", ".join(shown)


def _sanitize_mermaid_label(text: str) -> str:
    return text.replace('"', "'").replace("|", "/").replace("\n", " ").strip()


def _render_mermaid_subgraph(blast_radius: BlastRadiusResult) -> list[str]:
    if not blast_radius.direct:
        return []

    direct_set = set(blast_radius.direct)
    hop1_set = set(blast_radius.hop_1)
    relevant_nodes = sorted(direct_set) + sorted(p for p in hop1_set if p not in direct_set)

    # Deduplicate and sort direct + 1-hop edges deterministically
    edge_symbols: dict[tuple[str, str], list[str]] = {}
    for edge in blast_radius.impacted_edges:
        if edge.target in direct_set and (edge.source in hop1_set or edge.source in direct_set):
            key = (edge.source, edge.target)
            syms = edge_symbols.setdefault(key, [])
            for sym in edge.imported_symbols:
                if sym not in syms:
                    syms.append(sym)

    sorted_edges = sorted(edge_symbols.items(), key=lambda item: item[0])[:_MAX_MERMAID_EDGES]

    # Ensure every edge endpoint appears in node map
    node_order = list(relevant_nodes)
    node_seen = set(node_order)
    for src, dst in (pair for pair, _ in sorted_edges):
        for endpoint in (src, dst):
            if endpoint not in node_seen:
                node_seen.add(endpoint)
                node_order.append(endpoint)

    node_ids = {path: f"N{idx}" for idx, path in enumerate(node_order)}

    lines: list[str] = [
        "### Blast-Radius Subgraph (Direct + 1-Hop)",
        "",
        "```mermaid",
        "flowchart LR",
        "  classDef direct fill:#F59E0B,color:#111827,stroke:#B45309;",
        "  classDef hop1 fill:#EF4444,color:#FFFFFF,stroke:#991B1B;",
    ]

    for path in node_order:
        nid = node_ids[path]
        label = _sanitize_mermaid_label(path)
        lines.append(f'  {nid}["{label}"]')

    for (src, dst), syms in sorted_edges:
        src_id = node_ids[src]
        dst_id = node_ids[dst]
        if syms:
            sym_label = _sanitize_mermaid_label(", ".join(syms[:3]))
            if len(syms) > 3:
                sym_label += ", ..."
            lines.append(f'  {src_id} -->|"{sym_label}"| {dst_id}')
        else:
            lines.append(f"  {src_id} --> {dst_id}")

    direct_ids = [node_ids[p] for p in sorted(direct_set) if p in node_ids]
    hop1_ids = [node_ids[p] for p in sorted(hop1_set - direct_set) if p in node_ids]
    if direct_ids:
        lines.append(f"  class {','.join(direct_ids)} direct;")
    if hop1_ids:
        lines.append(f"  class {','.join(hop1_ids)} hop1;")

    lines.extend(["```", ""])
    return lines


def _format_patch_block(patch: str) -> list[str]:
    stripped = patch.strip()
    if stripped.startswith("```"):
        return [stripped, ""]
    return ["```diff", stripped, "```", ""]


def render_pr_comment(analysis: PRAnalysisResponse) -> str:
    """Render a deterministic GitHub Markdown PR comment from a PRAnalysisResponse."""
    br = analysis.blast_radius
    report = analysis.ai_report
    telemetry = analysis.citation_telemetry

    effective_risk = report.overall_risk if report else br.deterministic_risk
    breaking = (
        report.breaking_change_detected
        if report
        else effective_risk in {"high", "critical"}
    )

    pr_heading = analysis.pr_title
    if analysis.pr_number is not None and f"#{analysis.pr_number}" not in analysis.pr_title:
        pr_heading = f"#{analysis.pr_number} — {analysis.pr_title}"

    badges = [
        f"**Risk:** `{effective_risk.upper()}`",
        f"**Score:** `{br.score}/100`",
        f"**Breaking:** `{'YES' if breaking else 'NO'}`",
    ]
    if telemetry is not None:
        citation_str = f"`{telemetry.valid_cited_paths}/{telemetry.total_cited_paths} verified`"
        if telemetry.hallucination_caught > 0:
            citation_str += f" ({telemetry.hallucination_caught} stripped)"
        badges.append(f"**Citations:** {citation_str}")

    lines: list[str] = [
        "## ArchRadar Blast-Radius Report",
        "",
        f"**PR:** {pr_heading}  ",
        " · ".join(badges),
        "",
    ]

    if report is not None:
        lines.extend([f"> {report.executive_summary}", ""])
    else:
        lines.extend(
            [
                "> Deterministic AST & reverse-BFS analysis only (`run_ai=false`). "
                "Enable AI analysis for impacted flow narratives and doc-drift patches.",
                "",
            ]
        )

    lines.extend(
        [
            "### Blast-Radius Summary",
            "",
            "| Tier | Count | Files |",
            "| :--- | ---: | :--- |",
            f"| Direct (Depth 0) | {len(br.direct)} | {_format_file_list(br.direct)} |",
            f"| 1-Hop Dependents | {len(br.hop_1)} | {_format_file_list(br.hop_1)} |",
            f"| 2-Hop Dependents | {len(br.hop_2)} | {_format_file_list(br.hop_2)} |",
            f"| 3-Hop Dependents | {len(br.hop_3)} | {_format_file_list(br.hop_3)} |",
            "",
        ]
    )

    if br.sensitive_boundaries_touched:
        boundaries = ", ".join(f"`{b}`" for b in br.sensitive_boundaries_touched)
        lines.extend([f"**Sensitive Boundaries Touched:** {boundaries}", ""])

    lines.extend(_render_mermaid_subgraph(br))

    if report is not None and report.impacted_flows:
        lines.extend(["### Impacted Flows", ""])
        for flow in report.impacted_flows[:_MAX_FLOWS]:
            cited = [flow.entry_file, *(f for f in flow.affected_files if f != flow.entry_file)]
            files_str = ", ".join(f"`{p}`" for p in cited)
            lines.extend(
                [
                    f"- **[{flow.severity.upper()}] {flow.title}** — {files_str}",
                    f"  - {flow.explanation}",
                    f"  - *Suggested test:* {flow.suggested_test}",
                ]
            )
        lines.append("")

    if report is not None and report.doc_drift_alerts:
        lines.extend(["### Documentation Drift Alerts", ""])
        for alert in report.doc_drift_alerts:
            lines.extend(
                [
                    f"**`{alert.doc_file}` · {alert.section}** — {alert.reason}",
                    "",
                ]
            )
            lines.extend(_format_patch_block(alert.suggested_markdown_patch))

    if report is not None and report.reviewer_checklist:
        lines.extend(["### Reviewer Checklist", ""])
        for item in report.reviewer_checklist:
            lines.append(f"- [ ] {item}")
        lines.append("")

    model_label = analysis.model_used or "deterministic-only"
    lines.extend(
        [
            "---",
            (
                f"<sub>Generated by ArchRadar · Model: `{model_label}` · "
                f"{analysis.prompt_tokens}+{analysis.completion_tokens} tok · "
                f"${analysis.estimated_cost_usd:.6f} · {analysis.latency_ms}ms</sub>"
            ),
        ]
    )
    return "\n".join(lines)


def build_pr_comment_response(analysis: PRAnalysisResponse) -> PRCommentResponse:
    """Wrap rendered PR comment Markdown into the API PRCommentResponse contract."""
    markdown = render_pr_comment(analysis)
    return PRCommentResponse(
        analysis_id=analysis.id,
        markdown=markdown,
        character_count=len(markdown),
    )


def format_pending_pr_comment(repository: str, pr_number: int | None, action: str) -> str:
    """Render a dry-run placeholder comment when a webhook arrives before PR analysis runs."""
    repo_label = repository or "unknown-repository"
    pr_label = f"#{pr_number}" if pr_number is not None else "PR"
    return "\n".join(
        [
            "## ArchRadar Blast-Radius Report (Dry-Run Pending)",
            "",
            f"**Repository:** `{repo_label}` · **PR:** `{pr_label}` · **Action:** `{action}`",
            "",
            "> Webhook verified via HMAC-SHA256. No persisted blast-radius analysis exists "
            "yet for this PR in local dry-run mode.",
        ]
    )
