"""Order fulfillment orchestration service."""

from app.db import OrderRepository
from app.services.inventory import reserve_stock


def create_order(order_id: str, sku: str) -> str:
    if not reserve_stock(order_id, sku):
        raise RuntimeError("Out of stock")
    return order_id


def mark_shipped(order_id: str) -> str:
    repo = OrderRepository()
    record = repo.get_order(order_id)
    record.status = "shipped"
    return repo.save_order(record)
