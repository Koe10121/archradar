import { signSessionToken, verifyToken } from "@/lib";

export function refreshSession(token: string): string {
  const claims = verifyToken(token);
  return signSessionToken(claims.sub);
}
