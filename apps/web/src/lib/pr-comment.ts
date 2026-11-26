import {
  PRCommentResponseSchema,
  type BlastRadiusResult,
  type PRAnalysisResponse,
  type PRCommentResponse,
} from "@/lib/schemas/analysis";

const MAX_FILES_PER_TIER = 8;
const MAX_MERMAID_EDGES = 20;
const MAX_FLOWS = 5;

function formatFileList(paths: string[], limit: number = MAX_FILES_PER_TIER): string {
  if (paths.length === 0) {
    return "—";
  }
  const shown = paths.slice(0, limit).map((p) => `\`${p}\``);
  const remainder = paths.length - limit;
  if (remainder > 0) {
    shown.push(`*(+${remainder} more)*`);
  }
  return shown.join(", ");
}

function sanitizeMermaidLabel(text: string): string {
  return text.replaceAll('"', "'").replaceAll("|", "/").replaceAll("\n", " ").trim();
}

function renderMermaidSubgraph(blastRadius: BlastRadiusResult): string[] {
  if (blastRadius.direct.length === 0) {
    return [];
  }

  const directSet = new Set(blastRadius.direct);
  const hop1Set = new Set(blastRadius.hop_1);
  const relevantNodes = [
    ...[...directSet].sort(),
    ...[...hop1Set].filter((p) => !directSet.has(p)).sort(),
  ];

  const edgeMap = new Map<string, { source: string; target: string; symbols: string[] }>();
  for (const edge of blastRadius.impacted_edges) {
    if (directSet.has(edge.target) && (hop1Set.has(edge.source) || directSet.has(edge.source))) {
      const key = `${edge.source}=>${edge.target}`;
      let entry = edgeMap.get(key);
      if (!entry) {
        entry = { source: edge.source, target: edge.target, symbols: [] };
        edgeMap.set(key, entry);
      }
      for (const sym of edge.imported_symbols) {
        if (!entry.symbols.includes(sym)) {
          entry.symbols.push(sym);
        }
      }
    }
  }

  const sortedEdges = [...edgeMap.values()]
    .sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target))
    .slice(0, MAX_MERMAID_EDGES);

  const nodeOrder = [...relevantNodes];
  const nodeSeen = new Set(nodeOrder);
  for (const edge of sortedEdges) {
    for (const endpoint of [edge.source, edge.target]) {
      if (!nodeSeen.has(endpoint)) {
        nodeSeen.add(endpoint);
        nodeOrder.push(endpoint);
      }
    }
  }

  const nodeIds = new Map<string, string>();
  nodeOrder.forEach((path, idx) => {
    nodeIds.set(path, `N${idx}`);
  });

  const lines: string[] = [
    "### Blast-Radius Subgraph (Direct + 1-Hop)",
    "",
    "```mermaid",
    "flowchart LR",
    "  classDef direct fill:#F59E0B,color:#111827,stroke:#B45309;",
    "  classDef hop1 fill:#EF4444,color:#FFFFFF,stroke:#991B1B;",
  ];

  for (const path of nodeOrder) {
    const nid = nodeIds.get(path);
    if (!nid) continue;
    lines.push(`  ${nid}["${sanitizeMermaidLabel(path)}"]`);
  }

  for (const edge of sortedEdges) {
    const srcId = nodeIds.get(edge.source);
    const dstId = nodeIds.get(edge.target);
    if (!srcId || !dstId) continue;
    if (edge.symbols.length > 0) {
      const base = sanitizeMermaidLabel(edge.symbols.slice(0, 3).join(", "));
      const symLabel = edge.symbols.length > 3 ? `${base}, ...` : base;
      lines.push(`  ${srcId} -->|"${symLabel}"| ${dstId}`);
    } else {
      lines.push(`  ${srcId} --> ${dstId}`);
    }
  }

  const directIds = [...directSet]
    .sort()
    .map((p) => nodeIds.get(p))
    .filter((id): id is string => Boolean(id));
  const hop1Ids = [...hop1Set]
    .filter((p) => !directSet.has(p))
    .sort()
    .map((p) => nodeIds.get(p))
    .filter((id): id is string => Boolean(id));

  if (directIds.length > 0) {
    lines.push(`  class ${directIds.join(",")} direct;`);
  }
  if (hop1Ids.length > 0) {
    lines.push(`  class ${hop1Ids.join(",")} hop1;`);
  }

  lines.push("```", "");
  return lines;
}

function formatPatchBlock(patch: string): string[] {
  const stripped = patch.trim();
  if (stripped.startsWith("```")) {
    return [stripped, ""];
  }
  return ["```diff", stripped, "```", ""];
}

export function renderPRCommentMarkdown(analysis: PRAnalysisResponse): string {
  const br = analysis.blast_radius;
  const report = analysis.ai_report;
  const telemetry = analysis.citation_telemetry;

  const effectiveRisk = report ? report.overall_risk : br.deterministic_risk;
  const breaking = report
    ? report.breaking_change_detected
    : effectiveRisk === "high" || effectiveRisk === "critical";

  const prHeading =
    analysis.pr_number !== null && !analysis.pr_title.includes(`#${analysis.pr_number}`)
      ? `#${analysis.pr_number} — ${analysis.pr_title}`
      : analysis.pr_title;

  const badges = [
    `**Risk:** \`${effectiveRisk.toUpperCase()}\``,
    `**Score:** \`${br.score}/100\``,
    `**Breaking:** \`${breaking ? "YES" : "NO"}\``,
  ];
  if (telemetry) {
    const strippedNote =
      telemetry.hallucination_caught > 0 ? ` (${telemetry.hallucination_caught} stripped)` : "";
    badges.push(
      `**Citations:** \`${telemetry.valid_cited_paths}/${telemetry.total_cited_paths} verified\`${strippedNote}`
    );
  }

  const lines: string[] = [
    "## ArchRadar Blast-Radius Report",
    "",
    `**PR:** ${prHeading}  `,
    badges.join(" · "),
    "",
  ];

  if (report) {
    lines.push(`> ${report.executive_summary}`, "");
  } else {
    lines.push(
      "> Deterministic AST & reverse-BFS analysis only (`run_ai=false`). Enable AI analysis for impacted flow narratives and doc-drift patches.",
      ""
    );
  }

  lines.push(
    "### Blast-Radius Summary",
    "",
    "| Tier | Count | Files |",
    "| :--- | ---: | :--- |",
    `| Direct (Depth 0) | ${br.direct.length} | ${formatFileList(br.direct)} |`,
    `| 1-Hop Dependents | ${br.hop_1.length} | ${formatFileList(br.hop_1)} |`,
    `| 2-Hop Dependents | ${br.hop_2.length} | ${formatFileList(br.hop_2)} |`,
    `| 3-Hop Dependents | ${br.hop_3.length} | ${formatFileList(br.hop_3)} |`,
    ""
  );

  if (br.sensitive_boundaries_touched.length > 0) {
    const boundaries = br.sensitive_boundaries_touched.map((b) => `\`${b}\``).join(", ");
    lines.push(`**Sensitive Boundaries Touched:** ${boundaries}`, "");
  }

  lines.push(...renderMermaidSubgraph(br));

  if (report && report.impacted_flows.length > 0) {
    lines.push("### Impacted Flows", "");
    for (const flow of report.impacted_flows.slice(0, MAX_FLOWS)) {
      const cited = [
        flow.entry_file,
        ...flow.affected_files.filter((f) => f !== flow.entry_file),
      ];
      const filesStr = cited.map((p) => `\`${p}\``).join(", ");
      lines.push(
        `- **[${flow.severity.toUpperCase()}] ${flow.title}** — ${filesStr}`,
        `  - ${flow.explanation}`,
        `  - *Suggested test:* ${flow.suggested_test}`
      );
    }
    lines.push("");
  }

  if (report && report.doc_drift_alerts.length > 0) {
    lines.push("### Documentation Drift Alerts", "");
    for (const alert of report.doc_drift_alerts) {
      lines.push(`**\`${alert.doc_file}\` · ${alert.section}** — ${alert.reason}`, "");
      lines.push(...formatPatchBlock(alert.suggested_markdown_patch));
    }
  }

  if (report && report.reviewer_checklist.length > 0) {
    lines.push("### Reviewer Checklist", "");
    for (const item of report.reviewer_checklist) {
      lines.push(`- [ ] ${item}`);
    }
    lines.push("");
  }

  const modelLabel = analysis.model_used ?? "deterministic-only";
  lines.push(
    "---",
    `<sub>Generated by ArchRadar · Model: \`${modelLabel}\` · ${analysis.prompt_tokens}+${analysis.completion_tokens} tok · $${analysis.estimated_cost_usd.toFixed(6)} · ${analysis.latency_ms}ms</sub>`
  );

  return lines.join("\n");
}

export function buildOfflinePRComment(analysis: PRAnalysisResponse): PRCommentResponse {
  const markdown = renderPRCommentMarkdown(analysis);
  return PRCommentResponseSchema.parse({
    analysis_id: analysis.id,
    markdown,
    character_count: markdown.length,
  });
}
