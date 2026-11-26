"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
} from "@xyflow/react";
import { ArrowDownUp, ArrowLeftRight, Maximize2 } from "lucide-react";

import { FileNode, type DriftNodeStatus, type FileFlowNode } from "@/components/graph/file-node";
import { Button } from "@/components/ui/button";
import {
  classifyBlastTier,
  computeDagreLayout,
  getFolderColor,
  type LayoutDirection,
} from "@/lib/graph-layout";
import { type BlastRadiusResult } from "@/lib/schemas/analysis";
import { type GraphResponse, type SnapshotDiffResponse } from "@/lib/schemas/repo";

// Defined outside component render per React Flow performance guidelines.
const nodeTypes = { fileNode: FileNode } as const;

interface ArchitectureCanvasProps {
  graph: GraphResponse;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  blastRadius: BlastRadiusResult | null;
  blastOverlayActive: boolean;
  snapshotDiff?: SnapshotDiffResponse | null;
  driftOverlayActive?: boolean;
  searchQuery: string;
  focusedPaths: string[];
  focusTrigger: number;
}

function CanvasInner({
  graph,
  selectedNodeId,
  onSelectNode,
  blastRadius,
  blastOverlayActive,
  snapshotDiff = null,
  driftOverlayActive = false,
  searchQuery,
  focusedPaths,
  focusTrigger,
}: ArchitectureCanvasProps): React.JSX.Element {
  const [direction, setDirection] = useState<LayoutDirection>("LR");
  const { fitView } = useReactFlow();

  const layoutPositions = useMemo(
    () => computeDagreLayout(graph, direction),
    [graph, direction]
  );

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const focusedPathSet = useMemo(() => new Set(focusedPaths), [focusedPaths]);

  const impactedSet = useMemo(() => {
    if (!blastOverlayActive || !blastRadius) return new Set<string>();
    return new Set([
      ...blastRadius.direct,
      ...blastRadius.hop_1,
      ...blastRadius.hop_2,
      ...blastRadius.hop_3,
    ]);
  }, [blastOverlayActive, blastRadius]);

  const isDriftHighlight = driftOverlayActive && snapshotDiff !== null && !blastOverlayActive;

  const addedFileSet = useMemo(
    () => new Set(isDriftHighlight && snapshotDiff ? snapshotDiff.added_files : []),
    [isDriftHighlight, snapshotDiff]
  );

  const deltaByPath = useMemo(() => {
    const map = new Map<string, number>();
    if (isDriftHighlight && snapshotDiff) {
      for (const delta of snapshotDiff.centrality_deltas) {
        map.set(delta.path, delta.in_degree_delta);
      }
    }
    return map;
  }, [isDriftHighlight, snapshotDiff]);

  const addedEdgeKeys = useMemo(() => {
    const set = new Set<string>();
    if (isDriftHighlight && snapshotDiff) {
      for (const edge of snapshotDiff.added_edges) {
        set.add(`${edge.source_path}=>${edge.target_path}::${edge.edge_type}`);
      }
    }
    return set;
  }, [isDriftHighlight, snapshotDiff]);

  const flowNodes: FileFlowNode[] = useMemo(() => {
    return graph.nodes.map((node) => {
      const pos = layoutPositions.get(node.id) ?? { x: 0, y: 0 };
      const blastTier = classifyBlastTier(node.path, blastRadius, blastOverlayActive);
      const inDegreeDelta = deltaByPath.get(node.path) ?? 0;
      let driftStatus: DriftNodeStatus = "none";
      if (isDriftHighlight) {
        if (addedFileSet.has(node.path)) {
          driftStatus = "added";
        } else if (inDegreeDelta > 0) {
          driftStatus = "coupling_up";
        } else if (inDegreeDelta < 0) {
          driftStatus = "coupling_down";
        } else {
          driftStatus = "unchanged";
        }
      }
      const isSearchMatch =
        normalizedQuery.length > 0 &&
        (node.path.toLowerCase().includes(normalizedQuery) ||
          node.exports.some((exp) => exp.name.toLowerCase().includes(normalizedQuery)));

      return {
        id: node.id,
        type: "fileNode",
        position: pos,
        data: {
          node,
          blastTier,
          driftStatus,
          inDegreeDelta,
          isSelected: selectedNodeId === node.id,
          isSearchMatch,
          isFlowHighlighted: focusedPathSet.has(node.path),
          direction,
        },
      };
    });
  }, [
    graph.nodes,
    layoutPositions,
    blastRadius,
    blastOverlayActive,
    isDriftHighlight,
    addedFileSet,
    deltaByPath,
    normalizedQuery,
    selectedNodeId,
    focusedPathSet,
    direction,
  ]);

  const flowEdges: Edge[] = useMemo(() => {
    const baseEdges: Edge[] = graph.edges.map((edge) => {
      const edgeImpacted =
        blastOverlayActive &&
        impactedSet.has(edge.source_path) &&
        impactedSet.has(edge.target_path);

      const isDirectTarget =
        blastOverlayActive && blastRadius?.direct.includes(edge.target_path);

      const isAddedDriftEdge =
        isDriftHighlight &&
        addedEdgeKeys.has(`${edge.source_path}=>${edge.target_path}::${edge.edge_type}`);

      const strokeColor = edgeImpacted
        ? isDirectTarget
          ? "#F59E0B"
          : "#EF4444"
        : isAddedDriftEdge
          ? "#10B981"
          : "#475569";

      const opacity = blastOverlayActive
        ? edgeImpacted
          ? 0.95
          : 0.14
        : isDriftHighlight
          ? isAddedDriftEdge
            ? 0.95
            : 0.22
          : 0.65;

      return {
        id: edge.id,
        source: edge.source_node_id,
        target: edge.target_node_id,
        animated: edgeImpacted || isAddedDriftEdge,
        label:
          edge.imported_symbols.length > 0
            ? edge.imported_symbols.slice(0, 2).join(", ")
            : undefined,
        labelStyle: {
          fill: edgeImpacted || isAddedDriftEdge ? "#f8fafc" : "#94a3b8",
          fontSize: 10,
          fontFamily: "monospace",
        },
        labelBgStyle: {
          fill: "#0f172a",
          fillOpacity: 0.85,
        },
        style: {
          stroke: strokeColor,
          strokeWidth: edgeImpacted || isAddedDriftEdge ? 2.2 : 1.3,
          opacity,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 16,
          height: 16,
        },
      };
    });

    if (isDriftHighlight && snapshotDiff) {
      const nodeIdByPath = new Map(graph.nodes.map((n) => [n.path, n.id]));
      for (const removed of snapshotDiff.removed_edges) {
        const srcId = nodeIdByPath.get(removed.source_path);
        const dstId = nodeIdByPath.get(removed.target_path);
        if (!srcId || !dstId) continue;
        baseEdges.push({
          id: `removed-${removed.source_path}-${removed.target_path}-${removed.edge_type}`,
          source: srcId,
          target: dstId,
          animated: false,
          label: `removed: ${removed.imported_symbols.slice(0, 1).join("") || removed.edge_type}`,
          labelStyle: {
            fill: "#fda4af",
            fontSize: 10,
            fontFamily: "monospace",
          },
          labelBgStyle: {
            fill: "#0f172a",
            fillOpacity: 0.9,
          },
          style: {
            stroke: "#F43F5E",
            strokeWidth: 2,
            strokeDasharray: "6 4",
            opacity: 0.85,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#F43F5E",
            width: 16,
            height: 16,
          },
        });
      }
    }

    return baseEdges;
  }, [
    graph.edges,
    graph.nodes,
    blastOverlayActive,
    impactedSet,
    blastRadius,
    isDriftHighlight,
    addedEdgeKeys,
    snapshotDiff,
  ]);

  useEffect(() => {
    if (focusTrigger === 0 || focusedPaths.length === 0) return;
    const targetIds = graph.nodes
      .filter((n) => focusedPathSet.has(n.path))
      .map((n) => ({ id: n.id }));

    if (targetIds.length > 0) {
      void fitView({ nodes: targetIds, duration: 450, padding: 0.35 });
    }
  }, [focusTrigger, focusedPaths.length, focusedPathSet, graph.nodes, fitView]);

  useEffect(() => {
    void fitView({ duration: 300, padding: 0.18 });
  }, [graph.snapshot_id, direction, fitView]);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-border bg-slate-950">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
        fitView
        minZoom={0.2}
        maxZoom={1.75}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={22} size={1} color="#1e293b" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(rfNode) => {
            const data = rfNode.data as FileFlowNode["data"] | undefined;
            if (!data) return "#334155";
            if (data.blastTier === "direct") return "#F59E0B";
            if (data.blastTier === "hop_1") return "#EF4444";
            if (data.blastTier === "hop_2_plus") return "#FCA5A5";
            if (data.blastTier === "unaffected") return "#1e293b";
            if (data.driftStatus === "added") return "#10B981";
            if (data.driftStatus === "coupling_up") return "#F59E0B";
            if (data.driftStatus === "coupling_down") return "#38BDF8";
            return getFolderColor(data.node.module_group).hex;
          }}
          maskColor="rgba(2, 6, 23, 0.72)"
        />
      </ReactFlow>

      <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap items-center gap-2">
        <div className="pointer-events-auto flex items-center gap-1.5 rounded-lg border border-border bg-slate-900/90 px-2.5 py-1.5 backdrop-blur">
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() => setDirection((prev) => (prev === "LR" ? "TB" : "LR"))}
          >
            {direction === "LR" ? (
              <>
                <ArrowLeftRight className="h-3.5 w-3.5" />
                Horizontal
              </>
            ) : (
              <>
                <ArrowDownUp className="h-3.5 w-3.5" />
                Vertical
              </>
            )}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() => void fitView({ duration: 350, padding: 0.18 })}
          >
            <Maximize2 className="h-3.5 w-3.5" />
            Fit
          </Button>
        </div>

        {blastOverlayActive && blastRadius && (
          <div className="pointer-events-auto flex flex-wrap items-center gap-2.5 rounded-lg border border-border bg-slate-900/90 px-3 py-1.5 text-[11px] backdrop-blur">
            <span className="flex items-center gap-1.5 text-amber-300">
              <span className="h-2.5 w-2.5 rounded-full bg-[#F59E0B]" />
              Modified ({blastRadius.direct.length})
            </span>
            <span className="flex items-center gap-1.5 text-red-400">
              <span className="h-2.5 w-2.5 rounded-full bg-[#EF4444]" />
              1-Hop ({blastRadius.hop_1.length})
            </span>
            <span className="flex items-center gap-1.5 text-red-200">
              <span className="h-2.5 w-2.5 rounded-full bg-[#FCA5A5]" />
              2-3 Hop ({blastRadius.hop_2.length + blastRadius.hop_3.length})
            </span>
          </div>
        )}

        {isDriftHighlight && snapshotDiff && (
          <div className="pointer-events-auto flex flex-wrap items-center gap-2.5 rounded-lg border border-emerald-500/30 bg-slate-900/90 px-3 py-1.5 text-[11px] backdrop-blur">
            <span className="flex items-center gap-1.5 text-emerald-300">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              Added ({snapshotDiff.added_files.length} files / {snapshotDiff.added_edges.length} edges)
            </span>
            <span className="flex items-center gap-1.5 text-amber-300">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              Coupling Δ ({snapshotDiff.centrality_deltas.filter((d) => d.status === "changed").length})
            </span>
            <span className="flex items-center gap-1.5 text-rose-300">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
              Removed ({snapshotDiff.removed_files.length} files / {snapshotDiff.removed_edges.length} edges)
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function ArchitectureCanvas(
  props: ArchitectureCanvasProps
): React.JSX.Element {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
}
