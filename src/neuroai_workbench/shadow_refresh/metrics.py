from __future__ import annotations

from typing import Any, cast

from .schemas import (
    DEFAULT_GO_NO_GO_THRESHOLDS,
    SHADOW_EVALUATION_STATUS,
    SHADOW_REFRESH_BOUNDARY,
    validate_shadow_refresh_go_no_go_metrics,
    validate_shadow_refresh_run_results,
)


def _safe_rate(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def compute_go_no_go_metrics(
    run_results: dict[str, Any],
    *,
    thresholds: dict[str, float | int] | None = None,
    generated_at: str = "2026-08-02T12:00:00Z",
    generated_by: str = "shadow-refresh-stub",
) -> dict[str, Any]:
    """Compute go/no-go metrics from synthetic or recorded shadow run results.

    This is a deterministic stub for evaluation scaffolding. It does not ingest live captures
    or establish operational readiness.
    """
    validation_errors = validate_shadow_refresh_run_results(run_results)
    if validation_errors:
        raise ValueError(f"Invalid shadow run results: {validation_errors[0]['message']}")

    effective_thresholds: dict[str, float | int] = dict(DEFAULT_GO_NO_GO_THRESHOLDS)
    if thresholds:
        effective_thresholds.update(thresholds)

    def threshold_float(key: str) -> float:
        return float(effective_thresholds[key])

    def threshold_int(key: str) -> int:
        return int(effective_thresholds[key])

    captures = run_results["captures"]
    candidates = run_results["candidates"]
    entity_resolution = run_results["entity_resolution"]
    review = run_results["review"]
    reopening = run_results["reopening"]
    provenance = run_results["provenance"]
    publication = run_results["publication"]
    model_assistance = run_results.get("model_assistance", {"minutes_saved": 0.0, "errors_introduced": 0})

    metrics = {
        "retrieval_success_rate": _safe_rate(captures["succeeded"], captures["attempted"]),
        "retrieval_failure_rate": _safe_rate(captures["failed"], captures["attempted"]),
        "unchanged_capture_rate": _safe_rate(captures["unchanged"], captures["succeeded"]),
        "changed_capture_rate": _safe_rate(captures["changed"], captures["succeeded"]),
        "candidate_precision": _safe_rate(
            candidates["true_positives"],
            candidates["true_positives"] + candidates["false_positives"],
        ),
        "candidate_recall": _safe_rate(
            candidates["true_positives"],
            candidates["true_positives"] + candidates["false_negatives"],
        ),
        "unsupported_candidate_rate": _safe_rate(candidates["unsupported"], candidates["generated"]),
        "entity_resolution_precision": _safe_rate(entity_resolution["correct"], entity_resolution["decisions"]),
        "reviewer_agreement_rate": _safe_rate(review["agreements"], review["agreements"] + review["disagreements"]),
        "mean_adjudication_minutes_per_candidate": _safe_rate(
            review["total_adjudication_minutes"],
            review["sampled_candidates"],
        ),
        "model_assistance_minutes_saved": float(model_assistance["minutes_saved"]),
        "model_assistance_errors_introduced": int(model_assistance["errors_introduced"]),
        "reopening_precision": _safe_rate(reopening["true_positives"], reopening["recommended"]),
        "reopening_false_positive_rate": _safe_rate(reopening["false_positives"], reopening["recommended"]),
        "provenance_closure_rate": _safe_rate(provenance["complete_records"], provenance["total_records"]),
        "publication_reconciliation_error_count": int(publication["reconciliation_errors"]),
        "operational_cost_by_source_class": dict(run_results.get("cost_by_source_class", {})),
    }

    retrieval_success_rate = cast(float, metrics["retrieval_success_rate"])
    unsupported_candidate_rate = cast(float, metrics["unsupported_candidate_rate"])
    candidate_precision = cast(float, metrics["candidate_precision"])
    reopening_precision = cast(float, metrics["reopening_precision"])
    reopening_false_positive_rate = cast(float, metrics["reopening_false_positive_rate"])
    provenance_closure_rate = cast(float, metrics["provenance_closure_rate"])
    publication_reconciliation_error_count = cast(int, metrics["publication_reconciliation_error_count"])

    criteria_results = [
        _evaluate_criterion(
            "retrieval_success",
            retrieval_success_rate >= threshold_float("minimum_retrieval_success_rate"),
            f"retrieval_success_rate={retrieval_success_rate:.3f}",
        ),
        _evaluate_criterion(
            "unsupported_candidates",
            unsupported_candidate_rate <= threshold_float("maximum_unsupported_candidate_rate"),
            f"unsupported_candidate_rate={unsupported_candidate_rate:.3f}",
        ),
        _evaluate_criterion(
            "candidate_precision",
            candidate_precision >= threshold_float("minimum_candidate_precision"),
            f"candidate_precision={candidate_precision:.3f}",
        ),
        _evaluate_criterion(
            "reopening_precision",
            reopening_precision >= threshold_float("minimum_reopening_precision"),
            f"reopening_precision={reopening_precision:.3f}",
        ),
        _evaluate_criterion(
            "reopening_false_positives",
            reopening_false_positive_rate <= threshold_float("maximum_reopening_false_positive_rate"),
            f"reopening_false_positive_rate={reopening_false_positive_rate:.3f}",
        ),
        _evaluate_criterion(
            "provenance_closure",
            provenance_closure_rate >= threshold_float("minimum_provenance_closure_rate"),
            f"provenance_closure_rate={provenance_closure_rate:.3f}",
        ),
        _evaluate_criterion(
            "publication_reconciliation",
            publication_reconciliation_error_count <= threshold_int("maximum_publication_reconciliation_errors"),
            f"publication_reconciliation_error_count={publication_reconciliation_error_count}",
        ),
    ]

    recommendation = _derive_recommendation(criteria_results)
    package = {
        "metadata": {
            "title": "Shadow refresh go/no-go metrics",
            "generated_at": generated_at,
            "status": SHADOW_EVALUATION_STATUS,
            "generated_by": generated_by,
        },
        "run_id": run_results["run_id"],
        "metrics": metrics,
        "thresholds": effective_thresholds,
        "evaluation": {
            "recommendation": recommendation,
            "criteria_results": criteria_results,
        },
        "withheld_claims": [
            "Go/no-go metrics are rehearsal outputs only and do not authorize a canonical successor release.",
            "Passing thresholds in a synthetic or shadow run does not establish operational readiness.",
            "Human approval remains required before any live refresh over protected or archive sources.",
        ],
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    output_errors = validate_shadow_refresh_go_no_go_metrics(package)
    if output_errors:
        raise ValueError(f"Computed metrics package failed schema validation: {output_errors[0]['message']}")
    return package


def _evaluate_criterion(criterion_id: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"criterion_id": criterion_id, "passed": passed, "detail": detail}


def _derive_recommendation(criteria_results: list[dict[str, Any]]) -> str:
    if not criteria_results:
        return "INCOMPLETE"
    if all(item["passed"] for item in criteria_results):
        return "GO"
    if any(not item["passed"] for item in criteria_results):
        return "NO_GO"
    return "INCOMPLETE"
