"""Inventory reservation service."""

from app.db import OrderRepository
from app.db.models import OrderRecord


def reserve_stock(order_id: str, sku: str) -> bool:
    repo = OrderRepository()
    repo.save_order(OrderRecord(order_id=order_id, sku=sku))
    return True
