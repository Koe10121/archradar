"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Coins,
  Cpu,
  Gauge,
  Loader2,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchTelemetrySummary } from "@/lib/api";
import { computeDemoTelemetrySummary, DEMO_PR_SCENARIOS } from "@/lib/demo-data";
import { type PRAnalysisResponse } from "@/lib/schemas/analysis";
import { type TelemetrySummaryResponse } from "@/lib/schemas/telemetry";

interface TelemetryModalProps {
  open: boolean;
  isOfflineDemo: boolean;
  offlineAnalyses?: PRAnalysisResponse[];
  onClose: () => void;
}

export function TelemetryModal({
  open,
  isOfflineDemo,
  offlineAnalyses = DEMO_PR_SCENARIOS,
  onClose,
}: TelemetryModalProps): React.JSX.Element | null {
  const [summary, setSummary] = useState<TelemetrySummaryResponse | null>(null);
  const [sourceMode, setSourceMode] = useState<"live" | "demo">("demo");
  const [loading, setLoading] = useState(false);

  const loadTelemetry = useCallback(async () => {
    setLoading(true);
    const res = await fetchTelemetrySummary();
    if (res.ok) {
      setSummary(res.data);
      setSourceMode("live");
    } else {
      setSummary(computeDemoTelemetrySummary(offlineAnalyses));
      setSourceMode("demo");
    }
    setLoading(false);
  }, [offlineAnalyses]);

  useEffect(() => {
    if (!open) return;
    void loadTelemetry();
  }, [open, loadTelemetry]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const data = summary ?? computeDemoTelemetrySummary(offlineAnalyses);
  const totalRiskCount = Math.max(
    1,
    data.risk_counts.critical +
      data.risk_counts.high +
      data.risk_counts.medium +
      data.risk_counts.low
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2.5">
            <BarChart3 className="h-5 w-5 text-amber-400" />
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold">Telemetry &amp; Cost Analytics</h2>
                <Badge variant={sourceMode === "live" ? "success" : "secondary"}>
                  {sourceMode === "live" ? "Live DB Summary" : "Offline Demo Fallback"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {isOfflineDemo && sourceMode === "demo"
                  ? "Aggregated from pre-computed Demo Mode PR scenarios"
                  : "Aggregated across persisted pr_analyses runs"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="h-8 px-2.5 text-xs"
              disabled={loading}
              onClick={() => void loadTelemetry()}
            >
              {loading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Refresh
            </Button>
            <Button size="sm" variant="outline" className="h-8 w-8 p-0" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="space-y-5 p-5 text-sm">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-lg border border-border bg-secondary/35 p-3">
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Total Analyses</span>
                <Cpu className="h-3.5 w-3.5 text-sky-400" />
              </div>
              <p className="mt-1 font-mono text-xl font-bold text-slate-100">
                {data.total_analyses}
              </p>
              <p className="text-[11px] text-slate-400">
                {data.ai_enabled_analyses} AI · {data.deterministic_only_analyses} det-only
              </p>
            </div>

            <div className="rounded-lg border border-border bg-secondary/35 p-3">
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Median / P95</span>
                <Gauge className="h-3.5 w-3.5 text-amber-400" />
              </div>
              <p className="mt-1 font-mono text-xl font-bold text-slate-100">
                {Math.round(data.median_latency_ms)} ms
              </p>
              <p className="text-[11px] text-slate-400">
                P95: {Math.round(data.p95_latency_ms)} ms
              </p>
            </div>

            <div className="rounded-lg border border-border bg-secondary/35 p-3">
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Projected / 1k PRs</span>
                <Coins className="h-3.5 w-3.5 text-emerald-400" />
              </div>
              <p className="mt-1 font-mono text-xl font-bold text-emerald-300">
                ${data.projected_cost_per_1000_prs_usd.toFixed(2)}
              </p>
              <p className="text-[11px] text-slate-400">
                Total spend: ${data.total_cost_usd.toFixed(5)}
              </p>
            </div>

            <div className="rounded-lg border border-border bg-secondary/35 p-3">
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Citation Gate</span>
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              </div>
              <p className="mt-1 font-mono text-xl font-bold text-slate-100">
                {data.valid_cited_paths}/{data.total_cited_paths}
              </p>
              <p className="text-[11px] text-amber-300">
                {data.citation_gate_intercepts} phantom intercept
                {data.citation_gate_intercepts === 1 ? "" : "s"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2.5 rounded-lg border border-border bg-slate-950/60 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Risk Distribution
              </h3>
              {(
                [
                  ["critical", data.risk_counts.critical, "bg-red-500", "text-red-300"],
                  ["high", data.risk_counts.high, "bg-orange-500", "text-orange-300"],
                  ["medium", data.risk_counts.medium, "bg-amber-400", "text-amber-300"],
                  ["low", data.risk_counts.low, "bg-emerald-500", "text-emerald-300"],
                ] as const
              ).map(([label, count, barClass, textClass]) => {
                const pct = Math.round((count / totalRiskCount) * 100);
                return (
                  <div key={label} className="space-y-1 text-xs">
                    <div className="flex items-center justify-between">
                      <span className={`font-medium uppercase ${textClass}`}>{label}</span>
                      <span className="font-mono text-slate-300">
                        {count} ({data.total_analyses > 0 ? pct : 0}%)
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className={`h-full ${barClass}`}
                        style={{ width: `${data.total_analyses > 0 ? pct : 0}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="space-y-2.5 rounded-lg border border-border bg-slate-950/60 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Token Budget Efficiency
              </h3>
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between border-b border-border/60 pb-2">
                  <span className="text-slate-400">Avg Prompt Tokens / PR</span>
                  <span className="font-mono font-semibold text-slate-100">
                    {Math.round(data.avg_prompt_tokens).toLocaleString()} tok
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-border/60 pb-2">
                  <span className="text-slate-400">Avg Completion Tokens / PR</span>
                  <span className="font-mono font-semibold text-slate-100">
                    {Math.round(data.avg_completion_tokens).toLocaleString()} tok
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-border/60 pb-2">
                  <span className="text-slate-400">Cumulative Tokens</span>
                  <span className="font-mono text-slate-200">
                    {(data.total_prompt_tokens + data.total_completion_tokens).toLocaleString()} tok
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Avg Cost / PR</span>
                  <span className="font-mono font-semibold text-emerald-300">
                    ${data.avg_cost_per_pr_usd.toFixed(6)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-2 rounded-lg border border-border bg-slate-950/60 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Model Usage Breakdown
            </h3>
            {data.models.length === 0 ? (
              <p className="text-xs text-muted-foreground">No PR analyses recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs">
                  <thead className="border-b border-border text-[11px] text-muted-foreground">
                    <tr>
                      <th className="py-1.5 pr-3">Model</th>
                      <th className="py-1.5 pr-3 text-right">Runs</th>
                      <th className="py-1.5 pr-3 text-right">Avg Prompt</th>
                      <th className="py-1.5 pr-3 text-right">Avg Output</th>
                      <th className="py-1.5 pr-3 text-right">Avg Latency</th>
                      <th className="py-1.5 text-right">Total USD</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {data.models.map((row) => (
                      <tr key={row.model} className="text-slate-200">
                        <td className="py-2 pr-3">{row.model}</td>
                        <td className="py-2 pr-3 text-right">{row.analyses_count}</td>
                        <td className="py-2 pr-3 text-right">
                          {Math.round(row.avg_prompt_tokens)}
                        </td>
                        <td className="py-2 pr-3 text-right">
                          {Math.round(row.avg_completion_tokens)}
                        </td>
                        <td className="py-2 pr-3 text-right">
                          {Math.round(row.avg_latency_ms)} ms
                        </td>
                        <td className="py-2 text-right text-emerald-300">
                          ${row.total_cost_usd.toFixed(6)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
