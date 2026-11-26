import dagre from "@dagrejs/dagre";

import { type BlastRadiusResult } from "@/lib/schemas/analysis";
import { type GraphResponse } from "@/lib/schemas/repo";

export type LayoutDirection = "LR" | "TB";
export type BlastTier = "none" | "direct" | "hop_1" | "hop_2_plus" | "unaffected";

export const NODE_WIDTH = 260;
export const NODE_HEIGHT = 104;

const FOLDER_PALETTE = [
  { bar: "bg-sky-500", badge: "border-sky-500/30 bg-sky-500/10 text-sky-300", hex: "#0EA5E9" },
  { bar: "bg-violet-500", badge: "border-violet-500/30 bg-violet-500/10 text-violet-300", hex: "#8B5CF6" },
  { bar: "bg-emerald-500", badge: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", hex: "#10B981" },
  { bar: "bg-amber-500", badge: "border-amber-500/30 bg-amber-500/10 text-amber-300", hex: "#F59E0B" },
  { bar: "bg-cyan-500", badge: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300", hex: "#06B6D4" },
  { bar: "bg-pink-500", badge: "border-pink-500/30 bg-pink-500/10 text-pink-300", hex: "#EC4899" },
  { bar: "bg-indigo-500", badge: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300", hex: "#6366F1" },
] as const;

export function getFolderColor(moduleGroup: string): (typeof FOLDER_PALETTE)[number] {
  let hash = 0;
  for (let i = 0; i < moduleGroup.length; i += 1) {
    hash = (hash * 31 + moduleGroup.charCodeAt(i)) >>> 0;
  }
  const index = hash % FOLDER_PALETTE.length;
  return FOLDER_PALETTE[index] ?? FOLDER_PALETTE[0];
}

export function classifyBlastTier(
  path: string,
  blastRadius: BlastRadiusResult | null,
  overlayActive: boolean
): BlastTier {
  if (!overlayActive || !blastRadius) {
    return "none";
  }
  if (blastRadius.direct.includes(path)) {
    return "direct";
  }
  if (blastRadius.hop_1.includes(path)) {
    return "hop_1";
  }
  if (blastRadius.hop_2.includes(path) || blastRadius.hop_3.includes(path)) {
    return "hop_2_plus";
  }
  return "unaffected";
}

export function computeDagreLayout(
  graph: GraphResponse,
  direction: LayoutDirection = "LR"
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: direction,
    nodesep: direction === "LR" ? 36 : 48,
    ranksep: direction === "LR" ? 96 : 72,
    marginx: 32,
    marginy: 32,
  });

  const sortedNodes = [...graph.nodes].sort((a, b) => a.path.localeCompare(b.path));
  for (const node of sortedNodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  const sortedEdges = [...graph.edges].sort((a, b) =>
    `${a.source_path}->${a.target_path}`.localeCompare(`${b.source_path}->${b.target_path}`)
  );
  for (const edge of sortedEdges) {
    if (edge.source_node_id !== edge.target_node_id) {
      g.setEdge(edge.source_node_id, edge.target_node_id);
    }
  }

  dagre.layout(g);

  const positions = new Map<string, { x: number; y: number }>();
  for (const node of sortedNodes) {
    const pos = g.node(node.id) as { x: number; y: number } | undefined;
    positions.set(node.id, {
      x: (pos?.x ?? 0) - NODE_WIDTH / 2,
      y: (pos?.y ?? 0) - NODE_HEIGHT / 2,
    });
  }
  return positions;
}
