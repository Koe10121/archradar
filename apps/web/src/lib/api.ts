import { type z } from "zod";

import {
  PRAnalysisResponseSchema,
  type PRAnalysisResponse,
} from "@/lib/schemas/analysis";
import { HealthResponseSchema, type HealthResponse } from "@/lib/schemas/health";
import {
  GraphResponseSchema,
  RepoIndexResponseSchema,
  RepositoryListSchema,
  type GraphResponse,
  type RepoIndexResponse,
  type RepositorySummary,
} from "@/lib/schemas/repo";

export type HealthCheckResult =
  | { ok: true; data: HealthResponse; latencyMs: number }
  | { ok: false; error: string };

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string };

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
  schema: z.ZodType<T>,
  options?: {
    isServer?: boolean;
    method?: "GET" | "POST";
    body?: Record<string, unknown>;
  }
): Promise<ApiResult<T>> {
  const isServer = options?.isServer ?? false;
  const baseUrl = getApiBaseUrl(isServer).replace(/\/+$/, "");

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: options?.method ?? "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(options?.body ? { "Content-Type": "application/json" } : {}),
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
  options?: { isServer?: boolean }
): Promise<ApiResult<GraphResponse>> {
  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/graph`,
    GraphResponseSchema,
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
  }
): Promise<ApiResult<PRAnalysisResponse>> {
  return requestJson(
    `/api/repos/${encodeURIComponent(repoId)}/analyze-pr`,
    PRAnalysisResponseSchema,
    {
      method: "POST",
      body: payload,
    }
  );
}
