# Architecture — Acme Go Billing Service

## Authentication & Token Verification
`internal/auth/token.go` exposes `VerifyToken(token string) (Claims, error)` and `VerifyHMAC(payload, sig, secret string) bool`.

## Billing Service
`internal/billing/service.go` imports `internal/auth` and exposes `ChargeSubscription(token string, planID string) (Invoice, error)`.

## API Routes & Webhooks
- `HandleCheckout` (`cmd/server/main.go`) orchestrates checkout billing.
- `HandleBillingWebhook` (`internal/webhooks/handler.go`) verifies webhook signatures and reconciles invoices.
