"""Full noncanonical Gate-A predecessor migration checkpoint.

This module composes native objects with governed predecessor-state surfaces across the
frozen v1.4/v1.6/DELTA16/v1.7/PRIMA corpus and source/monitor registries. The current
checkpoint can establish representational completeness while still withholding Gate-A
completion pending end-to-end field proof, typed validation, and identity-bound packaging.
"""

from __future__ import annotations

from typing import Any

from .observatory_adjudication_migration import (
    ADJUDICATION_MIGRATION_BOUNDARY,
    delta16_record_ids,
    preserve_v16_adjudication_state,
    verify_v16_adjudication_state,
)
from .observatory_migration_candidate import (
    MIGRATION_CANDIDATE_BOUNDARY,
    build_predecessor_migration_candidate,
    verify_predecessor_migration_candidate,
)
from .observatory_residual_migration import (
    RESIDUAL_MIGRATION_BOUNDARY,
    RESIDUAL_POLICIES,
    preserve_residual_gate_a_state,
    verify_residual_gate_a_state,
)
from .observatory_successor_migration import (
    SUCCESSOR_MIGRATION_BOUNDARY,
    preserve_v17_successor_lineage,
    verify_v17_successor_lineage,
)
from .util import canonical_json_bytes, sha256_bytes

GATE_A_MIGRATION_BOUNDARY = (
    "Noncanonical Gate-A predecessor migration checkpoint. Exact native and governed-preserved surfaces are "
    "reconciled across the frozen predecessor corpus. Representational completeness means every in-scope family "
    "has an exact native or governed-preserved destination; it does not establish substantive truth, complete "
    "native graph materialization, institutional authority, or publication authorization."
)

REMAINING_GATE_REQUIREMENTS = (
    "UPDATED_FIELD_PROOF_EXECUTION_AND_DIGEST",
    "CANDIDATE_WIDE_TYPED_REFERENTIAL_AND_TEMPORAL_VALIDATION",
    "IDENTITY_BOUND_DETERMINISTIC_FULL_PACKAGE",
)

_GOVERNED_ELSEWHERE_FAMILIES = {
    "V16.adjudicated_delta",
    "V16.reopening_decisions",
    "V16.no_change_confirmations",
    "V16.withheld_claims",
    "V17.*",
    "PRIMA17.*",
}


class ObservatoryGateAMigrationError(ValueError):
    """Raised when the full migration checkpoint does not reconcile exactly."""


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _residual_family_keys(residual: dict[str, Any]) -> set[str]:
    families = residual.get("residual_families")
    if not isinstance(families, list):
        return set()
    keys: set[str] = set()
    for item in families:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        family = item.get("family")
        if isinstance(role, str) and isinstance(family, str):
            keys.add(f"{role}.{family}")
    return keys


def _expected_delta16_residual_keys() -> set[str]:
    return {
        f"{role}.{family}"
        for role, family in RESIDUAL_POLICIES
        if role == "DELTA16"
    }


def _expected_remaining_families(
    candidate: dict[str, Any], residual: dict[str, Any]
) -> list[str]:
    represented = set(_GOVERNED_ELSEWHERE_FAMILIES)
    residual_keys = _residual_family_keys(residual)
    represented.update(residual_keys)

    expected_delta_keys = _expected_delta16_residual_keys()
    actual_delta_keys = {
        key for key in residual_keys if key.startswith("DELTA16.")
    }
    if expected_delta_keys and actual_delta_keys == expected_delta_keys:
        represented.add("DELTA16.*")

    unresolved = candidate.get("remaining_unmaterialized_families")
    if not isinstance(unresolved, list):
        return ["CANDIDATE_REMAINING_FAMILY_LEDGER_MISSING"]
    return [family for family in unresolved if family not in represented]


def build_gate_a_migration_checkpoint(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
    v17_successor: dict[str, Any],
    prima17: dict[str, Any],
    source_register14: list[dict[str, Any]],
    monitor15: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compose all currently governed migration surfaces into one representational checkpoint."""
    embedded_v16_delta = v16_refresh.get("adjudicated_delta")
    if embedded_v16_delta != delta16:
        raise ObservatoryGateAMigrationError(
            "v1.6 adjudicated_delta container is not exactly the standalone DELTA16 input"
        )

    candidate = build_predecessor_migration_candidate(
        v14_release=v14_release,
        v16_refresh=v16_refresh,
    )
    if candidate.get("mechanical_verification") != "PASS":
        raise ObservatoryGateAMigrationError("base migration candidate must mechanically pass")
    source_ids = {
        str(source["source_id"])
        for source in candidate["core"]["source_migration"]["sources"]
    }
    adjudication = preserve_v16_adjudication_state(
        v16_refresh=v16_refresh,
        delta16=delta16,
        known_source_ids=source_ids,
    )
    successor = preserve_v17_successor_lineage(
        v16_refresh=v16_refresh,
        delta16=delta16,
        v17_successor=v17_successor,
        prima17=prima17,
    )
    residual = preserve_residual_gate_a_state(
        v14_release=v14_release,
        v16_refresh=v16_refresh,
        delta16=delta16,
        source_register14=source_register14,
        monitor15=monitor15,
        known_source_ids=source_ids,
    )

    remaining = _expected_remaining_families(candidate, residual)
    representation_complete = not remaining
    result = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "representational_scope_complete": representation_complete,
        "gate_a_complete": False,
        "candidate": candidate,
        "v16_adjudication_state": adjudication,
        "v17_successor_lineage": successor,
        "residual_predecessor_state": residual,
        "duplicate_container_proofs": {
            "v16_embedded_delta_equals_delta16": True,
            "v16_embedded_delta_sha256": _digest(embedded_v16_delta),
            "standalone_delta16_sha256": _digest(delta16),
            "v17_embedded_delta_equals_delta16": successor["embedded_delta_sha256"]
            == successor["standalone_delta_sha256"],
            "v17_embedded_prima_equals_standalone_prima": successor["embedded_prima_sha256"]
            == successor["standalone_prima_sha256"],
        },
        "counts": {
            "native_objects": candidate["counts"]["native_candidate_objects"],
            "preserved_organization_records": candidate["counts"]["preserved_organization_records"],
            "predecessor_observation_evidence_records": candidate["counts"][
                "predecessor_observation_evidence_records"
            ],
            "governed_v14_history_records": candidate["counts"]["governed_predecessor_history_records"],
            "governed_v16_adjudication_records": adjudication["counts"]["total_governed_records"],
            "governed_successor_packages": 2,
            "residual_family_records": residual["counts"]["residual_record_count"],
            "release_level_bundles": residual["counts"]["release_level_bundle_count"],
            "source_register_records": residual["counts"]["source_register_records"],
            "monitor_registry_records": residual["counts"]["monitor_registry_records"],
        },
        "remaining_unresolved_families": remaining,
        "remaining_gate_requirements": list(REMAINING_GATE_REQUIREMENTS),
        "boundaries": {
            "gate_a": GATE_A_MIGRATION_BOUNDARY,
            "candidate": MIGRATION_CANDIDATE_BOUNDARY,
            "adjudication": ADJUDICATION_MIGRATION_BOUNDARY,
            "successor": SUCCESSOR_MIGRATION_BOUNDARY,
            "residual": RESIDUAL_MIGRATION_BOUNDARY,
        },
    }
    report = verify_gate_a_migration_checkpoint(result, delta16=delta16)
    result["mechanical_verification"] = "PASS" if report["valid"] else "FAIL"
    result["verification_errors"] = report["errors"]
    return result


def verify_gate_a_migration_checkpoint(
    result: dict[str, Any],
    *,
    delta16: dict[str, Any],
) -> dict[str, Any]:
    """Verify representational completeness while keeping Gate-A authority withheld."""
    errors: list[str] = []
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        errors.append("Gate-A migration checkpoint must remain noncanonical and unauthorized")
    if result.get("native_v2_materialization_complete") is not False:
        errors.append("Gate-A checkpoint must not claim complete native v2 materialization")
    if result.get("gate_a_complete") is not False:
        errors.append("Gate-A completion must remain false until all non-representational gates close")

    candidate = result.get("candidate")
    adjudication = result.get("v16_adjudication_state")
    successor = result.get("v17_successor_lineage")
    residual = result.get("residual_predecessor_state")
    if not all(isinstance(item, dict) for item in (candidate, adjudication, successor, residual)):
        return {"valid": False, "errors": ["Gate-A child migration surfaces are missing"]}

    candidate_report = verify_predecessor_migration_candidate(candidate)
    errors.extend(f"candidate: {error}" for error in candidate_report["errors"])
    source_ids = {
        str(source["source_id"])
        for source in candidate.get("core", {}).get("source_migration", {}).get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("source_id"), str)
    }
    try:
        controlled_delta_ids = delta16_record_ids(delta16)
    except Exception as exc:
        errors.append(f"DELTA16 controlled identity validation failed: {exc}")
        controlled_delta_ids = set()
    errors.extend(
        f"adjudication: {error}"
        for error in verify_v16_adjudication_state(
            adjudication,
            known_source_ids=source_ids,
            delta_ids=controlled_delta_ids,
        )
    )
    errors.extend(f"successor: {error}" for error in verify_v17_successor_lineage(successor))
    errors.extend(
        f"residual: {error}"
        for error in verify_residual_gate_a_state(residual, known_source_ids=source_ids)
    )

    duplicate = result.get("duplicate_container_proofs")
    if not isinstance(duplicate, dict):
        errors.append("duplicate-container proof is missing")
    else:
        if duplicate.get("v16_embedded_delta_equals_delta16") is not True:
            errors.append("v1.6 embedded delta equality proof failed")
        if duplicate.get("v16_embedded_delta_sha256") != duplicate.get("standalone_delta16_sha256"):
            errors.append("v1.6 embedded/standalone DELTA16 digest mismatch")
        if duplicate.get("standalone_delta16_sha256") != _digest(delta16):
            errors.append("Gate-A DELTA16 digest binding mismatch")
        if duplicate.get("v17_embedded_delta_equals_delta16") is not True:
            errors.append("v1.7 embedded DELTA16 equality proof failed")
        if duplicate.get("v17_embedded_prima_equals_standalone_prima") is not True:
            errors.append("v1.7 embedded PRIMA equality proof failed")

    counts = result.get("counts")
    if not isinstance(counts, dict):
        errors.append("Gate-A counts are missing")
    else:
        expected = {
            "native_objects": candidate.get("counts", {}).get("native_candidate_objects"),
            "preserved_organization_records": candidate.get("counts", {}).get("preserved_organization_records"),
            "predecessor_observation_evidence_records": candidate.get("counts", {}).get(
                "predecessor_observation_evidence_records"
            ),
            "governed_v14_history_records": candidate.get("counts", {}).get("governed_predecessor_history_records"),
            "governed_v16_adjudication_records": adjudication.get("counts", {}).get("total_governed_records"),
            "governed_successor_packages": 2,
            "residual_family_records": residual.get("counts", {}).get("residual_record_count"),
            "release_level_bundles": residual.get("counts", {}).get("release_level_bundle_count"),
            "source_register_records": residual.get("counts", {}).get("source_register_records"),
            "monitor_registry_records": residual.get("counts", {}).get("monitor_registry_records"),
        }
        if counts != expected:
            errors.append("Gate-A count reconciliation mismatch")

    remaining = result.get("remaining_unresolved_families")
    expected_remaining = _expected_remaining_families(candidate, residual)
    if not isinstance(remaining, list):
        errors.append("remaining unresolved family ledger is missing")
    else:
        claimed_complete = not remaining
        if result.get("representational_scope_complete") is not claimed_complete:
            errors.append("representational_scope_complete does not match unresolved-family ledger")
        if remaining != expected_remaining:
            errors.append("remaining unresolved family ledger does not reconcile with governed surfaces")
        expected_complete = not expected_remaining
        if result.get("representational_scope_complete") is not expected_complete:
            errors.append("representational_scope_complete does not match governed family reconciliation")
        if expected_remaining:
            errors.append(f"representational scope still has unresolved families: {expected_remaining}")

    requirements = result.get("remaining_gate_requirements")
    if requirements != list(REMAINING_GATE_REQUIREMENTS):
        errors.append("remaining Gate-A requirement ledger mismatch")
    if not requirements:
        errors.append("Gate-A cannot remain incomplete without explicit remaining requirements")

    return {"valid": not errors, "errors": sorted(set(errors))}
