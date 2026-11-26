"use client";

import { ArrowDownLeft, ArrowUpRight, Code2, FileCode2, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { classifyBlastTier } from "@/lib/graph-layout";
import { type PRAnalysisResponse } from "@/lib/schemas/analysis";
import { type GraphNode, type GraphResponse } from "@/lib/schemas/repo";

interface NodeInspectorDrawerProps {
  graph: GraphResponse;
  selectedNode: GraphNode | null;
  activeAnalysis: PRAnalysisResponse | null;
  blastOverlayActive: boolean;
  onNavigateToNode: (nodeId: string) => void;
}

export function NodeInspectorDrawer({
  graph,
  selectedNode,
  activeAnalysis,
  blastOverlayActive,
  onNavigateToNode,
}: NodeInspectorDrawerProps): React.JSX.Element {
  if (!selectedNode) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center text-sm text-muted-foreground">
        <FileCode2 className="mb-3 h-8 w-8 text-slate-500" />
        <p className="font-medium text-slate-200">No file selected</p>
        <p className="mt-1 text-xs">
          Click any file node in the architecture graph to inspect exported symbols,
          upstream imports, and downstream dependents.
        </p>
      </div>
    );
  }

  const upstreamEdges = graph.edges.filter(
    (edge) => edge.source_node_id === selectedNode.id
  );
  const downstreamEdges = graph.edges.filter(
    (edge) => edge.target_node_id === selectedNode.id
  );

  const blastTier = classifyBlastTier(
    selectedNode.path,
    activeAnalysis?.blast_radius ?? null,
    blastOverlayActive
  );

  const relatedFlows =
    activeAnalysis?.ai_report?.impacted_flows.filter(
      (flow) =>
        flow.entry_file === selectedNode.path ||
        flow.affected_files.includes(selectedNode.path)
    ) ?? [];

  return (
    <div className="flex flex-col gap-5 p-4 text-sm">
      <div className="space-y-2 border-b border-border pb-4">
        <div className="flex items-start justify-between gap-2">
          <p className="break-all font-mono text-xs font-semibold text-slate-100">
            {selectedNode.path}
          </p>
          <Badge variant="secondary">{selectedNode.language}</Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Module: {selectedNode.module_group}</span>
          <span>·</span>
          <span>{selectedNode.loc} LOC</span>
          <span>·</span>
          <span>in:{selectedNode.in_degree}</span>
          <span>out:{selectedNode.out_degree}</span>
        </div>

        {blastTier !== "none" && (
          <div className="pt-1">
            {blastTier === "direct" && (
              <Badge variant="warning">Directly Modified in PR</Badge>
            )}
            {blastTier === "hop_1" && (
              <Badge variant="danger">1-Hop Downstream Dependent</Badge>
            )}
            {blastTier === "hop_2_plus" && (
              <Badge variant="danger">2-3 Hop Transitive Dependent</Badge>
            )}
            {blastTier === "unaffected" && (
              <Badge variant="secondary">Unaffected by PR</Badge>
            )}
          </div>
        )}
      </div>

      {relatedFlows.length > 0 && (
        <div className="space-y-2">
          <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-300">
            <ShieldAlert className="h-3.5 w-3.5" />
            AI Risk Notes
          </h4>
          <div className="space-y-2">
            {relatedFlows.map((flow) => (
              <div
                key={flow.title}
                className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-amber-200">{flow.title}</span>
                  <Badge variant="warning">{flow.severity}</Badge>
                </div>
                <p className="mt-1 text-slate-300">{flow.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Code2 className="h-3.5 w-3.5" />
          Exported Symbols ({selectedNode.exports.length})
        </h4>
        {selectedNode.exports.length === 0 ? (
          <p className="text-xs text-muted-foreground">No exported symbols detected.</p>
        ) : (
          <div className="space-y-1.5">
            {selectedNode.exports.map((exp, idx) => (
              <div
                key={`${exp.name}-${idx}`}
                className="rounded-lg border border-border bg-secondary/40 p-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-slate-100">
                    {exp.name}
                  </span>
                  <Badge variant="secondary">{exp.kind}</Badge>
                </div>
                <p className="mt-1 overflow-x-auto font-mono text-[11px] text-slate-400">
                  {exp.signature}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <ArrowUpRight className="h-3.5 w-3.5 text-sky-400" />
          Imports ({upstreamEdges.length})
        </h4>
        {upstreamEdges.length === 0 ? (
          <p className="text-xs text-muted-foreground">No internal imports.</p>
        ) : (
          <div className="space-y-1.5">
            {upstreamEdges.map((edge) => (
              <button
                key={edge.id}
                type="button"
                onClick={() => onNavigateToNode(edge.target_node_id)}
                className="flex w-full flex-col items-start rounded-lg border border-border bg-secondary/30 px-2.5 py-2 text-left transition hover:border-sky-500/50 hover:bg-secondary/60"
              >
                <span className="font-mono text-xs text-sky-300">{edge.target_path}</span>
                {edge.imported_symbols.length > 0 && (
                  <span className="mt-0.5 font-mono text-[11px] text-slate-400">
                    {edge.imported_symbols.join(", ")}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <ArrowDownLeft className="h-3.5 w-3.5 text-red-400" />
          Imported By ({downstreamEdges.length})
        </h4>
        {downstreamEdges.length === 0 ? (
          <p className="text-xs text-muted-foreground">No downstream dependents.</p>
        ) : (
          <div className="space-y-1.5">
            {downstreamEdges.map((edge) => (
              <button
                key={edge.id}
                type="button"
                onClick={() => onNavigateToNode(edge.source_node_id)}
                className="flex w-full flex-col items-start rounded-lg border border-border bg-secondary/30 px-2.5 py-2 text-left transition hover:border-red-500/50 hover:bg-secondary/60"
              >
                <span className="font-mono text-xs text-red-300">{edge.source_path}</span>
                {edge.imported_symbols.length > 0 && (
                  <span className="mt-0.5 font-mono text-[11px] text-slate-400">
                    {edge.imported_symbols.join(", ")}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
