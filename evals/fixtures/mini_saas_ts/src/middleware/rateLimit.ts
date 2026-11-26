import { verifyToken } from "../lib/token";

export function checkRateLimit(token: string): boolean {
  const claims = verifyToken(token);
  return claims.tier === "pro";
}
