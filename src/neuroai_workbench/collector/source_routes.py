from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ..util import canonical_json_bytes, sha256_bytes
from .url_policy import public_url_error

PRIMARY = "PRIMARY"
IDENTITY_EQUIVALENT = "IDENTITY_EQUIVALENT"
LIVENESS_CORROBORATION = "LIVENESS_CORROBORATION"
AVAILABLE_PRIMARY = "AVAILABLE_PRIMARY"
AVAILABLE_FALLBACK = "AVAILABLE_FALLBACK"
UNRESOLVED = "UNRESOLVED"
RETIRED = "RETIRED"

_ROUTE_CLASSES = frozenset({PRIMARY, IDENTITY_EQUIVALENT, LIVENESS_CORROBORATION})
_ROUTE_ROLES = frozenset({"PRIMARY", "FALLBACK"})
_FAILOVER_FAILURE_CLASSES = frozenset({"TIMEOUT", "NETWORK_ERROR"})
_FAILOVER_HTTP_STATUSES = frozenset({403, 404, 408, 410, 425, 429, 500, 502, 503, 504})
_BOUNDARY = (
    "Source-route resilience evaluates operational availability of a registered source identity. "
    "A fallback route never changes source truth, assessment meaning, clinical/regulatory status, "
    "governance authority, or release authority. Liveness corroboration is not evidence substitution."
)


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    url: str
    priority: int
    role: str
    route_class: str
    official_host: str
    official_basis: str
    identity_check: dict[str, str] | None = None
    corroboration_check: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "route_id": self.route_id,
            "url": self.url,
            "priority": self.priority,
            "role": self.role,
            "route_class": self.route_class,
            "official_host": self.official_host,
            "official_basis": self.official_basis,
        }
        if self.identity_check is not None:
            value["identity_check"] = dict(self.identity_check)
        if self.corroboration_check is not None:
            value["corroboration_check"] = dict(self.corroboration_check)
        return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _host(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.hostname or "").lower()


def _check_map(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    kind = _text(value.get("kind"), f"{field}.kind")
    expected = _text(value.get("expected"), f"{field}.expected")
    return {"kind": kind, "expected": expected}


def parse_route_policy(source_record: dict[str, Any]) -> list[RouteSpec]:
    source_id = _text(source_record.get("source_id"), "source_id")
    raw_routes = source_record.get("retrieval_routes")
    if raw_routes is None:
        url = _text(source_record.get("url"), f"{source_id}.url")
        error = public_url_error(url)
        if error is not None:
            raise ValueError(f"{source_id} primary route rejected by URL policy: {error}")
        host = _host(url)
        return [
            RouteSpec(
                route_id=f"{source_id}:primary",
                url=url,
                priority=0,
                role="PRIMARY",
                route_class=PRIMARY,
                official_host=host,
                official_basis="registered source URL",
            )
        ]
    if not isinstance(raw_routes, list) or not raw_routes:
        raise ValueError(f"{source_id}.retrieval_routes must be a non-empty array")

    specs: list[RouteSpec] = []
    route_ids: set[str] = set()
    priorities: set[int] = set()
    primary_count = 0
    for index, raw in enumerate(raw_routes):
        if not isinstance(raw, dict):
            raise ValueError(f"{source_id}.retrieval_routes[{index}] must be an object")
        route_id = _text(raw.get("route_id"), "route_id")
        if route_id in route_ids:
            raise ValueError(f"duplicate route_id {route_id}")
        route_ids.add(route_id)
        priority = raw.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:
            raise ValueError(f"{route_id}.priority must be an integer >= 0")
        if priority in priorities:
            raise ValueError(f"duplicate route priority {priority}")
        priorities.add(priority)
        role = _text(raw.get("role"), f"{route_id}.role")
        if role not in _ROUTE_ROLES:
            raise ValueError(f"{route_id}.role must be PRIMARY or FALLBACK")
        route_class = _text(raw.get("route_class"), f"{route_id}.route_class")
        if route_class not in _ROUTE_CLASSES:
            raise ValueError(f"{route_id} has unsupported route_class {route_class}")
        if role == "PRIMARY":
            primary_count += 1
            if route_class != PRIMARY:
                raise ValueError(f"{route_id} primary route must use route_class PRIMARY")
        elif route_class == PRIMARY:
            raise ValueError(f"{route_id} fallback route cannot use route_class PRIMARY")
        url = _text(raw.get("url"), f"{route_id}.url")
        error = public_url_error(url)
        if error is not None:
            raise ValueError(f"{route_id} rejected by URL policy: {error}")
        official_host = _text(raw.get("official_host"), f"{route_id}.official_host").lower()
        if _host(url) != official_host:
            raise ValueError(f"{route_id} URL host does not match declared official_host")
        official_basis = _text(raw.get("official_basis"), f"{route_id}.official_basis")

        identity_check = None
        corroboration_check = None
        if route_class in {PRIMARY, IDENTITY_EQUIVALENT} and raw.get("identity_check") is not None:
            identity_check = _check_map(raw.get("identity_check"), f"{route_id}.identity_check")
        if route_class == IDENTITY_EQUIVALENT and identity_check is None:
            raise ValueError(f"{route_id}.identity_check must be an object")
        if route_class == LIVENESS_CORROBORATION:
            corroboration_check = _check_map(raw.get("corroboration_check"), f"{route_id}.corroboration_check")

        specs.append(
            RouteSpec(
                route_id=route_id,
                url=url,
                priority=priority,
                role=role,
                route_class=route_class,
                official_host=official_host,
                official_basis=official_basis,
                identity_check=identity_check,
                corroboration_check=corroboration_check,
            )
        )

    if primary_count != 1:
        raise ValueError(f"{source_id} route policy requires exactly one primary route")
    specs.sort(key=lambda item: (item.priority, item.route_id))
    if specs[0].role != "PRIMARY":
        raise ValueError(f"{source_id} primary route must have the lowest priority")
    return specs


def route_failure_allows_failover(observation: dict[str, Any]) -> bool:
    if observation.get("outcome") != "FAILURE":
        return False
    failure_class = str(observation.get("failure_class") or "")
    if failure_class in _FAILOVER_FAILURE_CLASSES:
        return True
    if failure_class != "HTTP_ERROR":
        return False
    status = observation.get("http_status")
    return isinstance(status, int) and not isinstance(status, bool) and status in _FAILOVER_HTTP_STATUSES


def _successful_route_usable(spec: RouteSpec, observation: dict[str, Any]) -> tuple[bool, str | None]:
    if observation.get("outcome") != "SUCCESS":
        return False, None
    if spec.route_class == PRIMARY:
        if spec.identity_check is not None and observation.get("identity_match") is not True:
            return False, "IDENTITY_MISMATCH"
        return True, None
    if spec.route_class == IDENTITY_EQUIVALENT:
        if observation.get("identity_match") is True:
            return True, None
        return False, "IDENTITY_MISMATCH"
    if observation.get("corroboration_match") is True:
        return True, None
    return False, "CORROBORATION_MISMATCH"


def _validate_retirement(assertion: dict[str, Any] | None) -> dict[str, str] | None:
    if assertion is None:
        return None
    if not isinstance(assertion, dict):
        raise ValueError("lifecycle_assertion must be an object")
    if assertion.get("state") != RETIRED:
        raise ValueError("lifecycle_assertion.state must be RETIRED")
    return {
        "state": RETIRED,
        "evidence_ref": _text(assertion.get("evidence_ref"), "lifecycle_assertion.evidence_ref"),
        "basis": _text(assertion.get("basis"), "lifecycle_assertion.basis"),
        "asserted_at": _text(assertion.get("asserted_at"), "lifecycle_assertion.asserted_at"),
    }


def evaluate_source_route_availability(
    *,
    source_record: dict[str, Any],
    observations: list[dict[str, Any]],
    lifecycle_assertion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    specs = parse_route_policy(source_record)
    by_id = {spec.route_id: spec for spec in specs}
    seen: set[str] = set()
    normalized_observations: dict[str, dict[str, Any]] = {}
    for raw in observations:
        if not isinstance(raw, dict):
            raise ValueError("route observation must be an object")
        route_id = _text(raw.get("route_id"), "observation.route_id")
        if route_id not in by_id:
            raise ValueError(f"observation references unknown route_id {route_id}")
        if route_id in seen:
            raise ValueError(f"duplicate observation for route_id {route_id}")
        seen.add(route_id)
        outcome = _text(raw.get("outcome"), f"{route_id}.outcome")
        if outcome not in {"SUCCESS", "FAILURE"}:
            raise ValueError(f"{route_id}.outcome must be SUCCESS or FAILURE")
        item = dict(raw)
        item["route_id"] = route_id
        item["outcome"] = outcome
        normalized_observations[route_id] = item

    selected: RouteSpec | None = None
    selected_observation: dict[str, Any] | None = None
    diagnostics: list[dict[str, Any]] = []
    prior_failover_allowed = True
    primary_route_state = "NOT_OBSERVED"

    for spec in specs:
        observation = normalized_observations.get(spec.route_id)
        if observation is None:
            diagnostics.append({"route_id": spec.route_id, "state": "NOT_OBSERVED"})
            if spec.role == "PRIMARY":
                primary_route_state = "NOT_OBSERVED"
            prior_failover_allowed = False
            continue
        if observation["outcome"] == "FAILURE":
            failover_allowed = route_failure_allows_failover(observation)
            diagnostics.append(
                {
                    "route_id": spec.route_id,
                    "state": "FAILURE",
                    "failure_class": observation.get("failure_class"),
                    "http_status": observation.get("http_status"),
                    "failover_allowed": failover_allowed,
                }
            )
            if spec.role == "PRIMARY":
                primary_route_state = "DEGRADED"
            prior_failover_allowed = prior_failover_allowed and failover_allowed
            continue

        usable, rejection = _successful_route_usable(spec, observation)
        diagnostics.append(
            {
                "route_id": spec.route_id,
                "state": "SUCCESS" if usable else "SUCCESS_REJECTED",
                "rejection": rejection,
            }
        )
        if spec.role == "PRIMARY":
            primary_route_state = "AVAILABLE" if usable else "DEGRADED"
        if usable and (spec.role == "PRIMARY" or prior_failover_allowed):
            selected = spec
            selected_observation = observation
            break
        if not usable:
            prior_failover_allowed = False

    retirement = _validate_retirement(lifecycle_assertion)
    source_id = _text(source_record.get("source_id"), "source_id")
    if selected is not None:
        availability_state = AVAILABLE_PRIMARY if selected.role == "PRIMARY" else AVAILABLE_FALLBACK
        evidence_substitution_allowed = selected.route_class in {PRIMARY, IDENTITY_EQUIVALENT}
    elif retirement is not None:
        availability_state = RETIRED
        evidence_substitution_allowed = False
    else:
        availability_state = UNRESOLVED
        evidence_substitution_allowed = False

    observed_specs = [spec for spec in specs if spec.route_id in normalized_observations]
    semantic = {
        "schema_version": "1",
        "source_id": source_id,
        "availability_state": availability_state,
        "primary_route_state": primary_route_state,
        "selected_route_id": selected.route_id if selected is not None else None,
        "selected_route_class": selected.route_class if selected is not None else None,
        "evidence_substitution_allowed": evidence_substitution_allowed,
        "route_failover_used": selected is not None and selected.role == "FALLBACK",
        "route_metrics": {
            "registered_routes": len(specs),
            "observed_routes": len(observed_specs),
            "failed_routes": sum(
                1 for item in normalized_observations.values() if item.get("outcome") == "FAILURE"
            ),
            "fallback_routes_observed": sum(1 for spec in observed_specs if spec.role == "FALLBACK"),
        },
        "route_policy": [spec.as_dict() for spec in specs],
        "route_observations": [normalized_observations[key] for key in sorted(normalized_observations)],
        "diagnostics": diagnostics,
        "lifecycle_assertion": retirement,
        "boundary": _BOUNDARY,
    }
    if selected_observation is not None:
        semantic["selected_observation"] = selected_observation
    report = dict(semantic)
    report["report_sha256"] = sha256_bytes(canonical_json_bytes(semantic))
    return report


def run_registered_route_failover(
    *,
    source_record: dict[str, Any],
    probe: Callable[[RouteSpec], dict[str, Any]],
    lifecycle_assertion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for spec in parse_route_policy(source_record):
        raw = probe(spec)
        if not isinstance(raw, dict):
            raise ValueError("route probe must return an observation object")
        observation = {**raw, "route_id": spec.route_id}
        observations.append(observation)
        report = evaluate_source_route_availability(
            source_record=source_record,
            observations=observations,
            lifecycle_assertion=lifecycle_assertion,
        )
        if report["availability_state"] in {AVAILABLE_PRIMARY, AVAILABLE_FALLBACK, RETIRED}:
            return report
        if observation.get("outcome") == "FAILURE" and route_failure_allows_failover(observation):
            continue
        return report
    return evaluate_source_route_availability(
        source_record=source_record,
        observations=observations,
        lifecycle_assertion=lifecycle_assertion,
    )


def verify_source_route_report(
    report: dict[str, Any],
    *,
    source_record: dict[str, Any],
    observations: list[dict[str, Any]],
    lifecycle_assertion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected = evaluate_source_route_availability(
        source_record=source_record,
        observations=observations,
        lifecycle_assertion=lifecycle_assertion,
    )
    errors: list[str] = []
    if report.get("report_sha256") != expected.get("report_sha256"):
        errors.append("recorded report hash mismatch")
    if canonical_json_bytes(report) != canonical_json_bytes(expected):
        errors.append("report does not match recomputed source-route availability")
    return {
        "valid": not errors,
        "errors": errors,
        "availability_state": expected["availability_state"],
        "report_sha256": expected["report_sha256"],
    }
