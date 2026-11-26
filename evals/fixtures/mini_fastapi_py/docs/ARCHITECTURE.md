# Architecture Overview

## Security & Webhooks
- `app/core/security.py` exposes `verify_api_key` and `verify_webhook_hmac` using `WEBHOOK_SECRET` from `app/core/config.py`.
- `app/api/webhooks/shipping.py` verifies signatures before calling `mark_shipped`.

## Background Worker Queue
- `app/workers/notify_worker.py` connects to `REDIS_URL` to emit shipment notifications for `OrderRecord`.
