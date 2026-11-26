import { requireAuth } from "@/middleware/auth";
import { chargeSubscription } from "@/services/billing";

export function postCheckout(headers: Record<string, string>, planId: string): string {
  const ctx = requireAuth(headers);
  const invoice = chargeSubscription(ctx, planId);
  return invoice.invoiceId;
}
