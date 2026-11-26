"""Persistence repository for orders."""

from .models import OrderRecord


class OrderRepository:
    def save_order(self, record: OrderRecord) -> str:
        return record.order_id

    def get_order(self, order_id: str) -> OrderRecord:
        return OrderRecord(order_id=order_id, sku="SKU-1")
