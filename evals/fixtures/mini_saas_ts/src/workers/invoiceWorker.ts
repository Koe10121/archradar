import { formatUsdCents } from "@/lib/formatters";
import { chargeSubscription } from "@/services/billing";

export function enqueueInvoicePdf(userId: string, planId: string): string {
  const invoice = chargeSubscription({ userId, tier: "pro" }, planId);
  return `${invoice.invoiceId}:${formatUsdCents(invoice.amountCents)}`;
}
