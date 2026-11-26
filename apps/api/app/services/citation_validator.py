"""Post-LLM citation verification gate preventing hallucinated file paths."""

import logging

from app.parser.base import normalize_repo_path
from app.schemas.analysis import (
    BlastRadiusReport,
    CitationValidationTelemetry,
    ImpactedFlow,
)

logger = logging.getLogger(__name__)


def _is_valid_path(raw_path: str, valid_paths: set[str]) -> str | None:
    try:
        normalized = normalize_repo_path(raw_path)
    except ValueError:
        return None
    return normalized if normalized in valid_paths else None


def validate_report_citations(
    report: BlastRadiusReport,
    valid_paths: set[str],
) -> tuple[BlastRadiusReport, CitationValidationTelemetry]:
    """Verify every cited file path exists in the snapshot graph; strip phantom files."""
    total_cited = 0
    valid_cited = 0
    stripped_paths: list[str] = []
    verified_flows: list[ImpactedFlow] = []

    for flow in report.impacted_flows:
        total_cited += 1
        verified_entry = _is_valid_path(flow.entry_file, valid_paths)
        if verified_entry is None:
            stripped_paths.append(flow.entry_file)
        else:
            valid_cited += 1

        verified_affected: list[str] = []
        for raw_affected in flow.affected_files:
            total_cited += 1
            verified = _is_valid_path(raw_affected, valid_paths)
            if verified is None:
                stripped_paths.append(raw_affected)
            else:
                valid_cited += 1
                if verified not in verified_affected:
                    verified_affected.append(verified)

        if verified_entry is None:
            if not verified_affected:
                continue
            verified_entry = verified_affected[0]

        verified_flows.append(
            ImpactedFlow(
                title=flow.title,
                severity=flow.severity,
                entry_file=verified_entry,
                affected_files=verified_affected,
                explanation=flow.explanation,
                suggested_test=flow.suggested_test,
            )
        )

    hallucination_caught = len(stripped_paths)
    if hallucination_caught > 0:
        logger.warning(
            "Post-LLM citation validator stripped %d hallucinated path(s): %s",
            hallucination_caught,
            stripped_paths,
        )

    sanitized_report = report.model_copy(update={"impacted_flows": verified_flows})
    telemetry = CitationValidationTelemetry(
        total_cited_paths=total_cited,
        valid_cited_paths=valid_cited,
        hallucination_caught=hallucination_caught,
        stripped_paths=stripped_paths,
    )
    return sanitized_report, telemetry
