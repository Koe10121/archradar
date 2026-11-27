import { type BlastRadiusResult } from "@/lib/schemas/analysis";
import {
  type ArchitectureHealth,
  type CycleFinding,
  type GraphEdge,
  type GraphResponse,
  type HotspotFinding,
  type LayerViolation,
} from "@/lib/schemas/repo";

export interface CausalHop {
  sourcePath: string;
  targetPath: string;
  importedSymbols: string[];
  edgeType: string;
  symbolMatch: boolean;
}

const TEST_DIRS = new Set([
  "test",
  "tests",
  "__tests__",
  "spec",
  "specs",
  "e2e",
  "cypress",
  "playwright",
]);

const SENSITIVE_BOUNDARIES = new Set([
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
]);

const DATA_SEGMENTS = new Set([
  "db",
  "database",
  "models",
  "entities",
  "migrations",
  "repositories_db",
  "persistence",
]);

const SERVICE_SEGMENTS = new Set(["services", "domain", "usecases", "parser", "workers"]);

const PRESENTATION_SEGMENTS = new Set([
  "routes",
  "controllers",
  "handlers",
  "ui",
  "components",
  "pages",
  "views",
  "webhooks",
]);

export function isTestFilePath(repoRelPath: string): boolean {
  const parts = repoRelPath.replaceAll("\\", "/").split("/").filter(Boolean);
  if (parts.length === 0) return false;
  for (const dir of parts.slice(0, -1)) {
    if (TEST_DIRS.has(dir.toLowerCase())) return true;
  }
  const name = parts[parts.length - 1]!;
  const lower = name.toLowerCase();
  if (lower.includes(".test.") || lower.includes(".spec.")) return true;
  if (lower.startsWith("test_") && lower.endsWith(".py")) return true;
  if (lower.endsWith("_test.py") || lower.endsWith("_test.go") || lower.endsWith("_test.rs")) {
    return true;
  }
  return name.endsWith("Test.java") || name.endsWith("Tests.java") || name.endsWith("IT.java");
}

function classifyArchLayer(path: string): "data" | "service" | "presentation" | null {
  const parts = path
    .replaceAll("\\", "/")
    .split("/")
    .slice(0, -1)
    .map((p) => p.toLowerCase())
    .filter(Boolean);
  for (let i = parts.length - 1; i >= 0; i -= 1) {
    const seg = parts[i]!;
    if (PRESENTATION_SEGMENTS.has(seg)) return "presentation";
    if (DATA_SEGMENTS.has(seg)) return "data";
    if (SERVICE_SEGMENTS.has(seg)) return "service";
  }
  return null;
}

function reconstructCycleRing(scc: string[], adj: Map<string, string[]>): string[] {
  const sccSet = new Set(scc);
  const sorted = [...scc].sort();
  const start = sorted[0]!;
  let bestRing: string[] | null = null;

  const startNeighbors = (adj.get(start) ?? []).filter((n) => sccSet.has(n)).sort();
  for (const firstNext of startNeighbors) {
    if (firstNext === start) return [start, start];
    const parent = new Map<string, string>([[firstNext, start]]);
    const queue: string[] = [firstNext];
    let found = false;

    while (queue.length > 0 && !found) {
      const cur = queue.shift()!;
      const nexts = (adj.get(cur) ?? []).filter((n) => sccSet.has(n)).sort();
      for (const nxt of nexts) {
        if (nxt === start) {
          const chain: string[] = [];
          let step = cur;
          while (step !== start) {
            chain.push(step);
            step = parent.get(step)!;
          }
          chain.reverse();
          const ring = [start, ...chain, start];
          if (!bestRing || ring.length < bestRing.length) {
            bestRing = ring;
          }
          found = true;
          break;
        }
        if (!parent.has(nxt)) {
          parent.set(nxt, cur);
          queue.push(nxt);
        }
      }
    }
  }
  return bestRing ?? [...sorted, sorted[0]!];
}

function detectCycles(prodPaths: string[], edges: GraphEdge[]): CycleFinding[] {
  const prodSet = new Set(prodPaths);
  const adj = new Map<string, string[]>();
  for (const p of prodPaths) adj.set(p, []);
  for (const e of edges) {
    if (prodSet.has(e.source_path) && prodSet.has(e.target_path)) {
      const list = adj.get(e.source_path)!;
      if (!list.includes(e.target_path)) list.push(e.target_path);
    }
  }
  for (const list of adj.values()) list.sort();

  let indexCounter = 0;
  const indices = new Map<string, number>();
  const lowlink = new Map<string, number>();
  const stack: string[] = [];
  const onStack = new Set<string>();
  const sccs: string[][] = [];

  for (const root of [...prodPaths].sort()) {
    if (indices.has(root)) continue;
    const callStack: Array<[string, number]> = [[root, 0]];
    indices.set(root, indexCounter);
    lowlink.set(root, indexCounter);
    indexCounter += 1;
    stack.push(root);
    onStack.add(root);

    while (callStack.length > 0) {
      const top = callStack[callStack.length - 1]!;
      const [v, neighborIdx] = top;
      const neighbors = adj.get(v) ?? [];
      if (neighborIdx < neighbors.length) {
        top[1] = neighborIdx + 1;
        const w = neighbors[neighborIdx]!;
        if (!indices.has(w)) {
          indices.set(w, indexCounter);
          lowlink.set(w, indexCounter);
          indexCounter += 1;
          stack.push(w);
          onStack.add(w);
          callStack.push([w, 0]);
        } else if (onStack.has(w)) {
          lowlink.set(v, Math.min(lowlink.get(v)!, indices.get(w)!));
        }
      } else {
        callStack.pop();
        if (callStack.length > 0) {
          const parentV = callStack[callStack.length - 1]![0];
          lowlink.set(parentV, Math.min(lowlink.get(parentV)!, lowlink.get(v)!));
        }
        if (lowlink.get(v) === indices.get(v)) {
          const comp: string[] = [];
          while (stack.length > 0) {
            const w = stack.pop()!;
            onStack.delete(w);
            comp.push(w);
            if (w === v) break;
          }
          if (comp.length >= 2 || (comp.length === 1 && (adj.get(comp[0]!) ?? []).includes(comp[0]!))) {
            sccs.push(comp);
          }
        }
      }
    }
  }

  return sccs
    .sort((a, b) => b.length - a.length || [...a].sort()[0]!.localeCompare([...b].sort()[0]!))
    .slice(0, 15)
    .map((comp) => {
      const ring = reconstructCycleRing(comp, adj);
      return {
        cycle_paths: ring,
        length: Math.max(1, ring.length - 1),
        severity: comp.length >= 3 ? "high" : "warning",
      };
    });
}

function hasTestImporter(
  path: string,
  reverseAdj: Map<string, GraphEdge[]>,
  maxHops = 2
): boolean {
  const visited = new Set([path]);
  const queue: Array<[string, number]> = [[path, 0]];
  while (queue.length > 0) {
    const [cur, depth] = queue.shift()!;
    if (depth >= maxHops) continue;
    for (const edge of reverseAdj.get(cur) ?? []) {
      if (isTestFilePath(edge.source_path)) return true;
      if (!visited.has(edge.source_path)) {
        visited.add(edge.source_path);
        queue.push([edge.source_path, depth + 1]);
      }
    }
  }
  return false;
}

export function computeClientArchHealth(graph: GraphResponse): ArchitectureHealth {
  const prodNodes = graph.nodes.filter((n) => !n.is_test && !isTestFilePath(n.path));
  const prodPaths = prodNodes.map((n) => n.path);
  const prodSet = new Set(prodPaths);
  const anyTests = graph.nodes.some((n) => n.is_test || isTestFilePath(n.path));

  const reverseAdj = new Map<string, GraphEdge[]>();
  const prodInDegree = new Map<string, number>();
  for (const p of prodPaths) prodInDegree.set(p, 0);

  for (const edge of graph.edges) {
    const rev = reverseAdj.get(edge.target_path) ?? [];
    rev.push(edge);
    reverseAdj.set(edge.target_path, rev);
    if (prodSet.has(edge.source_path) && prodSet.has(edge.target_path)) {
      prodInDegree.set(edge.target_path, (prodInDegree.get(edge.target_path) ?? 0) + 1);
    }
  }

  const cycles = detectCycles(prodPaths, graph.edges);

  const layerViolations: LayerViolation[] = [];
  const seenPairs = new Set<string>();
  const sortedEdges = [...graph.edges].sort(
    (a, b) => a.source_path.localeCompare(b.source_path) || a.target_path.localeCompare(b.target_path)
  );
  for (const edge of sortedEdges) {
    if (
      edge.source_path === edge.target_path ||
      !prodSet.has(edge.source_path) ||
      !prodSet.has(edge.target_path)
    ) {
      continue;
    }
    const pairKey = `${edge.source_path}=>${edge.target_path}`;
    if (seenPairs.has(pairKey)) continue;
    const srcLayer = classifyArchLayer(edge.source_path);
    const dstLayer = classifyArchLayer(edge.target_path);
    if (!srcLayer || !dstLayer || srcLayer === dstLayer) continue;

    let reason: string | null = null;
    if (srcLayer === "data" && (dstLayer === "service" || dstLayer === "presentation")) {
      reason = `Persistence/data module imports upward from ${dstLayer} layer (\`${edge.target_path}\`).`;
    } else if (srcLayer === "service" && dstLayer === "presentation") {
      reason = `Service/domain module imports upward from presentation/API layer (\`${edge.target_path}\`).`;
    }
    if (reason) {
      seenPairs.add(pairKey);
      layerViolations.push({
        source_path: edge.source_path,
        target_path: edge.target_path,
        source_layer: srcLayer,
        target_layer: dstLayer,
        imported_symbols: edge.imported_symbols.slice(0, 4),
        reason,
      });
    }
  }

  const rankedHotspots: Array<{ score: number; item: HotspotFinding }> = [];
  let untestedHubCount = 0;

  for (const node of prodNodes) {
    const fanIn = prodInDegree.get(node.path) ?? node.in_degree;
    const sensitive = node.path
      .toLowerCase()
      .replaceAll(".", "/")
      .split("/")
      .some((tok) => SENSITIVE_BOUNDARIES.has(tok));
    const hasTests = hasTestImporter(node.path, reverseAdj, 2);
    if (fanIn >= 3 && !hasTests) untestedHubCount += 1;

    if (fanIn < 3 && !(fanIn >= 2 && sensitive && node.loc >= 70)) continue;

    let score = fanIn * 10 + Math.min(25, Math.floor(node.loc / 12)) + (sensitive ? 15 : 0);
    if (anyTests && !hasTests) score += 12;

    const reasons = [`Imported by ${fanIn} production modules`];
    if (sensitive) reasons.push("sits on a sensitive boundary");
    if (node.loc >= 180) reasons.push(`large module (${node.loc} LOC)`);
    if (anyTests && !hasTests) reasons.push("no test coverage within 2 hops");

    rankedHotspots.push({
      score,
      item: {
        path: node.path,
        module_group: node.module_group,
        in_degree: fanIn,
        out_degree: node.out_degree,
        loc: node.loc,
        has_tests: hasTests,
        touches_sensitive_boundary: sensitive,
        reason: `${reasons.join("; ")}.`,
      },
    });
  }

  rankedHotspots.sort(
    (a, b) => b.score - a.score || a.item.path.localeCompare(b.item.path)
  );
  const hotspots = rankedHotspots.slice(0, 8).map((r) => r.item);

  const penalty =
    Math.min(45, cycles.length * 15) +
    Math.min(30, layerViolations.length * 10) +
    (anyTests ? Math.min(20, untestedHubCount * 5) : 0);
  const healthScore = Math.max(0, 100 - penalty);
  const grade =
    healthScore >= 80 ? "healthy" : healthScore >= 55 ? "watch" : "at_risk";

  return {
    health_score: healthScore,
    grade,
    cycle_count: cycles.length,
    layer_violation_count: layerViolations.length,
    hotspot_count: hotspots.length,
    untested_hub_count: anyTests ? untestedHubCount : 0,
    cycles,
    hotspots,
    layer_violations: layerViolations.slice(0, 20),
  };
}

export function findShortestCausalChain(
  selectedPath: string,
  blastRadius: BlastRadiusResult | null,
  graphEdges?: GraphEdge[]
): CausalHop[] {
  if (!blastRadius) return [];
  const directSet = new Set(blastRadius.direct);
  if (directSet.has(selectedPath)) return [];

  const outgoing = new Map<string, CausalHop[]>();
  const hardImpactedEdges = blastRadius.impacted_edges.filter(
    (e) => (e.impact_tier ?? "hard") === "hard"
  );

  if (hardImpactedEdges.length > 0) {
    for (const edge of hardImpactedEdges) {
      const list = outgoing.get(edge.source) ?? [];
      list.push({
        sourcePath: edge.source,
        targetPath: edge.target,
        importedSymbols: edge.imported_symbols,
        edgeType: edge.edge_type,
        symbolMatch: edge.symbol_match,
      });
      outgoing.set(edge.source, list);
    }
  } else if (graphEdges) {
    const impactedSet = new Set([
      ...blastRadius.direct,
      ...blastRadius.hop_1,
      ...blastRadius.hop_2,
      ...blastRadius.hop_3,
    ]);
    for (const edge of graphEdges) {
      if (impactedSet.has(edge.source_path) && impactedSet.has(edge.target_path)) {
        const list = outgoing.get(edge.source_path) ?? [];
        list.push({
          sourcePath: edge.source_path,
          targetPath: edge.target_path,
          importedSymbols: edge.imported_symbols,
          edgeType: edge.edge_type,
          symbolMatch: false,
        });
        outgoing.set(edge.source_path, list);
      }
    }
  }

  const parentHop = new Map<string, CausalHop>();
  const visited = new Set<string>([selectedPath]);
  const queue: string[] = [selectedPath];

  while (queue.length > 0) {
    const cur = queue.shift()!;
    const candidates = outgoing.get(cur) ?? [];
    // Prefer symbol-matched edges first for clearest causal trace
    const ordered = [...candidates].sort(
      (a, b) => Number(b.symbolMatch) - Number(a.symbolMatch) || a.targetPath.localeCompare(b.targetPath)
    );
    for (const hop of ordered) {
      if (visited.has(hop.targetPath)) continue;
      visited.add(hop.targetPath);
      parentHop.set(hop.targetPath, hop);
      if (directSet.has(hop.targetPath)) {
        const chain: CausalHop[] = [];
        let cursor = hop.targetPath;
        while (cursor !== selectedPath) {
          const step = parentHop.get(cursor);
          if (!step) break;
          chain.push(step);
          cursor = step.sourcePath;
        }
        return chain.reverse();
      }
      queue.push(hop.targetPath);
    }
  }

  return [];
}
