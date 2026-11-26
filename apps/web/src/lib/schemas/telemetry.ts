import { z } from "zod";

export const RiskLevelCountsSchema = z.object({
  low: z.number().int(),
  medium: z.number().int(),
  high: z.number().int(),
  critical: z.number().int(),
});

export const ModelUsageBreakdownSchema = z.object({
  model: z.string(),
  analyses_count: z.number().int(),
  avg_prompt_tokens: z.number(),
  avg_completion_tokens: z.number(),
  total_cost_usd: z.number(),
  avg_latency_ms: z.number(),
});

export const TelemetrySummaryResponseSchema = z.object({
  total_analyses: z.number().int(),
  ai_enabled_analyses: z.number().int(),
  deterministic_only_analyses: z.number().int(),
  risk_counts: RiskLevelCountsSchema,
  median_latency_ms: z.number(),
  p95_latency_ms: z.number(),
  avg_prompt_tokens: z.number(),
  avg_completion_tokens: z.number(),
  total_prompt_tokens: z.number().int(),
  total_completion_tokens: z.number().int(),
  total_cost_usd: z.number(),
  avg_cost_per_pr_usd: z.number(),
  projected_cost_per_1000_prs_usd: z.number(),
  total_cited_paths: z.number().int(),
  valid_cited_paths: z.number().int(),
  citation_gate_intercepts: z.number().int(),
  models: z.array(ModelUsageBreakdownSchema),
});

export type RiskLevelCounts = z.infer<typeof RiskLevelCountsSchema>;
export type ModelUsageBreakdown = z.infer<typeof ModelUsageBreakdownSchema>;
export type TelemetrySummaryResponse = z.infer<typeof TelemetrySummaryResponseSchema>;
