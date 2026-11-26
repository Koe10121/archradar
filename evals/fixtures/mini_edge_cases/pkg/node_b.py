"""Node B in circular import pair."""

from .node_a import ping_a


def ping_b(limit: int) -> str:
    if limit <= 0:
        return "b"
    return ping_a(limit - 1)
