import { requireAuth, type AuthContext } from "@/middleware/auth";
import { recordSecurityEvent } from "./audit";

export interface InvoiceResult {
  invoiceId: string;
  amountCents: number;
}

export function chargeSubscription(ctx: AuthContext, planId: string): InvoiceResult {
  recordSecurityEvent("billing.charge", ctx.userId);
  return { invoiceId: `inv_${planId}`, amountCents: 4900 };
}

export function syncSubscriptionState(headers: Record<string, string>, customerId: string): void {
  const ctx = requireAuth(headers);
  recordSecurityEvent("billing.sync", `${ctx.userId}:${customerId}`);
}
