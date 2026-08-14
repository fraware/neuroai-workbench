from __future__ import annotations

import pytest

from neuroai_workbench.collector.source_routes import (
    AVAILABLE_FALLBACK,
    AVAILABLE_PRIMARY,
    UNRESOLVED,
    RouteSpec,
    run_registered_route_failover,
)


def _source() -> dict[str, object]:
    return {
        "source_id": "SRC-ROUTE",
        "url": "https://example.org/primary",
        "retrieval_routes": [
            {
                "route_id": "primary",
                "url": "https://example.org/primary",
                "priority": 0,
                "role": "PRIMARY",
                "route_class": "PRIMARY",
                "official_host": "example.org",
                "official_basis": "official primary",
            },
            {
                "route_id": "api-fallback",
                "url": "https://example.org/api/route",
                "priority": 1,
                "role": "FALLBACK",
                "route_class": "IDENTITY_EQUIVALENT",
                "official_host": "example.org",
                "official_basis": "official structured alternate",
                "identity_check": {"kind": "EXACT_ID", "expected": "SRC-ROUTE"},
            },
        ],
    }


def test_orchestrator_stops_after_primary_success() -> None:
    called: list[str] = []

    def probe(route: RouteSpec) -> dict[str, object]:
        called.append(route.route_id)
        return {"outcome": "SUCCESS"}

    report = run_registered_route_failover(source_record=_source(), probe=probe)
    assert report["availability_state"] == AVAILABLE_PRIMARY
    assert called == ["primary"]
    assert report["route_metrics"] == {
        "registered_routes": 2,
        "observed_routes": 1,
        "failed_routes": 0,
        "fallback_routes_observed": 0,
    }


def test_orchestrator_uses_registered_fallback_after_403() -> None:
    called: list[str] = []

    def probe(route: RouteSpec) -> dict[str, object]:
        called.append(route.route_id)
        if route.role == "PRIMARY":
            return {"outcome": "FAILURE", "failure_class": "HTTP_ERROR", "http_status": 403}
        return {"outcome": "SUCCESS", "identity_match": True}

    report = run_registered_route_failover(source_record=_source(), probe=probe)
    assert report["availability_state"] == AVAILABLE_FALLBACK
    assert report["evidence_substitution_allowed"] is True
    assert called == ["primary", "api-fallback"]
    assert report["route_metrics"]["failed_routes"] == 1
    assert report["route_metrics"]["fallback_routes_observed"] == 1


def test_orchestrator_stops_on_nonfailoverable_security_or_policy_failure() -> None:
    called: list[str] = []

    def probe(route: RouteSpec) -> dict[str, object]:
        called.append(route.route_id)
        return {"outcome": "FAILURE", "failure_class": "POLICY_BLOCK"}

    report = run_registered_route_failover(source_record=_source(), probe=probe)
    assert report["availability_state"] == UNRESOLVED
    assert called == ["primary"]


def test_orchestrator_stops_on_identity_mismatch() -> None:
    called: list[str] = []

    def probe(route: RouteSpec) -> dict[str, object]:
        called.append(route.route_id)
        if route.role == "PRIMARY":
            return {"outcome": "FAILURE", "failure_class": "NETWORK_ERROR"}
        return {"outcome": "SUCCESS", "identity_match": False}

    report = run_registered_route_failover(source_record=_source(), probe=probe)
    assert report["availability_state"] == UNRESOLVED
    assert called == ["primary", "api-fallback"]


def test_orchestrator_requires_probe_object() -> None:
    def probe(route: RouteSpec) -> dict[str, object]:
        del route
        return "bad"  # type: ignore[return-value]

    with pytest.raises(ValueError, match="route probe must return"):
        run_registered_route_failover(source_record=_source(), probe=probe)
