import { verifyHmacSignature } from "@/lib/crypto";
import { recordSecurityEvent } from "@/services/audit";
import { syncSubscriptionState } from "@/services/billing";

export function handleStripeWebhook(payload: string, sig: string): boolean {
  const secret = process.env.STRIPE_WEBHOOK_SECRET ?? "";
  if (!verifyHmacSignature(payload, sig, secret)) {
    return false;
  }
  recordSecurityEvent("stripe.webhook", "stripe");
  syncSubscriptionState({ authorization: "Bearer system" }, "cus_1");
  return true;
}
