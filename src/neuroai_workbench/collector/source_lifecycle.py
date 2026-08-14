from __future__ import annotations

from typing import Any

from ..util import canonical_json_bytes, sha256_bytes

NO_LONGER_LISTED = "NO_LONGER_LISTED"
LIFECYCLE_RESOLVED = "RESOLVED_LIFECYCLE_CHANGE"
LIFECYCLE_UNRESOLVED = "LIFECYCLE_UNRESOLVED"
_BOUNDARY = (
    "Lifecycle resolution records a narrow operational transition for a previously registered source. "
    "NO_LONGER_LISTED means only that the registered source endpoint is absent and a declared current official "
    "publisher listing no longer contains the exact source identity. It does not establish why the source disappeared, "
    "that a role was filled, that a programme ended, or any scientific, clinical, regulatory, governance, or release claim."
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _indexed(items: Any, *, key: str, field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError(f"{field} must be an array")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{field} item must be an object")
        item_key = _text(item.get(key), f"{field}.{key}")
        if item_key in result:
            raise ValueError(f"duplicate {field} {key} {item_key}")
        result[item_key] = item
    return result


def _validate_assertion(assertion: dict[str, Any]) -> dict[str, str]:
    if not isinstance(assertion, dict):
        raise ValueError("lifecycle_assertion must be an object")
    state = _text(assertion.get("state"), "lifecycle_assertion.state")
    if state != NO_LONGER_LISTED:
        raise ValueError(f"unsupported lifecycle state {state}")
    return {
        "state": state,
        "source_id": _text(assertion.get("source_id"), "lifecycle_assertion.source_id"),
        "primary_route_id": _text(assertion.get("primary_route_id"), "lifecycle_assertion.primary_route_id"),
        "publisher_listing_route_id": _text(
            assertion.get("publisher_listing_route_id"),
            "lifecycle_assertion.publisher_listing_route_id",
        ),
        "expected_identity": _text(assertion.get("expected_identity"), "lifecycle_assertion.expected_identity"),
        "evidence_ref": _text(assertion.get("evidence_ref"), "lifecycle_assertion.evidence_ref"),
        "basis": _text(assertion.get("basis"), "lifecycle_assertion.basis"),
        "asserted_at": _text(assertion.get("asserted_at"), "lifecycle_assertion.asserted_at"),
    }


def evaluate_source_lifecycle(
    *,
    route_report: dict[str, Any],
    lifecycle_assertion: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(route_report, dict):
        raise ValueError("route_report must be an object")
    assertion = _validate_assertion(lifecycle_assertion)
    source_id = _text(route_report.get("source_id"), "route_report.source_id")
    if source_id != assertion["source_id"]:
        raise ValueError("lifecycle assertion source_id does not match route report")

    route_policy = _indexed(route_report.get("route_policy"), key="route_id", field="route_policy")
    observations = _indexed(route_report.get("route_observations"), key="route_id", field="route_observations")
    primary_id = assertion["primary_route_id"]
    listing_id = assertion["publisher_listing_route_id"]
    if primary_id not in route_policy:
        raise ValueError("lifecycle primary_route_id is not registered")
    if listing_id not in route_policy:
        raise ValueError("lifecycle publisher_listing_route_id is not registered")
    if route_policy[primary_id].get("role") != "PRIMARY":
        raise ValueError("lifecycle primary_route_id must reference the registered PRIMARY route")
    if route_policy[listing_id].get("route_class") != "LIVENESS_CORROBORATION":
        raise ValueError("lifecycle publisher listing must use LIVENESS_CORROBORATION route class")

    reasons: list[str] = []
    if route_report.get("selected_route_id") is not None:
        reasons.append("SOURCE_STILL_RESOLVES_THROUGH_REGISTERED_ROUTE")
    primary = observations.get(primary_id)
    if primary is None:
        reasons.append("PRIMARY_ROUTE_NOT_OBSERVED")
    elif not (
        primary.get("outcome") == "FAILURE"
        and primary.get("failure_class") == "HTTP_ERROR"
        and primary.get("http_status") in {404, 410}
    ):
        reasons.append("PRIMARY_ROUTE_NOT_CONFIRMED_ABSENT")

    listing = observations.get(listing_id)
    if listing is None:
        reasons.append("PUBLISHER_LISTING_NOT_OBSERVED")
    elif listing.get("outcome") != "SUCCESS":
        reasons.append("PUBLISHER_LISTING_NOT_RETRIEVED")
    elif listing.get("corroboration_match") is not False:
        reasons.append("EXACT_IDENTITY_STILL_PRESENT_OR_NOT_CHECKED")

    resolved = not reasons
    semantic = {
        "schema_version": "1",
        "source_id": source_id,
        "resolution_state": LIFECYCLE_RESOLVED if resolved else LIFECYCLE_UNRESOLVED,
        "lifecycle_state": NO_LONGER_LISTED if resolved else None,
        "source_active_expected": False if resolved else None,
        "evidence_substitution_allowed": False,
        "assertion": assertion,
        "diagnostics": reasons,
        "route_report_sha256": route_report.get("report_sha256"),
        "boundary": _BOUNDARY,
    }
    result = dict(semantic)
    result["report_sha256"] = sha256_bytes(canonical_json_bytes(semantic))
    return result


def verify_source_lifecycle_report(
    report: dict[str, Any],
    *,
    route_report: dict[str, Any],
    lifecycle_assertion: dict[str, Any],
) -> dict[str, Any]:
    expected = evaluate_source_lifecycle(
        route_report=route_report,
        lifecycle_assertion=lifecycle_assertion,
    )
    errors: list[str] = []
    if report.get("report_sha256") != expected["report_sha256"]:
        errors.append("recorded lifecycle report hash mismatch")
    if canonical_json_bytes(report) != canonical_json_bytes(expected):
        errors.append("lifecycle report does not match recomputed inputs")
    return {
        "valid": not errors,
        "errors": errors,
        "resolution_state": expected["resolution_state"],
        "lifecycle_state": expected["lifecycle_state"],
        "report_sha256": expected["report_sha256"],
    }
