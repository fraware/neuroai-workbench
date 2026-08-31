"""Full noncanonical Gate-A predecessor migration checkpoint.

This module composes the current native migration candidate with governed v1.6
adjudication state and exact v1.7/PRIMA successor lineage. It is a checkpoint, not a
release: unresolved substantive families remain listed explicitly.
"""

from __future__ import annotations

from typing import Any

from .observatory_adjudication_migration import (
    ADJUDICATION_MIGRATION_BOUNDARY,
    preserve_v16_adjudication_state,
    verify_v16_adjudication_state,
)
from .observatory_migration_candidate import (
    MIGRATION_CANDIDATE_BOUNDARY,
    build_predecessor_migration_candidate,
    verify_predecessor_migration_candidate,
)
from .observatory_successor_migration import (
    SUCCESSOR_MIGRATION_BOUNDARY,
    preserve_v17_successor_lineage,
    verify_v17_successor_lineage,
)
from .util import canonical_json_bytes, sha256_bytes

GATE_A_MIGRATION_BOUNDARY = (
    "Noncanonical Gate-A predecessor migration checkpoint. Exact native and governed-preserved surfaces are "
    "reconciled across v1.4, v1.6, DELTA16, v1.7, and PRIMA17. Remaining families are explicit. Mechanical "
    "verification does not establish complete migration, substantive truth, assessment authority, or publication."
)


class ObservatoryGateAMigrationError(ValueError):
    """Raised when the full migration checkpoint does not reconcile exactly."""


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _delta_ids(delta16: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for records in delta16.values():
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    result.update(
                        value
                        for key, value in record.items()
                        if key.endswith("_id") and isinstance(value, str)
                    )
    return result


def build_gate_a_migration_checkpoint(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
    v17_successor: dict[str, Any],
    prima17: dict[str, Any],
) -> dict[str, Any]:
    """Compose all currently governed migration surfaces into one checkpoint."""
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

    retired = {
        "V16.adjudicated_delta",
        "V16.reopening_decisions",
        "V16.no_change_confirmations",
        "V16.withheld_claims",
        "V17.*",
        "PRIMA17.*",
    }
    remaining = [
        family
        for family in candidate["remaining_unmaterialized_families"]
        if family not in retired
    ]
    result = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "gate_a_complete": False,
        "candidate": candidate,
        "v16_adjudication_state": adjudication,
        "v17_successor_lineage": successor,
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
        },
        "remaining_unresolved_families": remaining,
        "boundaries": {
            "gate_a": GATE_A_MIGRATION_BOUNDARY,
            "candidate": MIGRATION_CANDIDATE_BOUNDARY,
            "adjudication": ADJUDICATION_MIGRATION_BOUNDARY,
            "successor": SUCCESSOR_MIGRATION_BOUNDARY,
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
    """Verify composed Gate-A state without converting unresolved families into success."""
    errors: list[str] = []
    if result.get("state") != "NONCANONICAL_CANDIDATE" or result.get("release_authorized") is not False:
        errors.append("Gate-A migration checkpoint must remain noncanonical and unauthorized")
    if result.get("native_v2_materialization_complete") is not False:
        errors.append("Gate-A checkpoint must not claim complete native v2 materialization")
    if result.get("gate_a_complete") is not False:
        errors.append("Gate-A checkpoint must remain incomplete while unresolved families exist")

    candidate = result.get("candidate")
    adjudication = result.get("v16_adjudication_state")
    successor = result.get("v17_successor_lineage")
    if not isinstance(candidate, dict) or not isinstance(adjudication, dict) or not isinstance(successor, dict):
        return {"valid": False, "errors": ["Gate-A child migration surfaces are missing"]}

    candidate_report = verify_predecessor_migration_candidate(candidate)
    errors.extend(f"candidate: {error}" for error in candidate_report["errors"])
    source_ids = {
        str(source["source_id"])
        for source in candidate.get("core", {}).get("source_migration", {}).get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("source_id"), str)
    }
    adjudication_errors = verify_v16_adjudication_state(
        adjudication,
        known_source_ids=source_ids,
        delta_ids=_delta_ids(delta16),
    )
    errors.extend(f"adjudication: {error}" for error in adjudication_errors)
    errors.extend(f"successor: {error}" for error in verify_v17_successor_lineage(successor))

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
        }
        if counts != expected:
            errors.append("Gate-A count reconciliation mismatch")

    remaining = result.get("remaining_unresolved_families")
    if not isinstance(remaining, list):
        errors.append("remaining unresolved family ledger is missing")
    elif not remaining:
        errors.append("Gate-A cannot be declared incomplete with an empty unresolved-family ledger")
    else:
        retired = {
            "V16.adjudicated_delta",
            "V16.reopening_decisions",
            "V16.no_change_confirmations",
            "V16.withheld_claims",
            "V17.*",
            "PRIMA17.*",
        }
        for family in sorted(retired & set(remaining)):
            errors.append(f"resolved governed family remains in unresolved ledger: {family}")

    return {"valid": not errors, "errors": sorted(set(errors))}
