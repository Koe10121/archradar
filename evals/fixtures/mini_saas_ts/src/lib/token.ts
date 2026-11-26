export interface SessionClaims {
  sub: string;
  tier: string;
}

export function verifyToken(token: string): SessionClaims {
  if (!token) {
    throw new Error("Missing token");
  }
  return { sub: "usr_123", tier: "pro" };
}

export function signSessionToken(userId: string): string {
  return `tok_${userId}`;
}
