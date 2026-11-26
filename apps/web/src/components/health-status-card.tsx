"use client";

import { useState } from "react";
import { Activity, Database, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchApiHealth, type HealthCheckResult } from "@/lib/api";

interface HealthStatusCardProps {
  initialResult: HealthCheckResult;
}

export function HealthStatusCard({
  initialResult,
}: HealthStatusCardProps): React.JSX.Element {
  const [result, setResult] = useState<HealthCheckResult>(initialResult);
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function handleRefresh(): Promise<void> {
    setIsRefreshing(true);
    const nextResult = await fetchApiHealth({ isServer: false });
    setResult(nextResult);
    setIsRefreshing(false);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1.5">
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-amber-400" />
            Backend API & Database Health
          </CardTitle>
          <CardDescription>
            Live status fetched from <code className="text-xs">GET /api/health</code>{" "}
            and validated with Zod.
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleRefresh()}
          disabled={isRefreshing}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
          {isRefreshing ? "Checking..." : "Re-check"}
        </Button>
      </CardHeader>

      <CardContent>
        {result.ok ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-border bg-secondary/40 p-3">
              <p className="text-xs text-muted-foreground">API Service</p>
              <div className="mt-1.5 flex items-center justify-between gap-2">
                <span className="font-mono text-sm font-medium">{result.data.service}</span>
                <Badge variant={result.data.status === "ok" ? "success" : "warning"}>
                  {result.data.status}
                </Badge>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-secondary/40 p-3">
              <p className="text-xs text-muted-foreground">PostgreSQL</p>
              <div className="mt-1.5 flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <Database className="h-3.5 w-3.5 text-muted-foreground" />
                  {result.data.database}
                </span>
                <Badge
                  variant={result.data.database === "connected" ? "success" : "warning"}
                >
                  {result.data.database === "connected" ? "ready" : "offline"}
                </Badge>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-secondary/40 p-3">
              <p className="text-xs text-muted-foreground">Version / Env</p>
              <p className="mt-1.5 font-mono text-sm">
                v{result.data.version} ({result.data.environment})
              </p>
            </div>

            <div className="rounded-lg border border-border bg-secondary/40 p-3">
              <p className="text-xs text-muted-foreground">Latency & Correlation</p>
              <p className="mt-1.5 truncate font-mono text-xs text-muted-foreground">
                {result.latencyMs}ms · {result.data.correlation_id.slice(0, 12)}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-lg border border-red-500/30 bg-red-500/10 p-4">
            <div>
              <p className="text-sm font-medium text-red-200">
                Backend unreachable from frontend
              </p>
              <p className="mt-0.5 font-mono text-xs text-red-300/80">{result.error}</p>
            </div>
            <Badge variant="danger">offline</Badge>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
