import { verifyToken } from "@/lib/token";

export interface AuthContext {
  userId: string;
  tier: string;
}

export function requireAuth(headers: Record<string, string>): AuthContext {
  const header = headers["authorization"] ?? headers["Authorization"] ?? "";
  const token = header.replace("Bearer ", "").trim();
  const claims = verifyToken(token);
  return { userId: claims.sub, tier: claims.tier };
}
