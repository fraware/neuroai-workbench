"""Fail-closed mechanical lineage validators for observatory v1.6 / v1.7 packages.

These checks encode arithmetic and identity integrity only. Passing does not
establish scientific truth, regulatory authorization, clinical effectiveness,
or assessment correctness.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

from .util import canonical_json_bytes

OBSERVATORY_RESOURCE_PACKAGE = "neuroai_workbench.resources.observatory"
REFRESH_SCHEMA = "OBSERVATORY_V1_6_REFRESH.schema.json"
DELTA_SCHEMA = "OBSERVATORY_V1_6_ADJUDICATED_DELTA.schema.json"

DELTA_SECTIONS = (
    "regulatory_and_market_events",
    "capital_and_ownership_events",
    "model_records",
    "supplier_dependency_relationships",
    "governance_and_leadership_events",
)

ACCEPTED_ADJUDICATION_PREFIX = "ACCEPT"

PackageKind = Literal["OBSERVATORY_V1_6_REFRESH", "OBSERVATORY_V1_6_ADJUDICATED_DELTA", "UNKNOWN"]


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(OBSERVATORY_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any, schema_name: str) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_schema(schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def detect_v16_package_kind(value: Any) -> PackageKind:
    if not isinstance(value, dict):
        return "UNKNOWN"
    if "new_sources" in value and "change_candidates" in value and "adjudicated_delta" in value:
        return "OBSERVATORY_V1_6_REFRESH"
    if all(key in value for key in DELTA_SECTIONS) and "new_sources" not in value:
        return "OBSERVATORY_V1_6_ADJUDICATED_DELTA"
    return "UNKNOWN"


def validate_v16_package(value: Any) -> dict[str, Any]:
    """Validate a single v1.6 package shape (refresh or adjudicated delta)."""
    kind = detect_v16_package_kind(value)
    if kind == "UNKNOWN":
        return {
            "valid": False,
            "release_kind": "UNKNOWN",
            "errors": [{"code": "UNKNOWN_V16_PACKAGE", "message": "Value is not a recognized v1.6 package"}],
        }
    schema_name = REFRESH_SCHEMA if kind == "OBSERVATORY_V1_6_REFRESH" else DELTA_SCHEMA
    errors = _schema_errors(value, schema_name)
    if kind == "OBSERVATORY_V1_6_REFRESH":
        errors.extend(_refresh_local_errors(cast(dict[str, Any], value)))
    else:
        errors.extend(_delta_local_errors(cast(dict[str, Any], value)))
    return {"valid": not errors, "release_kind": kind, "errors": errors, "issue_count": len(errors)}


def _refresh_local_errors(refresh: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    new_sources = refresh.get("new_sources")
    if not isinstance(new_sources, list):
        return [{"code": "NEW_SOURCES_REQUIRED", "message": "new_sources must be an array"}]
    ids = [str(item.get("source_id")) for item in new_sources if isinstance(item, dict)]
    if not ids:
        errors.append({"code": "NEW_SOURCE_COUNT", "message": "new_sources must be non-empty"})
    if len(ids) != len(set(ids)):
        errors.append({"code": "DUPLICATE_NEW_SOURCE_ID", "message": "new_sources contains duplicate source_id values"})

    candidates = refresh.get("change_candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append({"code": "CANDIDATE_COUNT", "message": "change_candidates must be a non-empty array"})
    nested = refresh.get("adjudicated_delta")
    if isinstance(nested, dict):
        errors.extend(_delta_local_errors(nested))
    else:
        errors.append({"code": "ADJUDICATED_DELTA_REQUIRED", "message": "adjudicated_delta object is required"})
    return errors


def _delta_local_errors(delta: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for section in DELTA_SECTIONS:
        value = delta.get(section)
        if not isinstance(value, list):
            errors.append({"code": "DELTA_SECTION_TYPE", "path": section, "message": f"{section} must be an array"})
    return errors


def _collect_delta_source_ids(delta: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for section in DELTA_SECTIONS:
        rows = delta.get(section)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for source_id in row.get("source_ids") or []:
                if isinstance(source_id, str):
                    found.add(source_id)
    return found


def _event_ids(delta: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for section in DELTA_SECTIONS:
        rows = delta.get(section)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ("event_id", "model_id", "dependency_id", "governance_id"):
                value = row.get(key)
                if isinstance(value, str):
                    ids.add(value)
    return ids


def validate_v16_v17_lineage(
    *,
    refresh: dict[str, Any],
    delta: dict[str, Any],
    v17: dict[str, Any],
    v14_source_ids: set[str],
    expected_new_sources: int = 12,
    expected_candidates: int = 9,
    expected_final_sources: int = 248,
    expected_baseline_sources: int = 224,
    expected_assessment_adds: int = 12,
) -> dict[str, Any]:
    """Cross-package arithmetic and identity checks for governing lineage."""
    errors: list[dict[str, Any]] = []

    refresh_report = validate_v16_package(refresh)
    if refresh_report["release_kind"] != "OBSERVATORY_V1_6_REFRESH" or not refresh_report["valid"]:
        errors.extend(
            refresh_report.get("errors") or [{"code": "REFRESH_INVALID", "message": "refresh package invalid"}]
        )

    delta_report = validate_v16_package(delta)
    if delta_report["release_kind"] != "OBSERVATORY_V1_6_ADJUDICATED_DELTA" or not delta_report["valid"]:
        errors.extend(delta_report.get("errors") or [{"code": "DELTA_INVALID", "message": "delta package invalid"}])

    new_sources = [item for item in refresh.get("new_sources", []) if isinstance(item, dict)]
    new_ids = [str(item["source_id"]) for item in new_sources if item.get("source_id")]
    if len(new_ids) != expected_new_sources:
        errors.append(
            {
                "code": "NEW_SOURCE_COUNT",
                "message": f"Expected {expected_new_sources} new sources, found {len(new_ids)}",
            }
        )
    overlap = sorted(set(new_ids) & set(v14_source_ids))
    if overlap:
        errors.append(
            {
                "code": "NEW_SOURCE_OVERLAP_V14",
                "message": "new_sources overlap v1.4 baseline IDs",
                "identifiers": overlap,
            }
        )

    candidates = [item for item in refresh.get("change_candidates", []) if isinstance(item, dict)]
    if len(candidates) != expected_candidates:
        errors.append(
            {
                "code": "CANDIDATE_COUNT",
                "message": f"Expected {expected_candidates} change_candidates, found {len(candidates)}",
            }
        )

    known_sources = set(v14_source_ids) | set(new_ids)
    for index, candidate in enumerate(candidates):
        adjudication = str(candidate.get("adjudication") or "")
        if not adjudication.startswith(ACCEPTED_ADJUDICATION_PREFIX):
            errors.append(
                {
                    "code": "CANDIDATE_NOT_ACCEPTED",
                    "path": f"change_candidates[{index}]",
                    "message": f"Candidate adjudication is not ACCEPT*: {adjudication!r}",
                }
            )
        for source_id in candidate.get("source_ids") or []:
            if source_id not in known_sources:
                errors.append(
                    {
                        "code": "UNRESOLVED_SOURCE_REF",
                        "path": f"change_candidates[{index}].source_ids",
                        "value": source_id,
                        "message": "Candidate source_id does not resolve to v1.4 or v1.6 new_sources",
                    }
                )

    nested_delta = refresh.get("adjudicated_delta")
    if not isinstance(nested_delta, dict):
        errors.append({"code": "NESTED_DELTA_MISSING", "message": "refresh.adjudicated_delta must be an object"})
        nested_delta = {}

    if canonical_json_bytes(nested_delta) != canonical_json_bytes(delta):
        errors.append(
            {
                "code": "REFRESH_DELTA_MISMATCH",
                "message": "refresh.adjudicated_delta is not byte-equal to standalone adjudicated delta",
            }
        )

    v17_delta = v17.get("delta")
    if not isinstance(v17_delta, dict) or canonical_json_bytes(v17_delta) != canonical_json_bytes(delta):
        errors.append(
            {
                "code": "V17_DELTA_MISMATCH",
                "message": "v1.7 delta records are not equal to v1.6 adjudicated delta",
            }
        )

    delta_counts = v17.get("delta_counts")
    if not isinstance(delta_counts, dict):
        errors.append({"code": "DELTA_COUNTS_MISSING", "message": "v1.7 delta_counts object is required"})
    else:
        for section in DELTA_SECTIONS:
            expected = len(delta.get(section) or [])
            observed = delta_counts.get(section)
            if observed != expected:
                errors.append(
                    {
                        "code": "DELTA_COUNT_MISMATCH",
                        "path": f"delta_counts.{section}",
                        "message": f"Expected {expected}, found {observed}",
                    }
                )
        if delta_counts.get("new_sources") != expected_new_sources:
            errors.append(
                {
                    "code": "DELTA_COUNT_NEW_SOURCES",
                    "message": f"delta_counts.new_sources must equal {expected_new_sources}",
                }
            )
        if delta_counts.get("change_candidates") != expected_candidates:
            errors.append(
                {
                    "code": "DELTA_COUNT_CANDIDATES",
                    "message": f"delta_counts.change_candidates must equal {expected_candidates}",
                }
            )
        reopenings = refresh.get("reopening_decisions")
        if isinstance(reopenings, list) and delta_counts.get("reopening_decisions") != len(reopenings):
            errors.append(
                {
                    "code": "DELTA_COUNT_REOPENING",
                    "message": "delta_counts.reopening_decisions must match refresh reopening_decisions length",
                }
            )

    for source_id in _collect_delta_source_ids(delta):
        if source_id not in known_sources:
            errors.append(
                {
                    "code": "UNRESOLVED_DELTA_SOURCE",
                    "value": source_id,
                    "message": "Delta source_id does not resolve to v1.4 or v1.6 new_sources",
                }
            )

    for check in refresh.get("source_checks") or []:
        if not isinstance(check, dict):
            continue
        source_id = check.get("source_id")
        if isinstance(source_id, str) and source_id not in known_sources:
            errors.append(
                {
                    "code": "UNRESOLVED_SOURCE_CHECK",
                    "value": source_id,
                    "message": "source_checks.source_id does not resolve",
                }
            )

    event_ids = _event_ids(delta)
    for index, decision in enumerate(refresh.get("reopening_decisions") or []):
        if not isinstance(decision, dict):
            continue
        if not decision.get("decision_id") or not decision.get("decision"):
            errors.append(
                {
                    "code": "REOPENING_INCOMPLETE",
                    "path": f"reopening_decisions[{index}]",
                    "message": "Reopening decision missing decision_id or decision",
                }
            )
        for basis_id in decision.get("basis") or []:
            if isinstance(basis_id, str) and basis_id not in event_ids and basis_id not in known_sources:
                # Basis may reference event ids or descriptive objects; only flag opaque REG-/event-like IDs.
                if basis_id.startswith(("REG-", "CAP-", "MOD-", "SUP-", "GOV-", "SRC-")):
                    errors.append(
                        {
                            "code": "REOPENING_BASIS_UNRESOLVED",
                            "path": f"reopening_decisions[{index}].basis",
                            "value": basis_id,
                            "message": "Reopening basis identifier does not resolve to delta event or source",
                        }
                    )

    baseline_raw = v17.get("baseline_counts")
    baseline_counts: dict[str, Any] = baseline_raw if isinstance(baseline_raw, dict) else {}
    effective_raw = v17.get("successor_effective_counts")
    effective: dict[str, Any] = effective_raw if isinstance(effective_raw, dict) else {}
    assessment_block = v17.get("assessment_successor_delta")
    if isinstance(assessment_block, dict):
        source_delta = assessment_block.get("source_delta")
        assessment: dict[str, Any] = source_delta if isinstance(source_delta, dict) else {}
    else:
        assessment = {}

    baseline_sources = baseline_counts.get("source_records")
    if baseline_sources != expected_baseline_sources:
        errors.append(
            {
                "code": "BASELINE_SOURCE_COUNT",
                "message": f"baseline_counts.source_records expected {expected_baseline_sources}, found {baseline_sources}",
            }
        )
    assessment_adds = assessment.get("new_unique_source_records_relative_to_v1_6")
    if assessment_adds != expected_assessment_adds:
        errors.append(
            {
                "code": "ASSESSMENT_SOURCE_ADD_COUNT",
                "message": (
                    f"assessment new_unique_source_records_relative_to_v1_6 expected "
                    f"{expected_assessment_adds}, found {assessment_adds}"
                ),
            }
        )
    final_sources = effective.get("source_records")
    if final_sources != expected_final_sources:
        errors.append(
            {
                "code": "FINAL_SOURCE_COUNT",
                "message": f"successor_effective_counts.source_records expected {expected_final_sources}, found {final_sources}",
            }
        )
    if (
        isinstance(baseline_sources, int)
        and isinstance(assessment_adds, int)
        and isinstance(final_sources, int)
        and baseline_sources + expected_new_sources + assessment_adds != final_sources
    ):
        errors.append(
            {
                "code": "SOURCE_PROGRESSION_ARITHMETIC",
                "message": (
                    f"Expected {baseline_sources}+{expected_new_sources}+{assessment_adds}="
                    f"{baseline_sources + expected_new_sources + assessment_adds}, found {final_sources}"
                ),
            }
        )

    # Effective-count arithmetic for capital / models / suppliers.
    if isinstance(baseline_counts.get("capital_and_ownership_events"), int) and isinstance(
        effective.get("capital_and_ownership_events"), int
    ):
        expected_capital = baseline_counts["capital_and_ownership_events"] + len(
            delta.get("capital_and_ownership_events") or []
        )
        if effective["capital_and_ownership_events"] != expected_capital:
            errors.append(
                {
                    "code": "CAPITAL_COUNT_ARITHMETIC",
                    "message": (
                        f"capital_and_ownership_events expected {expected_capital}, "
                        f"found {effective['capital_and_ownership_events']}"
                    ),
                }
            )
    if isinstance(baseline_counts.get("supplier_dependency_relationships"), int) and isinstance(
        effective.get("supplier_dependency_relationships"), int
    ):
        expected_supplier = baseline_counts["supplier_dependency_relationships"] + len(
            delta.get("supplier_dependency_relationships") or []
        )
        if effective["supplier_dependency_relationships"] != expected_supplier:
            errors.append(
                {
                    "code": "SUPPLIER_COUNT_ARITHMETIC",
                    "message": (
                        f"supplier_dependency_relationships expected {expected_supplier}, "
                        f"found {effective['supplier_dependency_relationships']}"
                    ),
                }
            )
    if effective.get("organizations") != baseline_counts.get("active_nonlegacy_organization_denominator"):
        # Organizations stay at the active non-legacy denominator across this lineage.
        if (
            effective.get("organizations") is not None
            and baseline_counts.get("active_nonlegacy_organization_denominator") is not None
        ):
            errors.append(
                {
                    "code": "ORG_COUNT_UNCHANGED",
                    "message": "organizations effective count must equal active non-legacy baseline denominator",
                }
            )

    return {
        "valid": not errors,
        "errors": errors,
        "issue_count": len(errors),
        "boundary": (
            "Lineage validation establishes mechanical package integrity only. "
            "It does not establish substantive observatory truth or assessment authority."
        ),
    }
