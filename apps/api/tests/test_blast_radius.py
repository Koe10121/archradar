"""Unit tests for deterministic reverse-BFS BlastRadiusCalculator."""

from app.services.blast_radius import BlastRadiusCalculator, EdgeSnapshot, NodeSnapshot


def _node(path: str, in_degree: int = 1, out_degree: int = 1) -> NodeSnapshot:
    return NodeSnapshot(
        path=path,
        language="typescript",
        module_group="src",
        loc=40,
        in_degree=in_degree,
        out_degree=out_degree,
        exports=[],
    )


def test_blast_radius_multi_hop_and_depth_limit() -> None:
    """Reverse BFS finds direct, hop_1, hop_2, hop_3 and stops before depth 4."""
    nodes = [
        _node("src/utils/token.ts", in_degree=2, out_degree=0),
        _node("src/middleware/auth.ts", in_degree=2, out_degree=1),
        _node("src/services/billing.ts", in_degree=1, out_degree=1),
        _node("src/api/webhooks/stripe.ts", in_degree=1, out_degree=1),
        _node("src/app/dashboard.ts", in_degree=0, out_degree=1),
    ]
    edges = [
        EdgeSnapshot("src/middleware/auth.ts", "src/utils/token.ts", "import", ["verifyToken"]),
        EdgeSnapshot(
            "src/services/billing.ts",
            "src/middleware/auth.ts",
            "import",
            ["requireAuth"],
        ),
        EdgeSnapshot("src/api/webhooks/stripe.ts", "src/services/billing.ts", "import", ["charge"]),
        EdgeSnapshot("src/app/dashboard.ts", "src/api/webhooks/stripe.ts", "import", ["status"]),
    ]

    calc = BlastRadiusCalculator()
    result = calc.calculate(
        nodes=nodes,
        edges=edges,
        changed_files=["src/utils/token.ts"],
        changed_symbols_by_file={"src/utils/token.ts": {"verifyToken"}},
        max_depth=3,
    )

    assert result.direct == ["src/utils/token.ts"]
    assert result.hop_1 == ["src/middleware/auth.ts"]
    assert result.hop_2 == ["src/services/billing.ts"]
    assert result.hop_3 == ["src/api/webhooks/stripe.ts"]
    assert "src/app/dashboard.ts" not in result.hop_3
    assert "src/middleware/auth.ts" in result.symbol_matched_files
    assert "auth" in result.sensitive_boundaries_touched
    assert "webhooks" in result.sensitive_boundaries_touched
    assert result.score >= 50
    assert result.deterministic_risk in {"high", "critical"}


def test_blast_radius_handles_cycles_cleanly() -> None:
    """Circular imports terminate cleanly without duplicating nodes across hops."""
    nodes = [_node("src/a.ts", 1, 1), _node("src/b.ts", 1, 1)]
    edges = [
        EdgeSnapshot("src/b.ts", "src/a.ts", "import", ["fnA"]),
        EdgeSnapshot("src/a.ts", "src/b.ts", "import", ["fnB"]),
    ]

    result = BlastRadiusCalculator().calculate(nodes, edges, changed_files=["src/a.ts"])
    assert result.direct == ["src/a.ts"]
    assert result.hop_1 == ["src/b.ts"]
    assert result.hop_2 == []
