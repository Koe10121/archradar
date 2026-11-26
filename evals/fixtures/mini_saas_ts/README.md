# Mini SaaS Billing Service

TypeScript billing, authentication, and Stripe webhook service used for ArchRadar evaluation benchmarks.

## Environment Variables
- `STRIPE_WEBHOOK_SECRET` — HMAC secret used by `src/api/webhooks/stripe.ts` to verify Stripe webhook payloads.
- `AUTH_TOKEN_SECRET` — Secret key used for JWT signing and verification.
- `PORT` — HTTP server port (defaults to `3000`).
