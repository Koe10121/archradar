import { describe, expect, it } from "vitest";

import {
  PRAnalysisResponseSchema,
  PRCommentResponseSchema,
} from "@/lib/schemas/analysis";
import {
  GraphResponseSchema,
  RepositorySummarySchema,
  SnapshotDiffResponseSchema,
} from "@/lib/schemas/repo";
import { TelemetrySummaryResponseSchema } from "@/lib/schemas/telemetry";
import {
  computeDemoSnapshotDiff,
  computeDemoTelemetrySummary,
  DEMO_BILLING_GRAPH,
  DEMO_BILLING_REPO_ID,
  DEMO_BILLING_SNAPSHOT_ID,
  DEMO_BILLING_V1_GRAPH,
  DEMO_BILLING_V1_SNAPSHOT_ID,
  DEMO_PR_SCENARIOS,
  DEMO_REPOSITORIES,
  DEMO_SNAPSHOTS_BY_REPO_ID,
} from "@/lib/demo-data";

describe("Zod API Schema Contracts", () => {
  it("validates repository, graph, and snapshot diff schemas", () => {
    for (const repo of DEMO_REPOSITORIES) {
      expect(RepositorySummarySchema.safeParse(repo).success).toBe(true);
    }
    expect(GraphResponseSchema.safeParse(DEMO_BILLING_GRAPH).success).toBe(true);

    const snaps = DEMO_SNAPSHOTS_BY_REPO_ID[DEMO_BILLING_REPO_ID] ?? [];
    expect(snaps.length).toBe(2);
    const diff = computeDemoSnapshotDiff(
      snaps[0]!,
      snaps[1]!,
      DEMO_BILLING_V1_GRAPH,
      DEMO_BILLING_GRAPH
    );
    expect(SnapshotDiffResponseSchema.safeParse(diff).success).toBe(true);

    const invalidGraph = { ...DEMO_BILLING_GRAPH, file_count: "twelve" };
    expect(GraphResponseSchema.safeParse(invalidGraph).success).toBe(false);
  });

  it("validates PR analysis, PR comment, and telemetry schemas and rejects invalid bounds", () => {
    for (const scenario of DEMO_PR_SCENARIOS) {
      expect(PRAnalysisResponseSchema.safeParse(scenario).success).toBe(true);
    }

    const validComment = {
      analysis_id: DEMO_PR_SCENARIOS[0]!.id,
      markdown: "## ArchRadar Blast-Radius Report",
      character_count: 34,
    };
    expect(PRCommentResponseSchema.safeParse(validComment).success).toBe(true);
    expect(
      PRCommentResponseSchema.safeParse({ ...validComment, character_count: -1 }).success
    ).toBe(false);

    const invalidAnalysis = {
      ...DEMO_PR_SCENARIOS[0]!,
      blast_radius: {
        ...DEMO_PR_SCENARIOS[0]!.blast_radius,
        score: 150,
      },
    };
    expect(PRAnalysisResponseSchema.safeParse(invalidAnalysis).success).toBe(false);

    const summary = computeDemoTelemetrySummary(DEMO_PR_SCENARIOS);
    expect(TelemetrySummaryResponseSchema.safeParse(summary).success).toBe(true);
    expect(
      TelemetrySummaryResponseSchema.safeParse({
        ...summary,
        risk_counts: { low: 0, medium: 0, high: 0 },
      }).success
    ).toBe(false);
  });

  it("ensures snapshot IDs match expected demo constants", () => {
    expect(DEMO_BILLING_V1_GRAPH.snapshot_id).toBe(DEMO_BILLING_V1_SNAPSHOT_ID);
    expect(DEMO_BILLING_GRAPH.snapshot_id).toBe(DEMO_BILLING_SNAPSHOT_ID);
  });
});
