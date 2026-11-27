import { describe, expect, it } from "vitest";

import { DEMO_BILLING_GRAPH } from "@/lib/demo-data";
import { isPlausibleGeminiKey, maskApiKey } from "@/lib/gemini-key";
import { type GraphResponse } from "@/lib/schemas/repo";
import { buildSampleDiffForGraph } from "@/lib/sample-diff";

describe("BYOK Gemini Key Helpers", () => {
  it("validates plausible key shapes and rejects whitespace", () => {
    expect(isPlausibleGeminiKey("AIzaSyD1234567890abcdefg")).toBe(true);
    expect(isPlausibleGeminiKey("short")).toBe(false);
    expect(isPlausibleGeminiKey("AIzaSyD1234567890 abcdefg")).toBe(false);
  });

  it("masks API keys without exposing middle characters", () => {
    expect(maskApiKey("AIzaSyD1234567890wxyz")).toBe("AIza••••••wxyz");
    expect(maskApiKey("short")).toBe("••••");
    expect(maskApiKey("")).toBe("");
  });
});

describe("buildSampleDiffForGraph", () => {
  it("targets the highest in_degree node and synthesizes a valid unified diff", () => {
    const sample = buildSampleDiffForGraph(DEMO_BILLING_GRAPH);
    expect(sample.title).toContain("src/lib/token.ts");
    expect(sample.diff).toContain("diff --git a/src/lib/token.ts b/src/lib/token.ts");
    expect(sample.diff).toContain("--- a/src/lib/token.ts");
    expect(sample.diff).toContain("+++ b/src/lib/token.ts");
  });

  it("handles Python and Go graphs cleanly", () => {
    const pyGraph: GraphResponse = {
      repository_id: "r1",
      snapshot_id: "s1",
      commit_sha: "abc",
      file_count: 1,
      edge_count: 0,
      nodes: [
        {
          id: "n1",
          path: "app/core/auth.py",
          language: "python",
          module_group: "app/core",
          loc: 20,
          exports: [{ name: "verify_user", kind: "function", signature: "def verify_user():" }],
          in_degree: 4,
          out_degree: 0,
        },
      ],
      edges: [],
    };
    const sample = buildSampleDiffForGraph(pyGraph);
    expect(sample.diff).toContain("diff --git a/app/core/auth.py b/app/core/auth.py");
    expect(sample.diff).toContain("def verify_user(");
  });
});
