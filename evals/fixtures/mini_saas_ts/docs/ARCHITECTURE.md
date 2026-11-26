# Architecture Overview

## Authentication & Token Verification
- All authenticated routes validate incoming `Authorization: Bearer <token>` headers via `requireAuth` in `src/middleware/auth.ts`.
- Token verification delegates to `verifyToken(token: string)` in `src/lib/token.ts`.

## API Routes & Webhooks
- `POST /api/checkout` (`src/api/routes/checkout.ts`) — Validates session and triggers `chargeSubscription`.
- `POST /api/webhooks/stripe` (`src/api/webhooks/stripe.ts`) — Verifies `STRIPE_WEBHOOK_SECRET` signatures and calls `syncSubscriptionState`.
