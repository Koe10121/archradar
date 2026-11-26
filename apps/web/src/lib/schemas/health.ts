import { z } from "zod";

export const HealthResponseSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  service: z.string(),
  version: z.string(),
  environment: z.string(),
  database: z.enum(["connected", "unavailable"]),
  timestamp: z.string(),
  correlation_id: z.string(),
});

export type HealthResponse = z.infer<typeof HealthResponseSchema>;
