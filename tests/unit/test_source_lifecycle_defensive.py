from __future__ import annotations

import copy

import pytest

from neuroai_workbench.collector.source_lifecycle import (
    LIFECYCLE_UNRESOLVED,
    evaluate_source_lifecycle,
    verify_source_lifecycle_report,
)


def _assertion() -> dict[str, str]:
    return {
        "state": "NO_LONGER_LISTED",
        "source_id": "SRC-X",
        "primary_route_id": "primary",
        "publisher_listing_route_id": "listing",
        "expected_identity": "Exact Historical Listing",
        "evidence_ref": "official-route:listing",
        "basis": "Primary absent and current official publisher listing lacks the exact identity.",
        "asserted_at": "2026-08-14T17:00:00Z",
    }


def _report() -> dict[str, object]:
    return {
        "source_id": "SRC-X",
        "selected_route_id": None,
        "report_sha256": "a" * 64,
        "route_policy": [
            {"route_id": "primary", "role": "PRIMARY", "route_class": "PRIMARY"},
            {
                "route_id": "listing",
                "role": "FALLBACK",
                "route_class": "LIVENESS_CORROBORATION",
            },
        ],
        "route_observations": [
            {
                "route_id": "primary",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 404,
            },
            {"route_id": "listing", "outcome": "SUCCESS", "corroboration_match": False},
        ],
    }


def test_route_policy_and_observation_containers_must_be_arrays() -> None:
    report = _report()
    report["route_policy"] = None
    with pytest.raises(ValueError, match="route_policy must be an array"):
        evaluate_source_lifecycle(route_report=report, lifecycle_assertion=_assertion())

    report = _report()
    report["route_observations"] = None
    with pytest.raises(ValueError, match="route_observations must be an array"):
        evaluate_source_lifecycle(route_report=report, lifecycle_assertion=_assertion())


def test_lifecycle_assertion_and_route_report_must_be_objects() -> None:
    with pytest.raises(ValueError, match="lifecycle_assertion must be an object"):
        evaluate_source_lifecycle(
            route_report=_report(),
            lifecycle_assertion="bad",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="route_report must be an object"):
        evaluate_source_lifecycle(
            route_report="bad",  # type: ignore[arg-type]
            lifecycle_assertion=_assertion(),
        )


def test_missing_primary_observation_stays_unresolved() -> None:
    report = _report()
    report["route_observations"] = [report["route_observations"][1]]  # type: ignore[index]
    resolved = evaluate_source_lifecycle(route_report=report, lifecycle_assertion=_assertion())
    assert resolved["resolution_state"] == LIFECYCLE_UNRESOLVED
    assert "PRIMARY_ROUTE_NOT_OBSERVED" in resolved["diagnostics"]


def test_verifier_detects_hash_only_and_content_only_tampering() -> None:
    route_report = _report()
    assertion = _assertion()
    valid = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=assertion)

    bad_hash = copy.deepcopy(valid)
    bad_hash["report_sha256"] = "b" * 64
    verification = verify_source_lifecycle_report(
        bad_hash,
        route_report=route_report,
        lifecycle_assertion=assertion,
    )
    assert verification["valid"] is False
    assert "recorded lifecycle report hash mismatch" in verification["errors"]

    bad_content = copy.deepcopy(valid)
    bad_content["boundary"] = "tampered"
    verification = verify_source_lifecycle_report(
        bad_content,
        route_report=route_report,
        lifecycle_assertion=assertion,
    )
    assert verification["valid"] is False
    assert "lifecycle report does not match recomputed inputs" in verification["errors"]
