import { formatUsdCents } from "@/lib/formatters";
import { postCheckout } from "@/api/routes/checkout";

export function renderBillingSummary(cents: number): string {
  const label = cents > 0 ? "Due now" : "Credit";
  return `${label}: ${formatUsdCents(cents)}`;
}

export function submitQuickCheckout(planId: string): string {
  return postCheckout({}, planId);
}
