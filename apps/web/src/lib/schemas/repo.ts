import { z } from "zod";

export const ExportedSymbolSchema = z.object({
  name: z.string(),
  kind: z.string(),
  signature: z.string(),
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

export const GraphResponseSchema = z.object({
  repository_id: z.string(),
  snapshot_id: z.string(),
  commit_sha: z.string(),
  file_count: z.number().int(),
  edge_count: z.number().int(),
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
});

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

export type ExportedSymbol = z.infer<typeof ExportedSymbolSchema>;
export type GraphNode = z.infer<typeof GraphNodeSchema>;
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;
export type GraphResponse = z.infer<typeof GraphResponseSchema>;
export type RepositorySummary = z.infer<typeof RepositorySummarySchema>;
export type RepoIndexResponse = z.infer<typeof RepoIndexResponseSchema>;
