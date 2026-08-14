from __future__ import annotations

import copy

import pytest

from neuroai_workbench.collector.source_routes import (
    AVAILABLE_FALLBACK,
    AVAILABLE_PRIMARY,
    RETIRED,
    UNRESOLVED,
    evaluate_source_route_availability,
    parse_route_policy,
    route_failure_allows_failover,
    verify_source_route_report,
)


def _source() -> dict[str, object]:
    return {
        "source_id": "SRC-X",
        "url": "https://example.org/primary",
        "retrieval_routes": [
            {
                "route_id": "primary",
                "url": "https://example.org/primary",
                "priority": 0,
                "role": "PRIMARY",
                "route_class": "PRIMARY",
                "official_host": "example.org",
                "official_basis": "registered official publisher endpoint",
            },
            {
                "route_id": "identity-fallback",
                "url": "https://example.org/api?id=X",
                "priority": 1,
                "role": "FALLBACK",
                "route_class": "IDENTITY_EQUIVALENT",
                "official_host": "example.org",
                "official_basis": "official alternate representation",
                "identity_check": {"kind": "EXACT_ID", "expected": "X"},
            },
            {
                "route_id": "index-fallback",
                "url": "https://example.org/index",
                "priority": 2,
                "role": "FALLBACK",
                "route_class": "LIVENESS_CORROBORATION",
                "official_host": "example.org",
                "official_basis": "official publisher index",
                "corroboration_check": {"kind": "TEXT_CONTAINS", "expected": "Source X"},
            },
        ],
    }


def test_primary_success_is_available_primary() -> None:
    report = evaluate_source_route_availability(
        source_record=_source(),
        observations=[{"route_id": "primary", "outcome": "SUCCESS"}],
    )
    assert report["availability_state"] == AVAILABLE_PRIMARY
    assert report["primary_route_state"] == "AVAILABLE"
    assert report["selected_route_id"] == "primary"
    assert report["evidence_substitution_allowed"] is True
    assert report["route_failover_used"] is False


def test_403_can_fail_over_to_identity_equivalent_route() -> None:
    report = evaluate_source_route_availability(
        source_record=_source(),
        observations=[
            {
                "route_id": "primary",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 403,
            },
            {
                "route_id": "identity-fallback",
                "outcome": "SUCCESS",
                "identity_match": True,
            },
        ],
    )
    assert report["availability_state"] == AVAILABLE_FALLBACK
    assert report["selected_route_id"] == "identity-fallback"
    assert report["evidence_substitution_allowed"] is True
    assert report["route_failover_used"] is True


def test_404_can_fail_over_to_liveness_without_evidence_substitution() -> None:
    report = evaluate_source_route_availability(
        source_record=_source(),
        observations=[
            {
                "route_id": "primary",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 404,
            },
            {
                "route_id": "identity-fallback",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 404,
            },
            {
                "route_id": "index-fallback",
                "outcome": "SUCCESS",
                "corroboration_match": True,
            },
        ],
    )
    assert report["availability_state"] == AVAILABLE_FALLBACK
    assert report["selected_route_class"] == "LIVENESS_CORROBORATION"
    assert report["evidence_substitution_allowed"] is False


def test_policy_block_never_allows_fallback_bypass() -> None:
    report = evaluate_source_route_availability(
        source_record=_source(),
        observations=[
            {"route_id": "primary", "outcome": "FAILURE", "failure_class": "POLICY_BLOCK"},
            {"route_id": "identity-fallback", "outcome": "SUCCESS", "identity_match": True},
        ],
    )
    assert report["availability_state"] == UNRESOLVED
    assert report["selected_route_id"] is None


def test_identity_mismatch_rejects_successful_fallback() -> None:
    report = evaluate_source_route_availability(
        source_record=_source(),
        observations=[
            {
                "route_id": "primary",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 403,
            },
            {"route_id": "identity-fallback", "outcome": "SUCCESS", "identity_match": False},
        ],
    )
    assert report["availability_state"] == UNRESOLVED
    assert any(item.get("rejection") == "IDENTITY_MISMATCH" for item in report["diagnostics"])


def test_corroboration_mismatch_rejects_liveness_claim() -> None:
    report = evaluate_source_route_availability(
        source_record=_source(),
        observations=[
            {
                "route_id": "primary",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 404,
            },
            {
                "route_id": "identity-fallback",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 404,
            },
            {"route_id": "index-fallback", "outcome": "SUCCESS", "corroboration_match": False},
        ],
    )
    assert report["availability_state"] == UNRESOLVED
    assert any(item.get("rejection") == "CORROBORATION_MISMATCH" for item in report["diagnostics"])


def test_404_without_lifecycle_evidence_never_means_retired() -> None:
    report = evaluate_source_route_availability(
        source_record={"source_id": "SRC-X", "url": "https://example.org/gone"},
        observations=[
            {
                "route_id": "SRC-X:primary",
                "outcome": "FAILURE",
                "failure_class": "HTTP_ERROR",
                "http_status": 404,
            }
        ],
    )
    assert report["availability_state"] == UNRESOLVED


def test_explicit_retirement_requires_evidence_fields() -> None:
    source = {"source_id": "SRC-X", "url": "https://example.org/gone"}
    observation = [
        {
            "route_id": "SRC-X:primary",
            "outcome": "FAILURE",
            "failure_class": "HTTP_ERROR",
            "http_status": 410,
        }
    ]
    report = evaluate_source_route_availability(
        source_record=source,
        observations=observation,
        lifecycle_assertion={
            "state": "RETIRED",
            "evidence_ref": "publisher-ref:notice-1",
            "basis": "publisher explicitly retired this source",
            "asserted_at": "2026-08-14T00:00:00Z",
        },
    )
    assert report["availability_state"] == RETIRED
    assert report["evidence_substitution_allowed"] is False

    with pytest.raises(ValueError, match="evidence_ref"):
        evaluate_source_route_availability(
            source_record=source,
            observations=observation,
            lifecycle_assertion={"state": "RETIRED", "basis": "x", "asserted_at": "x"},
        )


def test_failover_failure_classifier_is_deliberately_narrow() -> None:
    assert route_failure_allows_failover({"outcome": "FAILURE", "failure_class": "TIMEOUT"}) is True
    assert route_failure_allows_failover({"outcome": "FAILURE", "failure_class": "NETWORK_ERROR"}) is True
    assert (
        route_failure_allows_failover({"outcome": "FAILURE", "failure_class": "HTTP_ERROR", "http_status": 503})
        is True
    )
    assert (
        route_failure_allows_failover({"outcome": "FAILURE", "failure_class": "HTTP_ERROR", "http_status": 401})
        is False
    )
    assert route_failure_allows_failover({"outcome": "FAILURE", "failure_class": "DNS_REBINDING"}) is False
    assert route_failure_allows_failover({"outcome": "SUCCESS"}) is False


def test_unobserved_preceding_route_prevents_silent_fallback() -> None:
    report = evaluate_source_route_availability(
        source_record=_source(),
        observations=[{"route_id": "identity-fallback", "outcome": "SUCCESS", "identity_match": True}],
    )
    assert report["availability_state"] == UNRESOLVED


def test_route_policy_validation_is_fail_closed() -> None:
    base = _source()

    bad = copy.deepcopy(base)
    bad["retrieval_routes"][1]["route_id"] = "primary"  # type: ignore[index]
    with pytest.raises(ValueError, match="duplicate route_id"):
        parse_route_policy(bad)

    bad = copy.deepcopy(base)
    bad["retrieval_routes"][1]["priority"] = 0  # type: ignore[index]
    with pytest.raises(ValueError, match="duplicate route priority"):
        parse_route_policy(bad)

    bad = copy.deepcopy(base)
    bad["retrieval_routes"][0]["official_host"] = "evil.example"  # type: ignore[index]
    with pytest.raises(ValueError, match="official_host"):
        parse_route_policy(bad)

    bad = copy.deepcopy(base)
    bad["retrieval_routes"][0]["url"] = "http://127.0.0.1/private"  # type: ignore[index]
    with pytest.raises(ValueError, match="URL policy"):
        parse_route_policy(bad)

    bad = copy.deepcopy(base)
    bad["retrieval_routes"][0]["route_class"] = "IDENTITY_EQUIVALENT"  # type: ignore[index]
    with pytest.raises(ValueError, match="primary route"):
        parse_route_policy(bad)

    bad = copy.deepcopy(base)
    bad["retrieval_routes"][1].pop("identity_check")  # type: ignore[index]
    with pytest.raises(ValueError, match="identity_check"):
        parse_route_policy(bad)

    bad = copy.deepcopy(base)
    bad["retrieval_routes"][2].pop("corroboration_check")  # type: ignore[index]
    with pytest.raises(ValueError, match="corroboration_check"):
        parse_route_policy(bad)


def test_policy_requires_exactly_one_lowest_priority_primary() -> None:
    bad = _source()
    bad["retrieval_routes"][1]["role"] = "PRIMARY"  # type: ignore[index]
    bad["retrieval_routes"][1]["route_class"] = "PRIMARY"  # type: ignore[index]
    with pytest.raises(ValueError, match="exactly one primary"):
        parse_route_policy(bad)

    bad = _source()
    bad["retrieval_routes"][0]["priority"] = 5  # type: ignore[index]
    with pytest.raises(ValueError, match="lowest priority"):
        parse_route_policy(bad)


def test_default_policy_synthesizes_registered_primary_route() -> None:
    specs = parse_route_policy({"source_id": "SRC-A", "url": "https://example.org/a"})
    assert len(specs) == 1
    assert specs[0].route_id == "SRC-A:primary"
    assert specs[0].route_class == "PRIMARY"


def test_observation_validation_rejects_unknown_duplicate_and_bad_outcomes() -> None:
    source = _source()
    with pytest.raises(ValueError, match="unknown route_id"):
        evaluate_source_route_availability(
            source_record=source,
            observations=[{"route_id": "unknown", "outcome": "SUCCESS"}],
        )
    with pytest.raises(ValueError, match="duplicate observation"):
        evaluate_source_route_availability(
            source_record=source,
            observations=[
                {"route_id": "primary", "outcome": "SUCCESS"},
                {"route_id": "primary", "outcome": "SUCCESS"},
            ],
        )
    with pytest.raises(ValueError, match="SUCCESS or FAILURE"):
        evaluate_source_route_availability(
            source_record=source,
            observations=[{"route_id": "primary", "outcome": "MAYBE"}],
        )


def test_verifier_detects_tampering_and_input_substitution() -> None:
    source = _source()
    observations = [
        {
            "route_id": "primary",
            "outcome": "FAILURE",
            "failure_class": "HTTP_ERROR",
            "http_status": 403,
        },
        {"route_id": "identity-fallback", "outcome": "SUCCESS", "identity_match": True},
    ]
    report = evaluate_source_route_availability(source_record=source, observations=observations)
    verification = verify_source_route_report(report, source_record=source, observations=observations)
    assert verification["valid"] is True

    tampered = copy.deepcopy(report)
    tampered["availability_state"] = "AVAILABLE_PRIMARY"
    verification = verify_source_route_report(tampered, source_record=source, observations=observations)
    assert verification["valid"] is False
    assert any("report does not match recomputed" in error for error in verification["errors"])

    substituted = copy.deepcopy(source)
    substituted["source_id"] = "SRC-Y"
    verification = verify_source_route_report(report, source_record=substituted, observations=observations)
    assert verification["valid"] is False


def test_lifecycle_assertion_rejects_nonretired_state_and_nonobject() -> None:
    source = {"source_id": "SRC-X", "url": "https://example.org/x"}
    with pytest.raises(ValueError, match="must be an object"):
        evaluate_source_route_availability(
            source_record=source,
            observations=[],
            lifecycle_assertion="RETIRED",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="must be RETIRED"):
        evaluate_source_route_availability(
            source_record=source,
            observations=[],
            lifecycle_assertion={"state": "ACTIVE"},
        )
