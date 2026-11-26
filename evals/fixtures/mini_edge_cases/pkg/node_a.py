"""Node A in circular import pair."""

from .node_b import ping_b


def ping_a(limit: int) -> str:
    if limit <= 0:
        return "a"
    return ping_b(limit - 1)
