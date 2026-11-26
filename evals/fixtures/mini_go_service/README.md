# Acme Go Billing Service

Lightweight Go microservice handling JWT token verification, subscription billing, and Stripe webhook verification.

## Environment Variables
- `AUTH_JWT_SECRET` — HMAC secret used to sign and verify session JWT tokens.
- `WEBHOOK_SIGNING_SECRET` — Shared secret for verifying inbound billing webhook signatures.
- `BILLING_CURRENCY` — Default ISO currency code (e.g. `usd`).

## Local Tests
```bash
go test ./...
```
