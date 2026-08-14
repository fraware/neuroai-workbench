from __future__ import annotations

import copy

import pytest

from neuroai_workbench.collector.source_lifecycle import (
    LIFECYCLE_RESOLVED,
    LIFECYCLE_UNRESOLVED,
    NO_LONGER_LISTED,
    evaluate_source_lifecycle,
    verify_source_lifecycle_report,
)


def _route_report() -> dict[str, object]:
    return {
        "source_id": "SRC-JOB",
        "availability_state": "UNRESOLVED",
        "selected_route_id": None,
        "report_sha256": "a" * 64,
        "route_policy": [
            {
                "route_id": "deep-page",
                "role": "PRIMARY",
                "route_class": "PRIMARY",
            },
            {
                "route_id": "publisher-index",
                "role": "FALLBACK",
                "route_class": "LIVENESS_CORROBORATION",
            },
        ],
        "route_observations": [
            {
                "route_id": "deep-page",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 404,
            },
            {
                "route_id": "publisher-index",
                "outcome": "SUCCESS",
                "corroboration_match": False,
            },
        ],
    }


def _assertion() -> dict[str, str]:
    return {
        "state": "NO_LONGER_LISTED",
        "source_id": "SRC-JOB",
        "primary_route_id": "deep-page",
        "publisher_listing_route_id": "publisher-index",
        "expected_identity": "Vision Rehabilitation Specialist, EU",
        "evidence_ref": "route-observation:publisher-index:2026-08-14",
        "basis": "Registered deep page is absent and current official publisher listing does not contain the exact role identity.",
        "asserted_at": "2026-08-14T17:00:00Z",
    }


def test_no_longer_listed_requires_404_and_current_official_listing_absence() -> None:
    report = evaluate_source_lifecycle(route_report=_route_report(), lifecycle_assertion=_assertion())
    assert report["resolution_state"] == LIFECYCLE_RESOLVED
    assert report["lifecycle_state"] == NO_LONGER_LISTED
    assert report["source_active_expected"] is False
    assert report["evidence_substitution_allowed"] is False
    assert report["diagnostics"] == []


def test_404_alone_never_establishes_no_longer_listed() -> None:
    route_report = _route_report()
    route_report["route_observations"] = [route_report["route_observations"][0]]  # type: ignore[index]
    report = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=_assertion())
    assert report["resolution_state"] == LIFECYCLE_UNRESOLVED
    assert report["lifecycle_state"] is None
    assert "PUBLISHER_LISTING_NOT_OBSERVED" in report["diagnostics"]


def test_listing_still_contains_identity_prevents_lifecycle_resolution() -> None:
    route_report = _route_report()
    route_report["route_observations"][1]["corroboration_match"] = True  # type: ignore[index]
    report = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=_assertion())
    assert report["resolution_state"] == LIFECYCLE_UNRESOLVED
    assert "EXACT_IDENTITY_STILL_PRESENT_OR_NOT_CHECKED" in report["diagnostics"]


def test_successful_registered_route_prevents_no_longer_listed_claim() -> None:
    route_report = _route_report()
    route_report["selected_route_id"] = "publisher-index"
    report = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=_assertion())
    assert report["resolution_state"] == LIFECYCLE_UNRESOLVED
    assert "SOURCE_STILL_RESOLVES_THROUGH_REGISTERED_ROUTE" in report["diagnostics"]


def test_primary_must_be_confirmed_404_or_410_http_failure() -> None:
    for mutation in [
        {"outcome": "SUCCESS", "failure_class": None, "http_status": 200},
        {"outcome": "FAILURE", "failure_class": "HTTP_ERROR", "http_status": 403},
        {"outcome": "FAILURE", "failure_class": "NETWORK_ERROR", "http_status": None},
    ]:
        route_report = _route_report()
        route_report["route_observations"][0].update(mutation)  # type: ignore[index]
        report = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=_assertion())
        assert report["resolution_state"] == LIFECYCLE_UNRESOLVED
        assert "PRIMARY_ROUTE_NOT_CONFIRMED_ABSENT" in report["diagnostics"]


def test_410_is_valid_absence_signal_when_publisher_listing_is_current() -> None:
    route_report = _route_report()
    route_report["route_observations"][0]["http_status"] = 410  # type: ignore[index]
    report = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=_assertion())
    assert report["resolution_state"] == LIFECYCLE_RESOLVED


def test_publisher_listing_must_be_successfully_retrieved() -> None:
    route_report = _route_report()
    route_report["route_observations"][1] = {
        "route_id": "publisher-index",
        "outcome": "FAILURE",
        "failure_class": "HTTP_ERROR",
        "http_status": 503,
    }  # type: ignore[index]
    report = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=_assertion())
    assert report["resolution_state"] == LIFECYCLE_UNRESOLVED
    assert "PUBLISHER_LISTING_NOT_RETRIEVED" in report["diagnostics"]


def test_assertion_is_strict_and_source_bound() -> None:
    with pytest.raises(ValueError, match="unsupported lifecycle state"):
        evaluate_source_lifecycle(
            route_report=_route_report(),
            lifecycle_assertion={**_assertion(), "state": "ROLE_FILLED"},
        )
    with pytest.raises(ValueError, match="source_id does not match"):
        evaluate_source_lifecycle(
            route_report=_route_report(),
            lifecycle_assertion={**_assertion(), "source_id": "SRC-OTHER"},
        )
    with pytest.raises(ValueError, match="evidence_ref"):
        assertion = _assertion()
        assertion.pop("evidence_ref")
        evaluate_source_lifecycle(route_report=_route_report(), lifecycle_assertion=assertion)


def test_assertion_route_ids_must_be_registered_with_correct_classes() -> None:
    with pytest.raises(ValueError, match="primary_route_id is not registered"):
        evaluate_source_lifecycle(
            route_report=_route_report(),
            lifecycle_assertion={**_assertion(), "primary_route_id": "missing"},
        )
    with pytest.raises(ValueError, match="publisher_listing_route_id is not registered"):
        evaluate_source_lifecycle(
            route_report=_route_report(),
            lifecycle_assertion={**_assertion(), "publisher_listing_route_id": "missing"},
        )

    report = _route_report()
    report["route_policy"][0]["role"] = "FALLBACK"  # type: ignore[index]
    with pytest.raises(ValueError, match="registered PRIMARY"):
        evaluate_source_lifecycle(route_report=report, lifecycle_assertion=_assertion())

    report = _route_report()
    report["route_policy"][1]["route_class"] = "IDENTITY_EQUIVALENT"  # type: ignore[index]
    with pytest.raises(ValueError, match="LIVENESS_CORROBORATION"):
        evaluate_source_lifecycle(route_report=report, lifecycle_assertion=_assertion())


def test_duplicate_or_malformed_route_material_fails_closed() -> None:
    report = _route_report()
    report["route_policy"].append(copy.deepcopy(report["route_policy"][0]))  # type: ignore[union-attr,index]
    with pytest.raises(ValueError, match="duplicate route_policy route_id"):
        evaluate_source_lifecycle(route_report=report, lifecycle_assertion=_assertion())

    report = _route_report()
    report["route_observations"] = ["bad"]
    with pytest.raises(ValueError, match="route_observations item must be an object"):
        evaluate_source_lifecycle(route_report=report, lifecycle_assertion=_assertion())


def test_verifier_detects_tampering() -> None:
    route_report = _route_report()
    assertion = _assertion()
    report = evaluate_source_lifecycle(route_report=route_report, lifecycle_assertion=assertion)
    assert (
        verify_source_lifecycle_report(
            report,
            route_report=route_report,
            lifecycle_assertion=assertion,
        )["valid"]
        is True
    )

    tampered = copy.deepcopy(report)
    tampered["lifecycle_state"] = "RETIRED"
    verification = verify_source_lifecycle_report(
        tampered,
        route_report=route_report,
        lifecycle_assertion=assertion,
    )
    assert verification["valid"] is False
    assert verification["resolution_state"] == LIFECYCLE_RESOLVED
