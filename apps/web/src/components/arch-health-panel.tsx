"use client";

import {
  AlertOctagon,
  CheckCircle2,
  Flame,
  GitCompareArrows,
  RefreshCcw,
  ShieldAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { type ArchitectureHealth } from "@/lib/schemas/repo";

interface ArchHealthPanelProps {
  health: ArchitectureHealth;
  onFocusCycle: (cyclePaths: string[]) => void;
  onFocusPaths: (paths: string[]) => void;
  onInspectPath: (path: string) => void;
}

export function ArchHealthPanel({
  health,
  onFocusCycle,
  onFocusPaths,
  onInspectPath,
}: ArchHealthPanelProps): React.JSX.Element {
  const gradeVariant =
    health.grade === "healthy"
      ? "success"
      : health.grade === "watch"
        ? "warning"
        : "danger";

  return (
    <div className="flex flex-col gap-4 p-4 text-sm">
      <div className="space-y-3 border-b border-border pb-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant={gradeVariant}>{health.grade.replace("_", " ").toUpperCase()}</Badge>
              <span className="font-mono text-xs font-semibold text-slate-200">
                Score {health.health_score}/100
              </span>
            </div>
            <h3 className="mt-1 text-sm font-semibold text-slate-100">
              Deterministic Architecture Health
            </h3>
          </div>
          <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
            0 AI tokens
          </span>
        </div>

        <p className="text-xs text-muted-foreground">
          Computed directly from the Tree-sitter AST dependency graph: circular dependency SCCs,
          layer inversions, and high-fan-in hotspots.
        </p>

        <div className="grid grid-cols-3 gap-1.5 text-center text-[11px]">
          <div className="rounded border border-violet-500/30 bg-violet-500/10 px-2 py-1.5 text-violet-200">
            <div className="font-mono text-sm font-bold">{health.cycle_count}</div>
            <div>Cycles</div>
          </div>
          <div className="rounded border border-rose-500/30 bg-rose-500/10 px-2 py-1.5 text-rose-200">
            <div className="font-mono text-sm font-bold">{health.layer_violation_count}</div>
            <div>Layer Smells</div>
          </div>
          <div className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-amber-200">
            <div className="font-mono text-sm font-bold">{health.hotspot_count}</div>
            <div>Hotspots</div>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-violet-300">
          <RefreshCcw className="h-3.5 w-3.5" />
          Circular Dependencies ({health.cycles.length})
        </h4>
        {health.cycles.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-500/25 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-200">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            Zero circular import loops detected across production modules.
          </div>
        ) : (
          <div className="space-y-2">
            {health.cycles.map((cycle, idx) => (
              <button
                key={`cycle-${idx}`}
                type="button"
                onClick={() => onFocusCycle(cycle.cycle_paths)}
                className="w-full rounded-lg border border-violet-500/35 bg-violet-500/10 p-2.5 text-left text-xs transition hover:border-violet-400 hover:bg-violet-500/20"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-violet-200">
                    {cycle.length}-File Cycle Loop
                  </span>
                  <Badge variant={cycle.severity === "high" ? "danger" : "warning"}>
                    {cycle.severity}
                  </Badge>
                </div>
                <p className="mt-1.5 break-all font-mono text-[11px] leading-relaxed text-slate-200">
                  {cycle.cycle_paths.join(" → ")}
                </p>
                <p className="mt-1 text-[10px] text-violet-300">
                  Click to highlight &amp; isolate loop on canvas
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-rose-300">
          <GitCompareArrows className="h-3.5 w-3.5" />
          Layer Violations ({health.layer_violations.length})
        </h4>
        {health.layer_violations.length === 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-emerald-500/25 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-200">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            Clean downward layering (presentation → service → data).
          </div>
        ) : (
          <div className="space-y-2">
            {health.layer_violations.map((v, idx) => (
              <button
                key={`${v.source_path}-${v.target_path}-${idx}`}
                type="button"
                onClick={() => onFocusPaths([v.source_path, v.target_path])}
                className="w-full rounded-lg border border-rose-500/35 bg-rose-500/10 p-2.5 text-left text-xs transition hover:border-rose-400 hover:bg-rose-500/20"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] font-semibold text-rose-200">
                    {v.source_layer} → {v.target_layer}
                  </span>
                  <AlertOctagon className="h-3.5 w-3.5 text-rose-400" />
                </div>
                <p className="mt-1 break-all font-mono text-[11px] text-slate-100">
                  {v.source_path} → {v.target_path}
                </p>
                <p className="mt-1 text-[11px] text-slate-300">{v.reason}</p>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-300">
          <Flame className="h-3.5 w-3.5" />
          Coupling Hotspots &amp; Bus-Factor Hubs ({health.hotspots.length})
        </h4>
        {health.hotspots.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No high-coupling hub bottlenecks above threshold.
          </p>
        ) : (
          <div className="space-y-2">
            {health.hotspots.map((spot) => (
              <button
                key={spot.path}
                type="button"
                onClick={() => onInspectPath(spot.path)}
                className="w-full rounded-lg border border-border bg-secondary/30 p-2.5 text-left text-xs transition hover:border-amber-400/60 hover:bg-secondary/60"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="break-all font-mono font-semibold text-slate-100">
                    {spot.path}
                  </span>
                  <Badge variant={spot.touches_sensitive_boundary ? "warning" : "secondary"}>
                    in:{spot.in_degree}
                  </Badge>
                </div>
                <p className="mt-1 text-[11px] text-slate-300">{spot.reason}</p>
                {spot.touches_sensitive_boundary && (
                  <span className="mt-1.5 inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300">
                    <ShieldAlert className="h-3 w-3" />
                    Sensitive boundary hub
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
