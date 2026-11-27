import { z } from "zod";

export const RiskLevelSchema = z.enum(["low", "medium", "high", "critical"]);

export const ImpactedFlowSchema = z.object({
  title: z.string(),
  severity: RiskLevelSchema,
  entry_file: z.string(),
  affected_files: z.array(z.string()),
  explanation: z.string(),
  suggested_test: z.string(),
});

export const DocDriftAlertSchema = z.object({
  doc_file: z.string(),
  section: z.string(),
  reason: z.string(),
  suggested_markdown_patch: z.string(),
});

export const BlastRadiusReportSchema = z.object({
  overall_risk: RiskLevelSchema,
  confidence: z.number().min(0).max(1),
  executive_summary: z.string(),
  breaking_change_detected: z.boolean(),
  impacted_flows: z.array(ImpactedFlowSchema),
  doc_drift_alerts: z.array(DocDriftAlertSchema),
  reviewer_checklist: z.array(z.string()),
});

export const ImpactedEdgeDetailSchema = z.object({
  source: z.string(),
  target: z.string(),
  edge_type: z.string(),
  imported_symbols: z.array(z.string()),
  symbol_match: z.boolean(),
  impact_tier: z.enum(["hard", "co_located"]).optional().default("hard"),
});

export const BlastRadiusResultSchema = z.object({
  direct: z.array(z.string()),
  hop_1: z.array(z.string()),
  hop_2: z.array(z.string()),
  hop_3: z.array(z.string()),
  score: z.number().int().min(0).max(100),
  deterministic_risk: RiskLevelSchema,
  max_in_degree: z.number().int(),
  sensitive_boundaries_touched: z.array(z.string()),
  symbol_matched_files: z.array(z.string()),
  impacted_edges: z.array(ImpactedEdgeDetailSchema),
  co_located_files: z.array(z.string()).optional().default([]),
  impacted_test_files: z.array(z.string()).optional().default([]),
  uncovered_files: z.array(z.string()).optional().default([]),
  candidate_doc_files: z.array(z.string()).optional().default([]),
  suggested_test_command: z.string().nullable().optional().default(null),
});

export const CitationValidationTelemetrySchema = z.object({
  total_cited_paths: z.number().int(),
  valid_cited_paths: z.number().int(),
  hallucination_caught: z.number().int(),
  stripped_paths: z.array(z.string()),
});

export const PRAnalysisResponseSchema = z.object({
  id: z.string(),
  repository_id: z.string(),
  snapshot_id: z.string(),
  pr_number: z.number().int().nullable(),
  pr_title: z.string(),
  changed_files: z.array(z.string()),
  blast_radius: BlastRadiusResultSchema,
  ai_report: BlastRadiusReportSchema.nullable(),
  citation_telemetry: CitationValidationTelemetrySchema.nullable(),
  model_used: z.string().nullable(),
  prompt_tokens: z.number().int(),
  completion_tokens: z.number().int(),
  estimated_cost_usd: z.number(),
  latency_ms: z.number().int(),
  created_at: z.string(),
});

export const PRAnalysisListSchema = z.array(PRAnalysisResponseSchema);

export const PRCommentResponseSchema = z.object({
  analysis_id: z.string(),
  markdown: z.string(),
  character_count: z.number().int().nonnegative(),
});

export const VerifyGeminiKeyResponseSchema = z.object({
  valid: z.boolean(),
  model: z.string(),
});

export type RiskLevel = z.infer<typeof RiskLevelSchema>;
export type ImpactedFlow = z.infer<typeof ImpactedFlowSchema>;
export type DocDriftAlert = z.infer<typeof DocDriftAlertSchema>;
export type BlastRadiusReport = z.infer<typeof BlastRadiusReportSchema>;
export type ImpactedEdgeDetail = z.infer<typeof ImpactedEdgeDetailSchema>;
export type BlastRadiusResult = z.infer<typeof BlastRadiusResultSchema>;
export type CitationValidationTelemetry = z.infer<typeof CitationValidationTelemetrySchema>;
export type PRAnalysisResponse = z.infer<typeof PRAnalysisResponseSchema>;
export type PRCommentResponse = z.infer<typeof PRCommentResponseSchema>;
export type VerifyGeminiKeyResponse = z.infer<typeof VerifyGeminiKeyResponseSchema>;
