# Mini FastAPI Order Fulfillment Service

Python FastAPI & background worker service used for ArchRadar evaluation benchmarks.

## Environment Variables
- `WEBHOOK_SECRET` — HMAC secret used to validate incoming carrier shipping webhooks.
- `REDIS_URL` — Redis broker URL used by `app/workers/dispatch_worker.py` and `app/workers/notify_worker.py`.
