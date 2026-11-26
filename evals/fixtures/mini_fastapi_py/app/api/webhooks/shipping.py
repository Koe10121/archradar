"""Carrier shipping webhook handler."""

from app.core.security import verify_webhook_hmac
from app.services.fulfillment import mark_shipped


def handle_shipping_webhook(payload: bytes, signature: str, order_id: str) -> dict[str, str]:
    if not verify_webhook_hmac(payload, signature):
        raise PermissionError("Invalid webhook signature")
    updated = mark_shipped(order_id)
    return {"status": "ok", "order_id": updated}
