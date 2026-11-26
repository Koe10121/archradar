"""Database domain models."""

from dataclasses import dataclass


@dataclass
class OrderRecord:
    order_id: str
    sku: str
    status: str = "pending"
