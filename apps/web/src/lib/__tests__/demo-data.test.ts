import { describe, expect, it } from "vitest";

import {
  computeDemoSnapshotDiff,
  computeDemoTelemetrySummary,
  DEMO_BILLING_GRAPH,
  DEMO_BILLING_REPO_ID,
  DEMO_BILLING_V1_GRAPH,
  DEMO_PR_SCENARIOS,
  DEMO_SNAPSHOTS_BY_REPO_ID,
} from "@/lib/demo-data";
import { type PRAnalysisResponse } from "@/lib/schemas/analysis";

describe("computeDemoSnapshotDiff", () => {
  it("computes v1 -> v2 added/removed files, edges, and sorted centrality deltas", () => {
    const snaps = DEMO_SNAPSHOTS_BY_REPO_ID[DEMO_BILLING_REPO_ID] ?? [];
    const fromSnap = snaps[0]!;
    const toSnap = snaps[1]!;

    const diff = computeDemoSnapshotDiff(
      fromSnap,
      toSnap,
      DEMO_BILLING_V1_GRAPH,
      DEMO_BILLING_GRAPH
    );

    expect(diff.file_count_delta).toBe(3);
    expect(diff.edge_count_delta).toBe(5);
    expect(diff.added_files).toEqual([
      "src/lib/crypto.ts",
      "src/middleware/rate_limit.ts",
      "src/services/audit.ts",
      "src/workers/invoiceWorker.ts",
    ]);
    expect(diff.removed_files).toEqual(["src/lib/legacyBillingClient.ts"]);

    const addedPairs = diff.added_edges.map((e) => `${e.source_path}->${e.target_path}`);
    const removedPairs = diff.removed_edges.map((e) => `${e.source_path}->${e.target_path}`);
    expect(addedPairs).toContain("src/api/webhooks/stripe.ts->src/lib/crypto.ts");
    expect(removedPairs).toContain("src/services/billing.ts->src/lib/legacyBillingClient.ts");

    const byPath = new Map(diff.centrality_deltas.map((d) => [d.path, d]));
    expect(byPath.get("src/lib/token.ts")?.in_degree_delta).toBe(1);
    expect(byPath.get("src/middleware/auth.ts")?.in_degree_delta).toBe(-1);
    expect(byPath.get("src/api/routes/checkout.ts")?.in_degree_delta).toBe(2);
    expect(byPath.get("src/services/audit.ts")?.status).toBe("added");
    expect(byPath.get("src/lib/legacyBillingClient.ts")?.status).toBe("removed");
  });
});

describe("computeDemoTelemetrySummary", () => {
  it("returns zeroed summary when given an empty list", () => {
    const summary = computeDemoTelemetrySummary([]);
    expect(summary.total_analyses).toBe(0);
    expect(summary.median_latency_ms).toBe(0);
    expect(summary.projected_cost_per_1000_prs_usd).toBe(0);
    expect(summary.models).toEqual([]);
  });

  it("aggregates default demo PR scenarios accurately", () => {
    const summary = computeDemoTelemetrySummary(DEMO_PR_SCENARIOS);
    expect(summary.total_analyses).toBe(3);
    expect(summary.ai_enabled_analyses).toBe(3);
    expect(summary.deterministic_only_analyses).toBe(0);
    expect(summary.risk_counts).toEqual({ low: 1, medium: 0, high: 1, critical: 1 });
    expect(summary.median_latency_ms).toBe(1180);
    expect(summary.p95_latency_ms).toBe(1420);
    expect(summary.valid_cited_paths).toBe(12);
    expect(summary.citation_gate_intercepts).toBe(0);
    expect(summary.models[0]?.model).toBe("gemini-2.5-flash");
  });

  it("aggregates deterministic-only runs and citation gate intercepts", () => {
    const deterministicOnly: PRAnalysisResponse = {
      ...DEMO_PR_SCENARIOS[2]!,
      id: "22222222-2222-2222-2222-222222222222",
      ai_report: null,
      citation_telemetry: {
        total_cited_paths: 4,
        valid_cited_paths: 3,
        hallucination_caught: 1,
        stripped_paths: ["src/phantom.ts"],
      },
      model_used: null,
      prompt_tokens: 0,
      completion_tokens: 0,
      estimated_cost_usd: 0,
      latency_ms: 40,
    };

    const summary = computeDemoTelemetrySummary([...DEMO_PR_SCENARIOS, deterministicOnly]);
    expect(summary.total_analyses).toBe(4);
    expect(summary.ai_enabled_analyses).toBe(3);
    expect(summary.deterministic_only_analyses).toBe(1);
    expect(summary.citation_gate_intercepts).toBe(1);
    expect(summary.total_cited_paths).toBe(16);
    expect(summary.valid_cited_paths).toBe(15);
    expect(summary.models.map((m) => m.model)).toContain("deterministic-only");
  });
});
