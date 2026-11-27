import { type z } from "zod";

import {
  PRAnalysisListSchema,
  PRAnalysisResponseSchema,
  PRCommentResponseSchema,
  VerifyGeminiKeyResponseSchema,
  type PRAnalysisResponse,
  type PRCommentResponse,
  type VerifyGeminiKeyResponse,
} from "@/lib/schemas/analysis";
import { HealthResponseSchema, type HealthResponse } from "@/lib/schemas/health";
import {
  GitHubPRListSchema,
  GraphResponseSchema,
  RepoIndexResponseSchema,
  RepositoryListSchema,
  SnapshotDiffResponseSchema,
  SnapshotListSchema,
  type GitHubPRSummary,
  type GraphResponse,
  type RepoIndexResponse,
  type RepositorySummary,
  type SnapshotDiffResponse,
  type SnapshotSummary,
} from "@/lib/schemas/repo";
import {
  TelemetrySummaryResponseSchema,
  type TelemetrySummaryResponse,
} from "@/lib/schemas/telemetry";

export type HealthCheckResult =
  | { ok: true; data: HealthResponse; latencyMs: number }
  | { ok: false; error: string };

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string };

export function isApiConfigured(isServer: boolean): boolean {
  if (process.env.NODE_ENV !== "production") {
    return true;
  }
  if (isServer) {
    return Boolean(process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL);
  }
  return Boolean(process.env.NEXT_PUBLIC_API_URL);
}

export function getApiBaseUrl(isServer: boolean): string {
  if (isServer) {
    return (
      process.env.API_INTERNAL_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      "http://localhost:8000"
    );
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

async function requestJson<T>(
  path: string,
  schema: z.ZodType<T, z.ZodTypeDef, unknown>,
  options?: {
    isServer?: boolean;
    method?: "GET" | "POST";
    body?: Record<string, unknown>;
    timeoutMs?: number;
    extraHeaders?: Record<string, string>;
  }
): Promise<ApiResult<T>> {
  const isServer = options?.isServer ?? false;
  if (!isApiConfigured(isServer)) {
    return { ok: false, error: "Standalone Demo Mode (no backend API URL configured)." };
  }

  const baseUrl = getApiBaseUrl(isServer).replace(/\/+$/, "");

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: options?.method ?? "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(options?.timeoutMs ?? 8000),
      headers: {
        Accept: "application/json",
        ...(options?.body ? { "Content-Type": "application/json" } : {}),
        ...(options?.extraHeaders ?? {}),
      },
      body: options?.body ? JSON.stringify(options.body) : undefined,
    });

    const rawJson: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail =
        rawJson &&
        typeof rawJson === "object" &&
        "detail" in rawJson &&
        typeof rawJson.detail === "string"
          ? rawJson.detail
          : `HTTP ${response.status}`;
      console.error("[archradar-web] API HTTP error", { path, status: response.status, detail });
      return { ok: false, error: detail };
    }

    const parsed = schema.safeParse(rawJson);
    if (!parsed.success) {
      console.error("[archradar-web] API payload failed Zod validation", {
        path,
        issues: parsed.error.issues,
      });
      return { ok: false, error: "Invalid response schema received from backend API." };
    }

    return { ok: true, data: parsed.data };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown network error";
    console.error("[archradar-web] Failed API request", { path, baseUrl, message });
    return { ok: false, error: message };
  }
}

export async function fetchApiHealth(options?: {
  isServer?: boolean;
}): Promise<HealthCheckResult> {
  const startedAt = Date.now();
  const result = await requestJson("/api/health", HealthResponseSchema, {
    isServer: options?.isServer,
  });
  if (!result.ok) {
    return result;
  }
  return {
    ok: true,
    data: result.data,
    latencyMs: Date.now() - startedAt,
  };
}

export async function fetchRepositories(options?: {
  isServer?: boolean;
}): Promise<ApiResult<RepositorySummary[]>> {
  return requestJson("/api/repos", RepositoryListSchema, {
    isServer: options?.isServer,
  });
}

export async function fetchRepositoryGraph(
  repoId: string,
  options?: { isServer?: boolean; snapshotId?: string }
): Promise<ApiResult<GraphResponse>> {
  const qs = options?.snapshotId
    ? `?snapshot_id=${encodeURIComponent(options.snapshotId)}`
    : "";
  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/graph${qs}`,
    GraphResponseSchema,
    { isServer: options?.isServer }
  );
}

export async function fetchRepositorySnapshots(
  repoId: string,
  options?: { isServer?: boolean }
): Promise<ApiResult<SnapshotSummary[]>> {
  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/snapshots`,
    SnapshotListSchema,
    { isServer: options?.isServer }
  );
}

export async function fetchSnapshotDiff(
  repoId: string,
  fromSnapshotId: string,
  toSnapshotId: string,
  options?: { isServer?: boolean }
): Promise<ApiResult<SnapshotDiffResponse>> {
  const params = new URLSearchParams({
    from_snapshot_id: fromSnapshotId,
    to_snapshot_id: toSnapshotId,
  });
  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/snapshots/diff?${params.toString()}`,
    SnapshotDiffResponseSchema,
    { isServer: options?.isServer }
  );
}

export async function fetchTelemetrySummary(options?: {
  isServer?: boolean;
  repoId?: string;
}): Promise<ApiResult<TelemetrySummaryResponse>> {
  const qs = options?.repoId
    ? `?repo_id=${encodeURIComponent(options.repoId)}`
    : "";
  return requestJson(
    `/api/telemetry/summary${qs}`,
    TelemetrySummaryResponseSchema,
    { isServer: options?.isServer }
  );
}

export async function fetchRepositoryAnalyses(
  repoId: string,
  options?: { isServer?: boolean }
): Promise<ApiResult<PRAnalysisResponse[]>> {
  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/analyses`,
    PRAnalysisListSchema,
    { isServer: options?.isServer }
  );
}

export async function fetchRepositoryGitHubPRs(
  repoId: string
): Promise<ApiResult<GitHubPRSummary[]>> {
  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/github-prs`,
    GitHubPRListSchema,
    { timeoutMs: 12_000 }
  );
}

export async function fetchAnalysisPrComment(
  analysisId: string,
  options?: { isServer?: boolean }
): Promise<ApiResult<PRCommentResponse>> {
  return requestJson(
    `/api/analyses/${encodeURIComponent(analysisId)}/pr-comment`,
    PRCommentResponseSchema,
    { isServer: options?.isServer }
  );
}

export async function indexRepository(payload: {
  repo_url?: string;
  local_path?: string;
  branch?: string;
  is_demo?: boolean;
}): Promise<ApiResult<RepoIndexResponse>> {
  return requestJson("/api/repos/index", RepoIndexResponseSchema, {
    method: "POST",
    body: payload,
    timeoutMs: 45_000,
  });
}

export async function verifyGeminiApiKey(
  apiKey: string
): Promise<ApiResult<VerifyGeminiKeyResponse>> {
  return requestJson("/api/ai/verify-key", VerifyGeminiKeyResponseSchema, {
    method: "POST",
    timeoutMs: 10_000,
    extraHeaders: { "X-Gemini-Api-Key": apiKey },
  });
}

export async function analyzePullRequest(
  repoId: string,
  payload: {
    pr_url?: string;
    raw_diff?: string;
    pr_title?: string;
    pr_description?: string;
    run_ai?: boolean;
  },
  options?: { geminiApiKey?: string }
): Promise<ApiResult<PRAnalysisResponse>> {
  const extraHeaders =
    payload.run_ai && options?.geminiApiKey
      ? { "X-Gemini-Api-Key": options.geminiApiKey }
      : undefined;

  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/analyze-pr`,
    PRAnalysisResponseSchema,
    {
      method: "POST",
      body: payload,
      timeoutMs: 45_000,
      extraHeaders,
    }
  );
}
