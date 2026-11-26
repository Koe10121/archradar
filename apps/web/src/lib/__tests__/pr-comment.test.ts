import { describe, expect, it } from "vitest";

import { DEMO_PR_SCENARIOS } from "@/lib/demo-data";
import { buildOfflinePRComment, renderPRCommentMarkdown } from "@/lib/pr-comment";
import { type PRAnalysisResponse } from "@/lib/schemas/analysis";

describe("PR Comment Markdown Renderer", () => {
  it("renders badges, hop summary, Mermaid subgraph, flows, doc drift, and checklist for PR #42", () => {
    const pr42 = DEMO_PR_SCENARIOS[0]!;
    const comment = buildOfflinePRComment(pr42);

    expect(comment.analysis_id).toBe(pr42.id);
    expect(comment.character_count).toBe(comment.markdown.length);
    expect(comment.markdown).toContain("## ArchRadar Blast-Radius Report");
    expect(comment.markdown).toContain("**Risk:** `CRITICAL`");
    expect(comment.markdown).toContain("**Score:** `90/100`");
    expect(comment.markdown).toContain("**Breaking:** `YES`");
    expect(comment.markdown).toContain("| Direct (Depth 0) | 1 |");
    expect(comment.markdown).toContain("| 1-Hop Dependents | 3 |");
    expect(comment.markdown).toContain("```mermaid");
    expect(comment.markdown).toContain("flowchart LR");
    expect(comment.markdown).toContain('N1["src/middleware/auth.ts"]');
    expect(comment.markdown).toContain('N1 -->|"verifyToken"| N0');
    expect(comment.markdown).toContain("### Impacted Flows");
    expect(comment.markdown).toContain("### Documentation Drift Alerts");
    expect(comment.markdown).not.toContain("```diff\n```diff");
    expect(comment.markdown).toContain("### Reviewer Checklist");
    expect(comment.markdown).toContain("- [ ] ");
  });

  it("renders low-risk non-breaking PR #47 cleanly", () => {
    const pr47 = DEMO_PR_SCENARIOS[2]!;
    const md = renderPRCommentMarkdown(pr47);

    expect(md).toContain("**Risk:** `LOW`");
    expect(md).toContain("**Score:** `17/100`");
    expect(md).toContain("**Breaking:** `NO`");
    expect(md).toContain("src/lib/formatters.ts");
    expect(md).not.toContain("### Documentation Drift Alerts");
  });

  it("handles deterministic-only analyses without ai_report", () => {
    const base = DEMO_PR_SCENARIOS[1]!;
    const detOnly: PRAnalysisResponse = {
      ...base,
      pr_number: 88,
      pr_title: "Harden HMAC check",
      ai_report: null,
      citation_telemetry: null,
      model_used: null,
    };
    const md = renderPRCommentMarkdown(detOnly);

    expect(md).toContain("#88 — Harden HMAC check");
    expect(md).toContain("**Risk:** `HIGH`");
    expect(md).toContain("**Breaking:** `YES`");
    expect(md).toContain("Deterministic AST & reverse-BFS analysis only (`run_ai=false`)");
    expect(md).toContain("`deterministic-only`");
    expect(md).not.toContain("### Impacted Flows");
  });
});
