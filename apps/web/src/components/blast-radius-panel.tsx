"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckSquare,
  Copy,
  Eye,
  EyeOff,
  FileWarning,
  Filter,
  Flame,
  FlaskConical,
  History,
  Loader2,
  MessageSquareCode,
  ShieldCheck,
  Sparkles,
  Square,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchAnalysisPrComment } from "@/lib/api";
import { renderPRCommentMarkdown } from "@/lib/pr-comment";
import { type PRAnalysisResponse, type RiskLevel } from "@/lib/schemas/analysis";

interface BlastRadiusPanelProps {
  analysis: PRAnalysisResponse | null;
  analysesHistory?: PRAnalysisResponse[];
  onSelectAnalysis?: (analysis: PRAnalysisResponse) => void;
  overlayActive: boolean;
  isolateSubgraph?: boolean;
  onToggleIsolateSubgraph?: () => void;
  isOfflineDemo?: boolean;
  onToggleOverlay: () => void;
  onClearAnalysis: () => void;
  onFocusPaths: (paths: string[]) => void;
}

function riskBadgeVariant(
  risk: RiskLevel
): "success" | "warning" | "danger" | "secondary" {
  if (risk === "critical" || risk === "high") return "danger";
  if (risk === "medium") return "warning";
  return "success";
}

export function BlastRadiusPanel({
  analysis,
  analysesHistory = [],
  onSelectAnalysis,
  overlayActive,
  isolateSubgraph = false,
  onToggleIsolateSubgraph,
  isOfflineDemo = false,
  onToggleOverlay,
  onClearAnalysis,
  onFocusPaths,
}: BlastRadiusPanelProps): React.JSX.Element {
  const [copiedPatchIndex, setCopiedPatchIndex] = useState<number | null>(null);
  const [checkedItems, setCheckedItems] = useState<Record<number, boolean>>({});
  const [commentPreviewOpen, setCommentPreviewOpen] = useState(false);
  const [commentMarkdown, setCommentMarkdown] = useState<string | null>(null);
  const [commentLoading, setCommentLoading] = useState(false);
  const [commentCopied, setCommentCopied] = useState(false);
  const [testCmdCopied, setTestCmdCopied] = useState(false);

  const analysisId = analysis?.id ?? null;
  useEffect(() => {
    setCommentPreviewOpen(false);
    setCommentMarkdown(null);
    setCommentLoading(false);
    setCommentCopied(false);
    setTestCmdCopied(false);
  }, [analysisId]);

  if (!analysis) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center text-sm text-muted-foreground">
        <Flame className="mb-3 h-8 w-8 text-amber-400/70" />
        <p className="font-medium text-slate-200">No PR blast radius active</p>
        <p className="mt-1 text-xs">
          Click <strong>Demo PR #42</strong> or <strong>Analyze PR</strong> to
          highlight downstream dependents, impacted tests, and AI doc-drift notes.
        </p>
        {analysesHistory.length > 0 && onSelectAnalysis && (
          <div className="mt-4 w-full max-w-xs space-y-1.5 text-left">
            <label
              htmlFor="empty-history-select"
              className="flex items-center gap-1.5 text-[11px] font-medium text-slate-300"
            >
              <History className="h-3.5 w-3.5 text-amber-400" />
              Restore a saved PR analysis ({analysesHistory.length})
            </label>
            <select
              id="empty-history-select"
              defaultValue=""
              onChange={(e) => {
                const picked = analysesHistory.find((item) => item.id === e.target.value);
                if (picked) onSelectAnalysis(picked);
              }}
              className="h-8 w-full rounded-md border border-input bg-slate-950 px-2 text-xs text-slate-100"
            >
              <option value="" disabled>
                Select past PR run...
              </option>
              {analysesHistory.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.pr_number ? `#${item.pr_number} ` : ""}
                  {item.pr_title.slice(0, 38)} (
                  {(item.ai_report?.overall_risk ?? item.blast_radius.deterministic_risk).toUpperCase()}
                  )
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    );
  }

  const { blast_radius: br, ai_report: report, citation_telemetry: telemetry } = analysis;
  const effectiveRisk = report?.overall_risk ?? br.deterministic_risk;

  async function handleCopyPatch(index: number, patch: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(patch);
      setCopiedPatchIndex(index);
      window.setTimeout(() => setCopiedPatchIndex(null), 1800);
    } catch (err) {
      console.error("[archradar-web] Failed to copy markdown patch", err);
    }
  }

  async function handleCopyTestCmd(cmd: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(cmd);
      setTestCmdCopied(true);
      window.setTimeout(() => setTestCmdCopied(false), 1800);
    } catch (err) {
      console.error("[archradar-web] Failed to copy test command", err);
    }
  }

  async function handleToggleCommentPreview(): Promise<void> {
    if (!analysis) return;
    if (commentPreviewOpen) {
      setCommentPreviewOpen(false);
      return;
    }

    setCommentPreviewOpen(true);
    if (commentMarkdown !== null) return;

    if (isOfflineDemo) {
      setCommentMarkdown(renderPRCommentMarkdown(analysis));
      return;
    }

    setCommentLoading(true);
    const res = await fetchAnalysisPrComment(analysis.id);
    setCommentLoading(false);
    if (res.ok) {
      setCommentMarkdown(res.data.markdown);
    } else {
      setCommentMarkdown(renderPRCommentMarkdown(analysis));
    }
  }

  async function handleCopyCommentMarkdown(): Promise<void> {
    if (!analysis) return;
    const text = commentMarkdown ?? renderPRCommentMarkdown(analysis);
    try {
      await navigator.clipboard.writeText(text);
      setCommentCopied(true);
      window.setTimeout(() => setCommentCopied(false), 1800);
    } catch (err) {
      console.error("[archradar-web] Failed to copy GitHub PR comment markdown", err);
    }
  }

  const resolvedCommentMarkdown = commentMarkdown ?? renderPRCommentMarkdown(analysis);
  const hasTestOrPrecisionInfo =
    br.impacted_test_files.length > 0 ||
    br.uncovered_files.length > 0 ||
    br.co_located_files.length > 0 ||
    Boolean(br.suggested_test_command);

  return (
    <div className="flex flex-col gap-4 p-4 text-sm">
      {analysesHistory.length > 1 && onSelectAnalysis && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-slate-950/60 px-2.5 py-1.5 text-xs">
          <History className="h-3.5 w-3.5 shrink-0 text-amber-400" />
          <select
            aria-label="Saved PR analyses history"
            value={analysis.id}
            onChange={(e) => {
              const picked = analysesHistory.find((item) => item.id === e.target.value);
              if (picked) onSelectAnalysis(picked);
            }}
            className="w-full bg-transparent text-xs text-slate-100 outline-none"
          >
            {analysesHistory.map((item) => {
              const itemRisk = (
                item.ai_report?.overall_risk ?? item.blast_radius.deterministic_risk
              ).toUpperCase();
              const modeTag = item.ai_report ? "AI" : "Det";
              return (
                <option key={item.id} value={item.id} className="bg-slate-950 text-slate-100">
                  {item.pr_number ? `#${item.pr_number} ` : ""}
                  {item.pr_title.slice(0, 34)} · {itemRisk} ({modeTag})
                </option>
              );
            })}
          </select>
        </div>
      )}

      <div className="space-y-2.5 border-b border-border pb-4">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant={riskBadgeVariant(effectiveRisk)}>
                {effectiveRisk.toUpperCase()} RISK
              </Badge>
              <Badge variant="secondary">Score {br.score}/100</Badge>
              {report?.breaking_change_detected && (
                <Badge variant="danger">Breaking Change</Badge>
              )}
            </div>
            <h3 className="text-sm font-semibold text-slate-100">{analysis.pr_title}</h3>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7 w-7 shrink-0 p-0"
            onClick={onClearAnalysis}
            title="Clear active PR overlay"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            size="sm"
            variant={overlayActive ? "default" : "outline"}
            className="h-7 px-2.5 text-xs"
            onClick={onToggleOverlay}
          >
            {overlayActive ? (
              <>
                <Eye className="h-3.5 w-3.5" />
                Overlay Active
              </>
            ) : (
              <>
                <EyeOff className="h-3.5 w-3.5" />
                Overlay Off
              </>
            )}
          </Button>

          {overlayActive && onToggleIsolateSubgraph && (
            <Button
              size="sm"
              variant={isolateSubgraph ? "default" : "outline"}
              className="h-7 px-2.5 text-xs"
              onClick={onToggleIsolateSubgraph}
              title="Isolate only the impacted files on the graph"
            >
              <Filter className="h-3.5 w-3.5" />
              {isolateSubgraph ? "Subgraph Isolated" : "Isolate Subgraph"}
            </Button>
          )}

          <Button
            size="sm"
            variant={commentPreviewOpen ? "default" : "outline"}
            className="h-7 px-2.5 text-xs"
            onClick={() => void handleToggleCommentPreview()}
          >
            <MessageSquareCode className="h-3.5 w-3.5" />
            PR Comment
          </Button>

          {telemetry && (
            <span className="inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-300">
              <ShieldCheck className="h-3.5 w-3.5" />
              {telemetry.valid_cited_paths}/{telemetry.total_cited_paths} citations verified
              {telemetry.hallucination_caught > 0
                ? ` (${telemetry.hallucination_caught} stripped)`
                : ""}
            </span>
          )}
        </div>

        <div className="grid grid-cols-4 gap-1.5 text-center text-[11px]">
          <button
            type="button"
            onClick={() => onFocusPaths(br.direct)}
            className="rounded border border-[#F59E0B]/40 bg-[#F59E0B]/10 px-1.5 py-1 text-[#F59E0B] hover:bg-[#F59E0B]/20"
          >
            <div className="font-mono font-bold">{br.direct.length}</div>
            <div>Direct</div>
          </button>
          <button
            type="button"
            onClick={() => onFocusPaths(br.hop_1)}
            className="rounded border border-[#EF4444]/40 bg-[#EF4444]/10 px-1.5 py-1 text-[#EF4444] hover:bg-[#EF4444]/20"
          >
            <div className="font-mono font-bold">{br.hop_1.length}</div>
            <div>1-Hop</div>
          </button>
          <button
            type="button"
            onClick={() => onFocusPaths(br.hop_2)}
            className="rounded border border-[#FCA5A5]/40 bg-[#FCA5A5]/10 px-1.5 py-1 text-[#FCA5A5] hover:bg-[#FCA5A5]/20"
          >
            <div className="font-mono font-bold">{br.hop_2.length}</div>
            <div>2-Hop</div>
          </button>
          <button
            type="button"
            onClick={() => onFocusPaths(br.hop_3)}
            className="rounded border border-[#FCA5A5]/30 bg-[#FCA5A5]/5 px-1.5 py-1 text-red-200 hover:bg-[#FCA5A5]/15"
          >
            <div className="font-mono font-bold">{br.hop_3.length}</div>
            <div>3-Hop</div>
          </button>
        </div>

        {br.sensitive_boundaries_touched.length > 0 && (
          <div className="flex flex-wrap items-center gap-1 pt-1">
            <span className="text-[11px] text-muted-foreground">Boundaries:</span>
            {br.sensitive_boundaries_touched.map((boundary) => (
              <span
                key={boundary}
                className="rounded bg-red-500/15 px-1.5 py-0.5 font-mono text-[10px] text-red-300"
              >
                {boundary}
              </span>
            ))}
          </div>
        )}
      </div>

      {hasTestOrPrecisionInfo && (
        <div className="space-y-2 rounded-lg border border-border bg-slate-950/60 p-3 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 font-semibold text-slate-200">
              <FlaskConical className="h-3.5 w-3.5 text-emerald-400" />
              Test &amp; Symbol Precision
            </span>
            {br.co_located_files.length > 0 && (
              <span
                title={br.co_located_files.join(", ")}
                className="inline-flex items-center gap-1 rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-[10px] text-sky-300"
              >
                <Sparkles className="h-3 w-3" />
                {br.co_located_files.length} false-positive{br.co_located_files.length === 1 ? "" : "s"} pruned
              </span>
            )}
          </div>

          {br.suggested_test_command && (
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] text-emerald-300">
                  Targeted Tests ({br.impacted_test_files.length})
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 px-2 text-[10px]"
                  onClick={() => void handleCopyTestCmd(br.suggested_test_command!)}
                >
                  {testCmdCopied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-400" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      Copy Test Cmd
                    </>
                  )}
                </Button>
              </div>
              <pre className="overflow-x-auto rounded border border-border bg-slate-950 px-2 py-1.5 font-mono text-[11px] text-emerald-200">
                {br.suggested_test_command}
              </pre>
            </div>
          )}

          {br.uncovered_files.length > 0 && (
            <div className="space-y-1 pt-0.5">
              <span className="text-[11px] font-medium text-amber-300">
                Coverage Blind Spots ({br.uncovered_files.length} impacted prod file
                {br.uncovered_files.length === 1 ? "" : "s"} with 0 test importers):
              </span>
              <div className="flex flex-wrap gap-1">
                {br.uncovered_files.slice(0, 6).map((path) => (
                  <button
                    key={path}
                    type="button"
                    onClick={() => onFocusPaths([path])}
                    className="rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-200 hover:bg-amber-500/20"
                  >
                    {path}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {commentPreviewOpen && (
        <div className="space-y-2 rounded-lg border border-sky-500/30 bg-slate-950/70 p-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sky-300">GitHub PR Comment Preview</span>
              <Badge variant="secondary">{resolvedCommentMarkdown.length} chars</Badge>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="h-6 px-2 text-[11px]"
              onClick={() => void handleCopyCommentMarkdown()}
            >
              {commentCopied ? (
                <>
                  <Check className="h-3 w-3 text-emerald-400" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  Copy GitHub Markdown
                </>
              )}
            </Button>
          </div>
          {commentLoading ? (
            <div className="flex items-center gap-2 py-3 text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
              Rendering PR comment Markdown...
            </div>
          ) : (
            <pre className="max-h-72 overflow-auto rounded border border-border bg-slate-950 p-2.5 font-mono text-[11px] leading-relaxed text-slate-200 whitespace-pre-wrap">
              {resolvedCommentMarkdown}
            </pre>
          )}
        </div>
      )}

      {report ? (
        <>
          <div className="rounded-lg border border-border bg-secondary/35 p-3 text-xs leading-relaxed text-slate-200">
            {report.executive_summary}
          </div>

          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Impacted Flows ({report.impacted_flows.length}) — click to focus
            </h4>
            {report.impacted_flows.map((flow) => (
              <button
                key={flow.title}
                type="button"
                onClick={() => onFocusPaths([flow.entry_file, ...flow.affected_files])}
                className="w-full rounded-lg border border-border bg-secondary/30 p-3 text-left transition hover:border-amber-400/60 hover:bg-secondary/60"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-100">{flow.title}</span>
                  <Badge variant={riskBadgeVariant(flow.severity)}>{flow.severity}</Badge>
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-300">
                  {flow.explanation}
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {[flow.entry_file, ...flow.affected_files].map((file) => (
                    <span
                      key={file}
                      className="rounded bg-slate-950/70 px-1.5 py-0.5 font-mono text-[10px] text-amber-300"
                    >
                      {file}
                    </span>
                  ))}
                </div>
                <p className="mt-2 border-t border-border/60 pt-1.5 text-[11px] text-emerald-300/90">
                  Test: {flow.suggested_test}
                </p>
              </button>
            ))}
          </div>

          {report.doc_drift_alerts.length > 0 && (
            <div className="space-y-2">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-300">
                <FileWarning className="h-3.5 w-3.5" />
                Doc-Drift Alerts ({report.doc_drift_alerts.length})
              </h4>
              {report.doc_drift_alerts.map((alert, idx) => (
                <div
                  key={`${alert.doc_file}-${idx}`}
                  className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono font-semibold text-amber-200">
                      {alert.doc_file} · {alert.section}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 px-2 text-[11px]"
                      onClick={() => void handleCopyPatch(idx, alert.suggested_markdown_patch)}
                    >
                      {copiedPatchIndex === idx ? (
                        <>
                          <Check className="h-3 w-3 text-emerald-400" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3" />
                          Copy Patch
                        </>
                      )}
                    </Button>
                  </div>
                  <p className="mt-1 text-slate-300">{alert.reason}</p>
                  <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2 font-mono text-[11px] text-slate-200">
                    {alert.suggested_markdown_patch}
                  </pre>
                </div>
              ))}
            </div>
          )}

          {report.reviewer_checklist.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Reviewer Checklist
              </h4>
              <div className="space-y-1.5">
                {report.reviewer_checklist.map((item, idx) => {
                  const checked = Boolean(checkedItems[idx]);
                  return (
                    <button
                      key={`${item}-${idx}`}
                      type="button"
                      onClick={() =>
                        setCheckedItems((prev) => ({ ...prev, [idx]: !prev[idx] }))
                      }
                      className="flex w-full items-start gap-2 rounded-lg border border-border bg-secondary/25 px-2.5 py-2 text-left text-xs hover:bg-secondary/50"
                    >
                      {checked ? (
                        <CheckSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                      ) : (
                        <Square className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
                      )}
                      <span className={checked ? "text-slate-400 line-through" : "text-slate-200"}>
                        {item}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 font-mono text-[11px] text-muted-foreground">
            <span>{analysis.model_used ?? "deterministic"}</span>
            <span>
              {analysis.prompt_tokens}+{analysis.completion_tokens} tok · $
              {analysis.estimated_cost_usd.toFixed(5)} · {analysis.latency_ms}ms
            </span>
          </div>
        </>
      ) : (
        <div className="space-y-2 rounded-lg border border-border bg-secondary/30 p-3 text-xs text-slate-300">
          <p className="flex items-center gap-1.5 font-medium text-slate-100">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            Deterministic Blast-Radius Only
          </p>
          <p className="text-muted-foreground">
            AI risk narrative was skipped for this run. Click <strong>Free AI Key</strong> to add
            your session-only Gemini key for grounded flow narratives and Markdown doc-drift
            patches.
          </p>
          {br.candidate_doc_files.length > 0 && (
            <div className="border-t border-border/60 pt-2">
              <span className="text-[11px] font-medium text-amber-300">
                Indexed docs referencing touched symbols/routes:{" "}
              </span>
              <span className="font-mono text-[11px] text-slate-200">
                {br.candidate_doc_files.join(", ")}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
