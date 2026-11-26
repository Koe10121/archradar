import { computeLeafHash } from "@/barrel";

export function hashPayload(body: string): string {
  return computeLeafHash(body);
}
