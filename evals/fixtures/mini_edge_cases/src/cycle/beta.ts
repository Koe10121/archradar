import { stepAlpha } from "./alpha";

export function stepBeta(depth: number): string {
  if (depth <= 0) return "beta";
  return stepAlpha(depth - 1);
}
