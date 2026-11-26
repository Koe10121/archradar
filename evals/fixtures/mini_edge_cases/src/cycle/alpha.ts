import { stepBeta } from "./beta";

export function stepAlpha(depth: number): string {
  if (depth <= 0) return "done";
  return stepBeta(depth - 1);
}
