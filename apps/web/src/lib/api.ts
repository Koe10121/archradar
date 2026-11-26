import { HealthResponseSchema, type HealthResponse } from "@/lib/schemas/health";

export type HealthCheckResult =
  | { ok: true; data: HealthResponse; latencyMs: number }
  | { ok: false; error: string };

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

export async function fetchApiHealth(options?: {
  isServer?: boolean;
}): Promise<HealthCheckResult> {
  const isServer = options?.isServer ?? false;
  const baseUrl = getApiBaseUrl(isServer).replace(/\/+$/, "");
  const startedAt = Date.now();

  try {
    const response = await fetch(`${baseUrl}/api/health`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const error = `API health returned HTTP ${response.status}`;
      console.error("[archradar-web] Health check HTTP error", {
        status: response.status,
        baseUrl,
      });
      return { ok: false, error };
    }

    const rawJson: unknown = await response.json();
    const parsed = HealthResponseSchema.safeParse(rawJson);
    if (!parsed.success) {
      console.error("[archradar-web] Health payload failed Zod validation", {
        issues: parsed.error.issues,
      });
      return { ok: false, error: "Invalid health payload received from API" };
    }

    return {
      ok: true,
      data: parsed.data,
      latencyMs: Date.now() - startedAt,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown network error";
    console.error("[archradar-web] Failed to reach API health endpoint", {
      baseUrl,
      message,
    });
    return { ok: false, error: message };
  }
}
