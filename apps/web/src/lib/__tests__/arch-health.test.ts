import { describe, expect, it } from "vitest";

import {
  computeClientArchHealth,
  findShortestCausalChain,
  isTestFilePath,
} from "@/lib/arch-health";
import { BlastRadiusResultSchema } from "@/lib/schemas/analysis";
import { GraphResponseSchema } from "@/lib/schemas/repo";

describe("arch-health & causal chain utilities", () => {
  it("classifies test paths across languages", () => {
    expect(isTestFilePath("src/lib/__tests__/token.test.ts")).toBe(true);
    expect(isTestFilePath("apps/api/tests/test_parser.py")).toBe(true);
    expect(isTestFilePath("pkg/auth/verify_test.go")).toBe(true);
    expect(isTestFilePath("src/TokenGuardTest.java")).toBe(true);
    expect(isTestFilePath("src/services/billing.ts")).toBe(false);
  });

  it("detects circular dependencies and upward layer violations", () => {
    const graph = GraphResponseSchema.parse({
      repository_id: "repo-1",
      snapshot_id: "snap-1",
      commit_sha: "abc1234",
      file_count: 4,
      edge_count: 3,
      nodes: [
        {
          id: "n1",
          path: "src/services/order.ts",
          language: "typescript",
          module_group: "src/services",
          loc: 120,
          exports: [],
          in_degree: 2,
          out_degree: 1,
        },
        {
          id: "n2",
          path: "src/services/stock.ts",
          language: "typescript",
          module_group: "src/services",
          loc: 90,
          exports: [],
          in_degree: 1,
          out_degree: 1,
        },
        {
          id: "n3",
          path: "src/db/repo.ts",
          language: "typescript",
          module_group: "src/db",
          loc: 70,
          exports: [],
          in_degree: 0,
          out_degree: 1,
        },
        {
          id: "n4",
          path: "src/routes/api.ts",
          language: "typescript",
          module_group: "src/routes",
          loc: 65,
          exports: [],
          in_degree: 1,
          out_degree: 1,
        },
      ],
      edges: [
        {
          id: "e1",
          source_node_id: "n1",
          target_node_id: "n2",
          source_path: "src/services/order.ts",
          target_path: "src/services/stock.ts",
          edge_type: "import",
          imported_symbols: ["reserve"],
        },
        {
          id: "e2",
          source_node_id: "n2",
          target_node_id: "n1",
          source_path: "src/services/stock.ts",
          target_path: "src/services/order.ts",
          edge_type: "import",
          imported_symbols: ["Order"],
        },
        {
          id: "e3",
          source_node_id: "n3",
          target_node_id: "n4",
          source_path: "src/db/repo.ts",
          target_path: "src/routes/api.ts",
          edge_type: "import",
          imported_symbols: ["QueryDto"],
        },
      ],
    });

    const health = computeClientArchHealth(graph);
    expect(health.cycle_count).toBe(1);
    expect(health.cycles[0]?.cycle_paths).toEqual([
      "src/services/order.ts",
      "src/services/stock.ts",
      "src/services/order.ts",
    ]);
    expect(health.layer_violation_count).toBe(1);
    expect(health.layer_violations[0]?.source_layer).toBe("data");
    expect(health.layer_violations[0]?.target_layer).toBe("presentation");
  });

  it("reconstructs the shortest hard-impact causal chain back to modified file", () => {
    const blast = BlastRadiusResultSchema.parse({
      direct: ["src/lib/token.ts"],
      hop_1: ["src/middleware/auth.ts"],
      hop_2: ["src/routes/checkout.ts"],
      hop_3: [],
      score: 68,
      deterministic_risk: "high",
      max_in_degree: 3,
      sensitive_boundaries_touched: ["auth"],
      symbol_matched_files: ["src/middleware/auth.ts"],
      impacted_edges: [
        {
          source: "src/middleware/auth.ts",
          target: "src/lib/token.ts",
          edge_type: "import",
          imported_symbols: ["verifyToken"],
          symbol_match: true,
          impact_tier: "hard",
        },
        {
          source: "src/routes/checkout.ts",
          target: "src/middleware/auth.ts",
          edge_type: "import",
          imported_symbols: ["requireAuth"],
          symbol_match: false,
          impact_tier: "hard",
        },
      ],
    });

    const chain = findShortestCausalChain("src/routes/checkout.ts", blast);
    expect(chain).toHaveLength(2);
    expect(chain[0]?.sourcePath).toBe("src/routes/checkout.ts");
    expect(chain[0]?.targetPath).toBe("src/middleware/auth.ts");
    expect(chain[1]?.sourcePath).toBe("src/middleware/auth.ts");
    expect(chain[1]?.targetPath).toBe("src/lib/token.ts");
    expect(chain[1]?.symbolMatch).toBe(true);
  });
});
