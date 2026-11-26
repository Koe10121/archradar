"""Background shipment notification worker."""

from app.core.config import get_settings
from app.db.models import OrderRecord
from app.services.fulfillment import mark_shipped


def dispatch_notification(order: OrderRecord) -> str:
    settings = get_settings()
    mark_shipped(order.order_id)
    return f"{settings.redis_url}:{order.sku}"
