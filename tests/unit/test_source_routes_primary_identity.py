from __future__ import annotations

from neuroai_workbench.collector.source_routes import AVAILABLE_PRIMARY, UNRESOLVED, evaluate_source_route_availability


def _source() -> dict[str, object]:
    return {
        "source_id": "SRC-ID",
        "url": "https://example.org/item",
        "retrieval_routes": [
            {
                "route_id": "primary",
                "url": "https://example.org/item",
                "priority": 0,
                "role": "PRIMARY",
                "route_class": "PRIMARY",
                "official_host": "example.org",
                "official_basis": "official record",
                "identity_check": {"kind": "EXACT_ID", "expected": "SRC-ID"},
            }
        ],
    }


def test_primary_identity_check_must_pass_when_declared() -> None:
    failed = evaluate_source_route_availability(
        source_record=_source(),
        observations=[{"route_id": "primary", "outcome": "SUCCESS", "identity_match": False}],
    )
    assert failed["availability_state"] == UNRESOLVED
    assert failed["primary_route_state"] == "DEGRADED"
    assert failed["diagnostics"][0]["rejection"] == "IDENTITY_MISMATCH"

    passed = evaluate_source_route_availability(
        source_record=_source(),
        observations=[{"route_id": "primary", "outcome": "SUCCESS", "identity_match": True}],
    )
    assert passed["availability_state"] == AVAILABLE_PRIMARY
    assert passed["route_policy"][0]["identity_check"] == {"kind": "EXACT_ID", "expected": "SRC-ID"}
