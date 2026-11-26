"""Runner calling into circular package."""

from pkg.node_a import ping_a


def execute_cycle() -> str:
    return ping_a(3)
