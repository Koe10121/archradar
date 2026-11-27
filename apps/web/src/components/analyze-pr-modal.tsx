"use client";

import { useEffect, useMemo, useState } from "react";
import {
  GitPullRequest,
  KeyRound,
  Loader2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { analyzePullRequest, fetchRepositoryGitHubPRs } from "@/lib/api";
import { isTestFilePath } from "@/lib/arch-health";
import {
  SAMPLE_DIFFS_BY_REPO_ID,
  SAMPLE_UNIFIED_DIFF,
} from "@/lib/demo-data";
import { maskApiKey } from "@/lib/gemini-key";
import { buildSampleDiffForGraph } from "@/lib/sample-diff";
import { type BlastRadiusResult, type PRAnalysisResponse } from "@/lib/schemas/analysis";
import { type GitHubPRSummary, type GraphResponse } from "@/lib/schemas/repo";

interface AnalyzePRModalProps {
  open: boolean;
  repoId: string;
  repoLabel: string;
  isOfflineDemo: boolean;
  isDemoRepo?: boolean;
  demoScenarios: PRAnalysisResponse[];
  graph: GraphResponse;
  geminiApiKey: string;
  onOpenGeminiKeyModal: () => void;
  onClose: () => void;
  onAnalyzed: (analysis: PRAnalysisResponse) => void;
}

function computeDemoBlastRadius(
  graph: GraphResponse,
  rawDiff: string,
  prTitle: string
): PRAnalysisResponse {
  const diffLines = rawDiff.split("\n");
  const touched = new Set<string>();
  for (const line of diffLines) {
    if (line.startsWith("+++ b/") || line.startsWith("--- a/")) {
      const candidate = line.slice(6).trim();
      if (candidate && candidate !== "/dev/null") {
        touched.add(candidate);
      }
    }
  }

  const nodePaths = new Set(graph.nodes.map((n) => n.path));
  const direct = [...touched].filter((p) => nodePaths.has(p));

  const reverseAdj = new Map<string, string[]>();
  for (const edge of graph.edges) {
    const list = reverseAdj.get(edge.target_path) ?? [];
    list.push(edge.source_path);
    reverseAdj.set(edge.target_path, list);
  }

  const seen = new Set(direct);
  const hop1: string[] = [];
  const hop2: string[] = [];
  const hop3: string[] = [];
  const impactedTests: string[] = [];
  const queue: Array<[string, number]> = direct.map((p) => [p, 0]);

  while (queue.length > 0) {
    const next = queue.shift();
    if (!next) break;
    const [current, depth] = next;
    if (depth >= 3) continue;
    for (const dep of reverseAdj.get(current) ?? []) {
      if (seen.has(dep)) continue;
      if (isTestFilePath(dep)) {
        if (!impactedTests.includes(dep)) impactedTests.push(dep);
        continue;
      }
      seen.add(dep);
      if (depth + 1 === 1) hop1.push(dep);
      else if (depth + 1 === 2) hop2.push(dep);
      else hop3.push(dep);
      queue.push([dep, depth + 1]);
    }
  }

  const impactedCount = direct.length + hop1.length + hop2.length + hop3.length;
  const score =
    impactedCount === 0
      ? 0
      : Math.min(100, Math.round((impactedCount / Math.max(graph.nodes.length, 1)) * 75) + hop1.length * 6);

  const risk: BlastRadiusResult["deterministic_risk"] =
    score >= 75 ? "critical" : score >= 50 ? "high" : score >= 25 ? "medium" : "low";

  return {
    id: `demo-${Date.now()}`,
    repository_id: graph.repository_id,
    snapshot_id: graph.snapshot_id,
    pr_number: null,
    pr_title: prTitle || "Simulated Unified Diff",
    changed_files: direct,
    blast_radius: {
      direct,
      hop_1: hop1,
      hop_2: hop2,
      hop_3: hop3,
      score,
      deterministic_risk: risk,
      max_in_degree: 0,
      sensitive_boundaries_touched: [],
      symbol_matched_files: [],
      impacted_edges: [],
      co_located_files: [],
      impacted_test_files: impactedTests,
      uncovered_files: [],
      candidate_doc_files: [],
      suggested_test_command: null,
    },
    ai_report: null,
    citation_telemetry: null,
    model_used: "client-demo-bfs",
    prompt_tokens: 0,
    completion_tokens: 0,
    estimated_cost_usd: 0,
    latency_ms: 4,
    created_at: new Date().toISOString(),
  };
}

export function AnalyzePRModal({
  open,
  repoId,
  repoLabel,
  isOfflineDemo,
  isDemoRepo = false,
  demoScenarios,
  graph,
  geminiApiKey,
  onOpenGeminiKeyModal,
  onClose,
  onAnalyzed,
}: AnalyzePRModalProps): React.JSX.Element | null {
  const autoSample = useMemo(() => {
    const presetDiff = SAMPLE_DIFFS_BY_REPO_ID[repoId];
    if (presetDiff) {
      return {
        title: "Enforce strict audience claim in verifyToken",
        diff: presetDiff,
      };
    }
    const generated = buildSampleDiffForGraph(graph);
    return {
      title: generated.title,
      diff: generated.diff || SAMPLE_UNIFIED_DIFF,
    };
  }, [repoId, graph]);

  const [mode, setMode] = useState<"diff" | "url">("diff");
  const [prTitle, setPrTitle] = useState(autoSample.title);
  const [prUrl, setPrUrl] = useState("");
  const [rawDiff, setRawDiff] = useState(autoSample.diff);
  const [runAi, setRunAi] = useState(Boolean(geminiApiKey));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentPRs, setRecentPRs] = useState<GitHubPRSummary[]>([]);
  const [loadingPRs, setLoadingPRs] = useState(false);

  useEffect(() => {
    setRawDiff(autoSample.diff);
    setPrTitle(autoSample.title);
  }, [autoSample]);

  useEffect(() => {
    if (open && geminiApiKey) {
      setRunAi(true);
    }
  }, [open, geminiApiKey]);

  useEffect(() => {
    if (!open || isOfflineDemo || isDemoRepo) {
      setRecentPRs([]);
      setLoadingPRs(false);
      return;
    }
    let cancelled = false;
    setLoadingPRs(true);
    void fetchRepositoryGitHubPRs(repoId).then((res) => {
      if (cancelled) return;
      setLoadingPRs(false);
      if (res.ok) {
        setRecentPRs(res.data);
      } else {
        setRecentPRs([]);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [open, repoId, isOfflineDemo, isDemoRepo]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setError(null);

    if (isOfflineDemo && mode === "diff") {
      if (rawDiff.trim() === autoSample.diff.trim() && demoScenarios.length > 0) {
        const primary = demoScenarios[0];
        if (primary) {
          onAnalyzed(primary);
          onClose();
          return;
        }
      }
      onAnalyzed(computeDemoBlastRadius(graph, rawDiff, prTitle));
      onClose();
      return;
    }

    setIsSubmitting(true);
    const result = await analyzePullRequest(
      repoId,
      {
        pr_title: prTitle.trim() || "Ad-hoc PR Analysis",
        raw_diff: mode === "diff" ? rawDiff : undefined,
        pr_url: mode === "url" ? prUrl.trim() : undefined,
        run_ai: runAi,
      },
      { geminiApiKey }
    );
    setIsSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    onAnalyzed(result.data);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-2">
            <GitPullRequest className="h-5 w-5 text-amber-400" />
            <div>
              <h2 className="text-base font-semibold">Analyze Pull Request Blast Radius</h2>
              <p className="text-xs text-muted-foreground">Target repo: {repoLabel}</p>
            </div>
          </div>
          <Button size="sm" variant="outline" className="h-8 w-8 p-0" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 p-5 text-sm">
          {demoScenarios.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs">
              <span className="text-amber-200">
                {isOfflineDemo
                  ? "Offline Demo Mode active: launch a pre-computed scenario or test any unified diff."
                  : "Pre-computed demo scenarios available, or run a live diff/PR analysis below."}
              </span>
              <div className="flex gap-1.5">
                {demoScenarios.map((scenario) => (
                  <Button
                    key={scenario.id}
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-[11px]"
                    onClick={() => {
                      onAnalyzed(scenario);
                      onClose();
                    }}
                  >
                    <Sparkles className="h-3 w-3 text-amber-400" />
                    PR #{scenario.pr_number}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {!isOfflineDemo && !isDemoRepo && (loadingPRs || recentPRs.length > 0) && (
            <div className="space-y-2 rounded-lg border border-sky-500/30 bg-sky-500/10 p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sky-200">
                  1-Click Recent GitHub Pull Requests ({repoLabel})
                </span>
                {loadingPRs && <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-300" />}
              </div>
              {recentPRs.length > 0 && (
                <div className="flex max-h-28 flex-wrap gap-1.5 overflow-y-auto">
                  {recentPRs.map((pr) => (
                    <button
                      key={pr.number}
                      type="button"
                      onClick={() => {
                        setMode("url");
                        setPrUrl(pr.html_url);
                        setPrTitle(`#${pr.number} ${pr.title}`);
                      }}
                      className={`inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-left text-[11px] transition ${
                        mode === "url" && prUrl === pr.html_url
                          ? "border-sky-400 bg-sky-500/25 text-white"
                          : "border-border bg-slate-950/80 text-slate-200 hover:border-sky-400/60"
                      }`}
                    >
                      <Badge
                        variant={
                          pr.state === "open"
                            ? "success"
                            : pr.state === "merged"
                              ? "secondary"
                              : "warning"
                        }
                      >
                        #{pr.number} {pr.state}
                      </Badge>
                      <span className="truncate">{pr.title}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant={mode === "diff" ? "default" : "outline"}
              onClick={() => setMode("diff")}
            >
              Paste Unified Diff
            </Button>
            <Button
              type="button"
              size="sm"
              variant={mode === "url" ? "default" : "outline"}
              disabled={isOfflineDemo}
              onClick={() => setMode("url")}
            >
              GitHub PR URL {isOfflineDemo ? "(connect API or index a repo first)" : ""}
            </Button>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300" htmlFor="pr-title-input">
              PR Title
            </label>
            <input
              id="pr-title-input"
              value={prTitle}
              onChange={(e) => setPrTitle(e.target.value)}
              className="w-full rounded-md border border-input bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-ring"
              placeholder="e.g. Enforce strict token validation"
            />
          </div>

          {mode === "diff" ? (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-300" htmlFor="raw-diff-input">
                  Unified Git Diff
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setRawDiff(autoSample.diff);
                    setPrTitle(autoSample.title);
                  }}
                  className="text-xs text-amber-400 hover:underline"
                >
                  Load sample diff for this repo
                </button>
              </div>
              <textarea
                id="raw-diff-input"
                rows={8}
                value={rawDiff}
                onChange={(e) => setRawDiff(e.target.value)}
                className="w-full rounded-md border border-input bg-slate-950 p-3 font-mono text-xs text-slate-100 outline-none focus:ring-2 focus:ring-ring"
                placeholder="diff --git a/src/... b/src/..."
              />
            </div>
          ) : (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300" htmlFor="pr-url-input">
                GitHub Pull Request URL
              </label>
              <input
                id="pr-url-input"
                value={prUrl}
                onChange={(e) => setPrUrl(e.target.value)}
                className="w-full rounded-md border border-input bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-ring"
                placeholder="https://github.com/owner/repo/pull/42"
              />
            </div>
          )}

          {!isOfflineDemo && (
            <div className="space-y-2 rounded-lg border border-border bg-slate-950/60 p-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 font-medium text-slate-200">
                  <input
                    type="checkbox"
                    checked={runAi}
                    onChange={(e) => setRunAi(e.target.checked)}
                    className="h-4 w-4 rounded border-border bg-slate-950 accent-amber-500"
                  />
                  Include Grounded Gemini AI Risk &amp; Auto Doc-Drift Report
                </label>

                {geminiApiKey ? (
                  <button
                    type="button"
                    onClick={onOpenGeminiKeyModal}
                    className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[11px] text-emerald-300 hover:bg-emerald-500/20"
                  >
                    <ShieldCheck className="h-3 w-3" />
                    Session key ready ({maskApiKey(geminiApiKey)})
                  </button>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2.5 text-[11px]"
                    onClick={onOpenGeminiKeyModal}
                  >
                    <KeyRound className="h-3 w-3 text-emerald-400" />
                    Add Free Gemini Key
                  </Button>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {runAi
                  ? geminiApiKey
                    ? "Uses your session-only Gemini key over HTTPS + auto-retrieves indexed repo docs."
                    : "Uses the server's GEMINI_API_KEY if configured, or add your own free session key above."
                  : "Deterministic Tree-sitter AST + Symbol-Aware Reverse-BFS runs free with zero AI key."}
              </p>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {isSubmitting ? "Analyzing..." : "Run Blast-Radius Radar"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
