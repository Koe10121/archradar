"""Automated regression test validating the 30-case evaluation dataset and runner."""

import json
import sys
from pathlib import Path

from app.services.github import parse_unified_diff

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.run_benchmark import run_benchmark_async  # noqa: E402


def test_golden_dataset_structure_and_diffs() -> None:
    """All 30 benchmark cases exist, cover 5 categories, and contain valid unified diffs."""
    evals_root = _REPO_ROOT / "evals"
    datasets_dir = evals_root / "datasets"
    case_files = sorted(datasets_dir.glob("case_*.json"))
    assert len(case_files) == 30

    categories: set[str] = set()
    for case_file in case_files:
        payload = json.loads(case_file.read_text(encoding="utf-8"))
        categories.add(str(payload["category"]))
        fixture_dir = evals_root / str(payload["repo_fixture"])
        assert fixture_dir.is_dir(), f"Missing fixture {fixture_dir}"
        assert (fixture_dir / "ground_truth_graph.json").is_file()
        parsed = parse_unified_diff(str(payload["diff"]))
        assert len(parsed.changed_files) >= 1

    assert categories == {
        "benign_low_risk",
        "direct_1hop_break",
        "transitive_break",
        "doc_drift",
        "adversarial_edge",
    }


async def test_benchmark_simulated_thresholds() -> None:
    """Running the 30-case suite in simulated mode meets all ArchRadar quality targets."""
    evals_root = _REPO_ROOT / "evals"
    datasets_dir = evals_root / "datasets"

    report_md, summary = await run_benchmark_async(
        datasets_dir=datasets_dir,
        evals_root=evals_root,
        mode="simulated",
    )

    assert "ArchRadar Evaluation Benchmark Report" in report_md
    assert summary["case_count"] == 30
    assert summary["cases_passed"] == 30
    assert summary["graph_precision"] >= 0.98
    assert summary["graph_recall"] >= 0.98
    assert summary["blast_recall"] == 1.0
    assert summary["post_gate_phantom_rate"] == 0.0
    assert summary["hallucinations_intercepted"] >= 2
    assert summary["risk_agreement"] == 1.0
    assert summary["breaking_accuracy"] == 1.0
    assert summary["doc_drift_accuracy"] >= 0.85
