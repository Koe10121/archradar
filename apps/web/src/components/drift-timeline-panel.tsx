"use client";

import {
  ArrowRight,
  Eye,
  EyeOff,
  FileMinus2,
  FilePlus2,
  GitCommitHorizontal,
  History,
  Loader2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  type SnapshotDiffResponse,
  type SnapshotSummary,
} from "@/lib/schemas/repo";

interface DriftTimelinePanelProps {
  snapshots: SnapshotSummary[];
  activeSnapshotId: string;
  fromSnapshotId: string;
  toSnapshotId: string;
  snapshotDiff: SnapshotDiffResponse | null;
  driftOverlayActive: boolean;
  loading: boolean;
  error: string | null;
  isBillingDemoActive: boolean;
  onScrubSnapshot: (snapshotId: string) => void;
  onChangeRange: (fromId: string, toId: string) => void;
  onToggleDriftOverlay: () => void;
  onFocusPaths: (paths: string[]) => void;
  onSwitchToBillingDemo: () => void;
}

function formatShortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function DriftTimelinePanel({
  snapshots,
  activeSnapshotId,
  fromSnapshotId,
  toSnapshotId,
  snapshotDiff,
  driftOverlayActive,
  loading,
  error,
  isBillingDemoActive,
  onScrubSnapshot,
  onChangeRange,
  onToggleDriftOverlay,
  onFocusPaths,
  onSwitchToBillingDemo,
}: DriftTimelinePanelProps): React.JSX.Element {
  if (snapshots.length < 2) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center text-sm text-muted-foreground">
        <History className="h-8 w-8 text-emerald-400/70" />
        <p className="font-medium text-slate-200">
          Need at least 2 snapshots to compare drift
        </p>
        <p className="text-xs leading-relaxed">
          This repository currently has {snapshots.length} indexed snapshot. Re-index after
          new commits or explore the multi-snapshot{" "}
          <code className="text-slate-200">acme/saas-billing-platform</code> timeline.
        </p>
        {!isBillingDemoActive && (
          <Button
            size="sm"
            variant="secondary"
            className="mt-1 text-xs"
            onClick={onSwitchToBillingDemo}
          >
            Load Billing Demo Timeline (v1 → v2)
          </Button>
        )}
      </div>
    );
  }

  const activeIdx = Math.max(
    0,
    snapshots.findIndex((snap) => snap.id === activeSnapshotId)
  );
  const activeSnap = snapshots[activeIdx] ?? snapshots[snapshots.length - 1]!;

  return (
    <div className="flex flex-col gap-4 p-4 text-sm">
      <div className="space-y-3 border-b border-border pb-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="success">Architecture Drift</Badge>
            <span className="font-mono text-[11px] text-slate-400">
              {snapshots.length} snapshots
            </span>
          </div>
          <Button
            size="sm"
            variant={driftOverlayActive ? "default" : "outline"}
            className="h-7 px-2.5 text-xs"
            onClick={onToggleDriftOverlay}
          >
            {driftOverlayActive ? (
              <>
                <Eye className="h-3.5 w-3.5" />
                Drift Overlay
              </>
            ) : (
              <>
                <EyeOff className="h-3.5 w-3.5" />
                Overlay Off
              </>
            )}
          </Button>
        </div>

        <div className="rounded-lg border border-border bg-slate-950/70 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-slate-200">Snapshot Scrubber</span>
            <span className="font-mono text-[11px] text-emerald-300">
              v{activeIdx + 1} · {activeSnap.commit_sha.slice(0, 7)} (
              {activeSnap.file_count}f / {activeSnap.edge_count}e)
            </span>
          </div>

          <input
            aria-label="Architecture snapshot timeline slider"
            type="range"
            min={0}
            max={snapshots.length - 1}
            step={1}
            value={activeIdx}
            onChange={(e) => {
              const target = snapshots[Number(e.target.value)];
              if (target) onScrubSnapshot(target.id);
            }}
            className="mt-2.5 h-1.5 w-full cursor-pointer accent-emerald-400"
          />

          <div className="mt-2 flex flex-wrap gap-1.5">
            {snapshots.map((snap, idx) => {
              const isCurrent = snap.id === activeSnap.id;
              return (
                <button
                  key={snap.id}
                  type="button"
                  onClick={() => onScrubSnapshot(snap.id)}
                  className={`flex items-center gap-1 rounded border px-2 py-1 font-mono text-[10px] transition ${
                    isCurrent
                      ? "border-emerald-400/70 bg-emerald-500/15 text-emerald-200"
                      : "border-border bg-secondary/40 text-slate-400 hover:bg-secondary"
                  }`}
                >
                  <GitCommitHorizontal className="h-3 w-3" />
                  <span>
                    v{idx + 1} ({snap.commit_sha.slice(0, 7)})
                  </span>
                  <span className="text-slate-500">· {formatShortDate(snap.created_at)}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-1.5 text-xs">
          <select
            aria-label="Baseline snapshot"
            value={fromSnapshotId}
            onChange={(e) => onChangeRange(e.target.value, toSnapshotId)}
            className="h-8 rounded-md border border-input bg-slate-950 px-2 font-mono text-[11px] text-slate-100 outline-none focus:ring-2 focus:ring-ring"
          >
            {snapshots.map((snap, idx) => (
              <option key={snap.id} value={snap.id}>
                v{idx + 1} · {snap.commit_sha.slice(0, 7)}
              </option>
            ))}
          </select>
          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
          <select
            aria-label="Target snapshot"
            value={toSnapshotId}
            onChange={(e) => onChangeRange(fromSnapshotId, e.target.value)}
            className="h-8 rounded-md border border-input bg-slate-950 px-2 font-mono text-[11px] text-slate-100 outline-none focus:ring-2 focus:ring-ring"
          >
            {snapshots.map((snap, idx) => (
              <option key={snap.id} value={snap.id}>
                v{idx + 1} · {snap.commit_sha.slice(0, 7)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-secondary/30 p-3 text-xs text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
          Computing architectural drift diff...
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200">
          {error}
        </div>
      )}

      {snapshotDiff && !loading && (
        <>
          <div className="grid grid-cols-4 gap-1.5 text-center text-[11px]">
            <button
              type="button"
              onClick={() => onFocusPaths(snapshotDiff.added_files)}
              className="rounded border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-1.5 text-emerald-300 hover:bg-emerald-500/20"
            >
              <div className="font-mono font-bold">+{snapshotDiff.added_files.length}</div>
              <div>Files</div>
            </button>
            <div className="rounded border border-rose-500/40 bg-rose-500/10 px-1.5 py-1.5 text-rose-300">
              <div className="font-mono font-bold">-{snapshotDiff.removed_files.length}</div>
              <div>Removed</div>
            </div>
            <button
              type="button"
              onClick={() =>
                onFocusPaths(
                  snapshotDiff.added_edges.flatMap((e) => [e.source_path, e.target_path])
                )
              }
              className="rounded border border-emerald-500/30 bg-emerald-500/5 px-1.5 py-1.5 text-emerald-200 hover:bg-emerald-500/15"
            >
              <div className="font-mono font-bold">+{snapshotDiff.added_edges.length}</div>
              <div>Edges</div>
            </button>
            <div className="rounded border border-rose-500/30 bg-rose-500/5 px-1.5 py-1.5 text-rose-200">
              <div className="font-mono font-bold">-{snapshotDiff.removed_edges.length}</div>
              <div>Edges</div>
            </div>
          </div>

          {snapshotDiff.added_files.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-emerald-300">
                <FilePlus2 className="h-3.5 w-3.5" />
                Added Modules ({snapshotDiff.added_files.length})
              </h4>
              <div className="space-y-1">
                {snapshotDiff.added_files.map((path) => (
                  <button
                    key={path}
                    type="button"
                    onClick={() => onFocusPaths([path])}
                    className="flex w-full items-center justify-between rounded-md border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1.5 text-left font-mono text-[11px] text-emerald-200 hover:bg-emerald-500/20"
                  >
                    <span className="truncate">{path}</span>
                    <span className="shrink-0 text-[10px] text-emerald-300">NEW</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {snapshotDiff.removed_files.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-rose-300">
                <FileMinus2 className="h-3.5 w-3.5" />
                Removed Modules ({snapshotDiff.removed_files.length})
              </h4>
              <div className="space-y-1">
                {snapshotDiff.removed_files.map((path) => (
                  <div
                    key={path}
                    className="flex items-center justify-between rounded-md border border-rose-500/25 bg-rose-500/10 px-2.5 py-1.5 font-mono text-[11px] text-rose-200"
                  >
                    <span className="truncate line-through">{path}</span>
                    <span className="shrink-0 text-[10px] text-rose-300">REMOVED</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {snapshotDiff.centrality_deltas.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Coupling (In-Degree) Deltas
              </h4>
              <div className="space-y-1.5">
                {snapshotDiff.centrality_deltas.map((delta) => {
                  const isUp = delta.in_degree_delta > 0;
                  const isDown = delta.in_degree_delta < 0;
                  return (
                    <button
                      key={delta.path}
                      type="button"
                      onClick={() => onFocusPaths([delta.path])}
                      className="flex w-full items-center justify-between gap-2 rounded-lg border border-border bg-secondary/30 px-2.5 py-2 text-left text-xs hover:bg-secondary/60"
                    >
                      <span className="truncate font-mono text-[11px] text-slate-200">
                        {delta.path}
                      </span>
                      <span className="flex shrink-0 items-center gap-1 font-mono text-[11px]">
                        <span className="text-slate-400">
                          {delta.from_in_degree}→{delta.to_in_degree}
                        </span>
                        {isUp && (
                          <span className="inline-flex items-center gap-0.5 rounded bg-amber-500/20 px-1.5 py-0.5 text-amber-300">
                            <TrendingUp className="h-3 w-3" />+{delta.in_degree_delta}
                          </span>
                        )}
                        {isDown && (
                          <span className="inline-flex items-center gap-0.5 rounded bg-sky-500/20 px-1.5 py-0.5 text-sky-300">
                            <TrendingDown className="h-3 w-3" />
                            {delta.in_degree_delta}
                          </span>
                        )}
                        {!isUp && !isDown && (
                          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">
                            out {delta.out_degree_delta >= 0 ? `+${delta.out_degree_delta}` : delta.out_degree_delta}
                          </span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {(snapshotDiff.added_edges.length > 0 || snapshotDiff.removed_edges.length > 0) && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Edge Mutations (+{snapshotDiff.added_edges.length} / -
                {snapshotDiff.removed_edges.length})
              </h4>
              <div className="space-y-1">
                {snapshotDiff.added_edges.map((edge) => (
                  <button
                    key={`add-${edge.source_path}-${edge.target_path}`}
                    type="button"
                    onClick={() => onFocusPaths([edge.source_path, edge.target_path])}
                    className="w-full rounded border border-emerald-500/25 bg-emerald-500/5 px-2 py-1.5 text-left font-mono text-[10px] text-emerald-200 hover:bg-emerald-500/15"
                  >
                    + {edge.source_path} → {edge.target_path}
                  </button>
                ))}
                {snapshotDiff.removed_edges.map((edge) => (
                  <button
                    key={`rem-${edge.source_path}-${edge.target_path}`}
                    type="button"
                    onClick={() => onFocusPaths([edge.source_path, edge.target_path])}
                    className="w-full rounded border border-rose-500/25 bg-rose-500/5 px-2 py-1.5 text-left font-mono text-[10px] text-rose-200 hover:bg-rose-500/15"
                  >
                    - {edge.source_path} → {edge.target_path}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
