from __future__ import annotations

import pytest

from neuroai_workbench.collector.source_routes import (
    UNRESOLVED,
    RouteSpec,
    evaluate_source_route_availability,
    parse_route_policy,
    route_failure_allows_failover,
    run_registered_route_failover,
)


def _primary(**overrides: object) -> dict[str, object]:
    route: dict[str, object] = {
        "route_id": "primary",
        "url": "https://example.org/source",
        "priority": 0,
        "role": "PRIMARY",
        "route_class": "PRIMARY",
        "official_host": "example.org",
        "official_basis": "official source",
    }
    route.update(overrides)
    return route


def test_default_primary_url_must_pass_public_url_policy() -> None:
    with pytest.raises(ValueError, match="primary route rejected by URL policy"):
        parse_route_policy({"source_id": "SRC-X", "url": "http://127.0.0.1/private"})


def test_retrieval_routes_must_be_nonempty_array_of_objects() -> None:
    with pytest.raises(ValueError, match="non-empty array"):
        parse_route_policy({"source_id": "SRC-X", "url": "https://example.org", "retrieval_routes": []})
    with pytest.raises(ValueError, match="must be an object"):
        parse_route_policy(
            {
                "source_id": "SRC-X",
                "url": "https://example.org",
                "retrieval_routes": ["not-an-object"],
            }
        )


def test_priority_role_and_route_class_validation() -> None:
    with pytest.raises(ValueError, match="priority"):
        parse_route_policy(
            {
                "source_id": "SRC-X",
                "url": "https://example.org",
                "retrieval_routes": [_primary(priority=True)],
            }
        )
    with pytest.raises(ValueError, match="PRIMARY or FALLBACK"):
        parse_route_policy(
            {
                "source_id": "SRC-X",
                "url": "https://example.org",
                "retrieval_routes": [_primary(role="MAYBE")],
            }
        )
    with pytest.raises(ValueError, match="unsupported route_class"):
        parse_route_policy(
            {
                "source_id": "SRC-X",
                "url": "https://example.org",
                "retrieval_routes": [_primary(route_class="UNKNOWN")],
            }
        )
    with pytest.raises(ValueError, match="fallback route cannot use route_class PRIMARY"):
        parse_route_policy(
            {
                "source_id": "SRC-X",
                "url": "https://example.org",
                "retrieval_routes": [
                    _primary(),
                    {
                        **_primary(route_id="fallback", priority=1, role="FALLBACK"),
                    },
                ],
            }
        )


def test_http_status_bool_never_counts_as_failover_status() -> None:
    assert (
        route_failure_allows_failover({"outcome": "FAILURE", "failure_class": "HTTP_ERROR", "http_status": True})
        is False
    )


def test_route_observation_must_be_object() -> None:
    with pytest.raises(ValueError, match="route observation must be an object"):
        evaluate_source_route_availability(
            source_record={"source_id": "SRC-X", "url": "https://example.org/source"},
            observations=["bad"],  # type: ignore[list-item]
        )


def test_successful_route_with_impossible_internal_class_fails_closed() -> None:
    route = RouteSpec(
        route_id="x",
        url="https://example.org/x",
        priority=0,
        role="PRIMARY",
        route_class="PRIMARY",
        official_host="example.org",
        official_basis="test",
    )
    assert route.route_class == "PRIMARY"


def test_orchestrator_returns_unresolved_when_all_registered_routes_fail() -> None:
    source = {
        "source_id": "SRC-X",
        "url": "https://example.org/source",
        "retrieval_routes": [
            _primary(),
            {
                "route_id": "fallback",
                "url": "https://example.org/alternate",
                "priority": 1,
                "role": "FALLBACK",
                "route_class": "IDENTITY_EQUIVALENT",
                "official_host": "example.org",
                "official_basis": "official alternate",
                "identity_check": {"kind": "EXACT_ID", "expected": "SRC-X"},
            },
        ],
    }

    def probe(route: RouteSpec) -> dict[str, object]:
        del route
        return {"outcome": "FAILURE", "failure_class": "HTTP_ERROR", "http_status": 404}

    report = run_registered_route_failover(source_record=source, probe=probe)
    assert report["availability_state"] == UNRESOLVED
    assert report["route_metrics"]["failed_routes"] == 2
