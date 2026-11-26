"""HTTP route handlers for order creation."""

from app.core.security import verify_api_key
from app.services.fulfillment import create_order


def post_order(api_key: str, order_id: str, sku: str) -> dict[str, str]:
    tenant = verify_api_key(api_key)
    created_id = create_order(order_id, sku)
    return {"tenant": tenant, "order_id": created_id}
