import { z } from "zod";

export const ExportedSymbolSchema = z.object({
  name: z.string(),
  kind: z.string(),
  signature: z.string(),
  start_line: z.number().int().nullable().optional(),
  end_line: z.number().int().nullable().optional(),
});

export const GraphNodeSchema = z.object({
  id: z.string(),
  path: z.string(),
  language: z.string(),
  module_group: z.string(),
  loc: z.number().int(),
  exports: z.array(ExportedSymbolSchema),
  in_degree: z.number().int(),
  out_degree: z.number().int(),
  is_test: z.boolean().optional(),
});

export const GraphEdgeSchema = z.object({
  id: z.string(),
  source_node_id: z.string(),
  target_node_id: z.string(),
  source_path: z.string(),
  target_path: z.string(),
  edge_type: z.string(),
  imported_symbols: z.array(z.string()),
});

export const CycleFindingSchema = z.object({
  cycle_paths: z.array(z.string()),
  length: z.number().int(),
  severity: z.enum(["warning", "high"]),
});

export const HotspotFindingSchema = z.object({
  path: z.string(),
  module_group: z.string(),
  in_degree: z.number().int(),
  out_degree: z.number().int(),
  loc: z.number().int(),
  has_tests: z.boolean(),
  touches_sensitive_boundary: z.boolean(),
  reason: z.string(),
});

export const LayerViolationSchema = z.object({
  source_path: z.string(),
  target_path: z.string(),
  source_layer: z.string(),
  target_layer: z.string(),
  imported_symbols: z.array(z.string()).default([]),
  reason: z.string(),
});

export const ArchitectureHealthSchema = z.object({
  health_score: z.number().int().min(0).max(100),
  grade: z.enum(["healthy", "watch", "at_risk"]),
  cycle_count: z.number().int(),
  layer_violation_count: z.number().int(),
  hotspot_count: z.number().int(),
  untested_hub_count: z.number().int(),
  cycles: z.array(CycleFindingSchema).default([]),
  hotspots: z.array(HotspotFindingSchema).default([]),
  layer_violations: z.array(LayerViolationSchema).default([]),
});

export const GraphResponseSchema = z.object({
  repository_id: z.string(),
  snapshot_id: z.string(),
  commit_sha: z.string(),
  file_count: z.number().int(),
  edge_count: z.number().int(),
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
  arch_health: ArchitectureHealthSchema.nullable().optional(),
});

export const GitHubPRSummarySchema = z.object({
  number: z.number().int(),
  title: z.string(),
  state: z.string(),
  author: z.string(),
  html_url: z.string(),
  updated_at: z.string(),
  draft: z.boolean().default(false),
});

export const GitHubPRListSchema = z.array(GitHubPRSummarySchema);

export const RepositorySummarySchema = z.object({
  id: z.string(),
  owner: z.string(),
  name: z.string(),
  url: z.string(),
  default_branch: z.string(),
  is_demo: z.boolean(),
  last_indexed_sha: z.string().nullable(),
  latest_snapshot_id: z.string().nullable(),
  file_count: z.number().int(),
  edge_count: z.number().int(),
  created_at: z.string(),
});

export const RepositoryListSchema = z.array(RepositorySummarySchema);

export const RepoIndexResponseSchema = z.object({
  repository_id: z.string(),
  snapshot_id: z.string(),
  commit_sha: z.string(),
  status: z.string(),
  file_count: z.number().int(),
  edge_count: z.number().int(),
});

export const SnapshotSummarySchema = z.object({
  id: z.string(),
  repository_id: z.string(),
  commit_sha: z.string(),
  file_count: z.number().int(),
  edge_count: z.number().int(),
  status: z.string(),
  created_at: z.string(),
});

export const SnapshotListSchema = z.array(SnapshotSummarySchema);

export const SnapshotDiffEdgeSchema = z.object({
  source_path: z.string(),
  target_path: z.string(),
  edge_type: z.string(),
  imported_symbols: z.array(z.string()),
});

export const CentralityDeltaSchema = z.object({
  path: z.string(),
  module_group: z.string(),
  language: z.string(),
  from_in_degree: z.number().int(),
  to_in_degree: z.number().int(),
  in_degree_delta: z.number().int(),
  from_out_degree: z.number().int(),
  to_out_degree: z.number().int(),
  out_degree_delta: z.number().int(),
  status: z.enum(["added", "removed", "changed"]),
});

export const SnapshotDiffResponseSchema = z.object({
  repository_id: z.string(),
  from_snapshot: SnapshotSummarySchema,
  to_snapshot: SnapshotSummarySchema,
  added_files: z.array(z.string()),
  removed_files: z.array(z.string()),
  added_edges: z.array(SnapshotDiffEdgeSchema),
  removed_edges: z.array(SnapshotDiffEdgeSchema),
  centrality_deltas: z.array(CentralityDeltaSchema),
  file_count_delta: z.number().int(),
  edge_count_delta: z.number().int(),
});

export type ExportedSymbol = z.infer<typeof ExportedSymbolSchema>;
export type GraphNode = z.infer<typeof GraphNodeSchema>;
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;
export type GraphResponse = z.infer<typeof GraphResponseSchema>;
export type RepositorySummary = z.infer<typeof RepositorySummarySchema>;
export type RepoIndexResponse = z.infer<typeof RepoIndexResponseSchema>;
export type SnapshotSummary = z.infer<typeof SnapshotSummarySchema>;
export type SnapshotDiffEdge = z.infer<typeof SnapshotDiffEdgeSchema>;
export type CentralityDelta = z.infer<typeof CentralityDeltaSchema>;
export type SnapshotDiffResponse = z.infer<typeof SnapshotDiffResponseSchema>;
export type CycleFinding = z.infer<typeof CycleFindingSchema>;
export type HotspotFinding = z.infer<typeof HotspotFindingSchema>;
export type LayerViolation = z.infer<typeof LayerViolationSchema>;
export type ArchitectureHealth = z.infer<typeof ArchitectureHealthSchema>;
export type GitHubPRSummary = z.infer<typeof GitHubPRSummarySchema>;
