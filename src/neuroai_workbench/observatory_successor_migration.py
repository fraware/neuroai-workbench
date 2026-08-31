"""Lossless preservation of v1.7 successor and PRIMA assessment-transition state.

The v1.7 snapshot embeds the v1.6 adjudicated delta and the standalone PRIMA successor
delta for release traceability. This module proves those embeddings are exact, preserves
reopening lineage, and prevents duplicate materialization of embedded predecessor state.
"""

from __future__ import annotations

from typing import Any

from .util import canonical_json_bytes, sha256_bytes

SUCCESSOR_MIGRATION_BOUNDARY = (
    "v1.7 successor/reopening lineage preservation only. Embedded predecessor delta and PRIMA successor "
    "payloads are verified as exact duplicate containers and are not double-materialized. Assessment state, "
    "regulatory claims, reopening decisions, and prohibited inferences remain predecessor-governed state; "
    "this migration does not mutate an assessment or confer publication authority."
)
SUCCESSOR_MIGRATION_STATE = "PRESERVED_V17_SUCCESSOR_LINEAGE"


class ObservatorySuccessorMigrationError(ValueError):
    """Raised when successor lineage or duplicate-container identity does not reconcile exactly."""


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ObservatorySuccessorMigrationError(f"{field} must be an object")
    return value


def _array(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ObservatorySuccessorMigrationError(f"{field} must be an array")
    return value


def preserve_v17_successor_lineage(
    *,
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
    v17_successor: dict[str, Any],
    prima17: dict[str, Any],
) -> dict[str, Any]:
    """Preserve exact v1.7/PRIMA successor lineage and fail on duplicate-container drift."""
    metadata = _mapping(v17_successor.get("metadata"), field="v17.metadata")
    if metadata.get("version") != "v1.7" or metadata.get("predecessor") != "v1.6":
        raise ObservatorySuccessorMigrationError("v1.7 metadata predecessor/version identity mismatch")
    if metadata.get("status") != "CONTROLLED_SUCCESSOR_SNAPSHOT":
        raise ObservatorySuccessorMigrationError("v1.7 status must remain CONTROLLED_SUCCESSOR_SNAPSHOT")

    embedded_delta = v17_successor.get("delta")
    if embedded_delta != delta16:
        raise ObservatorySuccessorMigrationError("v1.7 embedded delta is not exactly the standalone v1.6 delta")
    embedded_prima = v17_successor.get("assessment_successor_delta")
    if embedded_prima != prima17:
        raise ObservatorySuccessorMigrationError("v1.7 embedded PRIMA successor delta is not exact standalone PRIMA")

    baseline_reference = _mapping(v17_successor.get("baseline_reference"), field="v17.baseline_reference")
    provenance = _mapping(v17_successor.get("provenance"), field="v17.provenance")
    predecessor_reference = _mapping(v17_successor.get("predecessor_reference"), field="v17.predecessor_reference")
    prima_predecessor = _mapping(prima17.get("predecessor_reference"), field="prima.predecessor_reference")
    baseline_sha = baseline_reference.get("canonical_sha256")
    if not isinstance(baseline_sha, str) or len(baseline_sha) != 64:
        raise ObservatorySuccessorMigrationError("v1.7 baseline reference lacks canonical SHA-256")
    if provenance.get("baseline_sha256") != baseline_sha:
        raise ObservatorySuccessorMigrationError("v1.7 baseline hash does not reconcile with provenance")
    predecessor_sha = predecessor_reference.get("v1_6_archive_sha256")
    if not isinstance(predecessor_sha, str) or len(predecessor_sha) != 64:
        raise ObservatorySuccessorMigrationError("v1.7 predecessor archive SHA-256 is missing")
    if provenance.get("predecessor_archive_sha256") != predecessor_sha:
        raise ObservatorySuccessorMigrationError("v1.7 predecessor archive hash does not reconcile with provenance")
    if prima_predecessor.get("archive_sha256") != predecessor_sha:
        raise ObservatorySuccessorMigrationError("PRIMA predecessor archive hash does not match v1.7 predecessor")
    if baseline_reference.get("immutable") is not True or predecessor_reference.get("immutable") is not True:
        raise ObservatorySuccessorMigrationError("v1.7 predecessor references must remain immutable")
    if prima_predecessor.get("immutable") is not True:
        raise ObservatorySuccessorMigrationError("PRIMA predecessor reference must remain immutable")

    prima_metadata = _mapping(prima17.get("metadata"), field="prima.metadata")
    if prima_metadata.get("version") != "v1.7" or prima_metadata.get("predecessor") != "v1.6":
        raise ObservatorySuccessorMigrationError("PRIMA successor metadata predecessor/version mismatch")
    if prima_metadata.get("status") != "CONTROLLED_SUCCESSOR":
        raise ObservatorySuccessorMigrationError("PRIMA status must remain CONTROLLED_SUCCESSOR")

    transition = _mapping(prima17.get("reopening_transition"), field="prima.reopening_transition")
    predecessor_id = transition.get("predecessor_decision_id")
    successor_id = transition.get("successor_decision_id")
    if not isinstance(predecessor_id, str) or not isinstance(successor_id, str):
        raise ObservatorySuccessorMigrationError("reopening transition decision ids must be strings")

    v16_reopenings = _array(v16_refresh.get("reopening_decisions"), field="v16.reopening_decisions")
    v17_reopenings = _array(v17_successor.get("reopening_decisions"), field="v17.reopening_decisions")
    if any(not isinstance(item, dict) for item in [*v16_reopenings, *v17_reopenings]):
        raise ObservatorySuccessorMigrationError("reopening decision entries must be objects")
    old = {str(item.get("decision_id")): item for item in v16_reopenings}
    new = {str(item.get("decision_id")): item for item in v17_reopenings}
    if len(old) != len(v16_reopenings) or len(new) != len(v17_reopenings):
        raise ObservatorySuccessorMigrationError("reopening decision ids must be complete and unique")
    predecessor_decision = old.get(predecessor_id)
    successor_decision = new.get(successor_id)
    if predecessor_decision is None or successor_decision is None:
        raise ObservatorySuccessorMigrationError("reopening transition references missing predecessor/successor decision")
    if transition.get("predecessor_state") != predecessor_decision.get("decision"):
        raise ObservatorySuccessorMigrationError("reopening predecessor state does not match v1.6 decision")
    if transition.get("successor_state") != successor_decision.get("decision"):
        raise ObservatorySuccessorMigrationError("reopening successor state does not match v1.7 decision")
    if predecessor_id in new:
        raise ObservatorySuccessorMigrationError("superseded reopening predecessor decision must not remain in v1.7 set")
    if successor_id in old:
        raise ObservatorySuccessorMigrationError("successor reopening decision must not pre-exist in v1.6 set")
    unchanged_old = {key: value for key, value in old.items() if key != predecessor_id}
    unchanged_new = {key: value for key, value in new.items() if key != successor_id}
    if unchanged_old != unchanged_new:
        raise ObservatorySuccessorMigrationError("unrelated reopening decisions changed across v1.6 to v1.7")
    if transition.get("open_actions") != successor_decision.get("required_actions"):
        raise ObservatorySuccessorMigrationError("PRIMA open_actions do not match successor required_actions")

    assessment_delta = _mapping(prima17.get("assessment_delta"), field="prima.assessment_delta")
    assessment_id = assessment_delta.get("assessment_id")
    predecessor_basis = predecessor_decision.get("basis")
    successor_basis = successor_decision.get("basis")
    if not isinstance(predecessor_basis, list) or not isinstance(successor_basis, list):
        raise ObservatorySuccessorMigrationError("reopening basis fields must be arrays")
    if not set(predecessor_basis).issubset(set(successor_basis)):
        raise ObservatorySuccessorMigrationError("successor reopening basis dropped predecessor trigger ids")
    if assessment_id not in successor_basis:
        raise ObservatorySuccessorMigrationError("successor reopening basis does not include executed assessment id")

    prohibited = _array(prima17.get("prohibited_inferences"), field="prima.prohibited_inferences")
    if not prohibited or any(not isinstance(item, str) or not item.strip() for item in prohibited):
        raise ObservatorySuccessorMigrationError("PRIMA prohibited_inferences must remain a non-empty string array")

    state = {
        "migration_state": SUCCESSOR_MIGRATION_STATE,
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_objects_created": 0,
        "v17_version": metadata["version"],
        "predecessor_version": metadata["predecessor"],
        "baseline_sha256": baseline_sha,
        "predecessor_archive_sha256": predecessor_sha,
        "embedded_delta_sha256": _digest(embedded_delta),
        "standalone_delta_sha256": _digest(delta16),
        "embedded_prima_sha256": _digest(embedded_prima),
        "standalone_prima_sha256": _digest(prima17),
        "reopening_predecessor_decision_id": predecessor_id,
        "reopening_successor_decision_id": successor_id,
        "unchanged_reopening_decision_count": len(unchanged_old),
        "prohibited_inference_count": len(prohibited),
        "v17_successor_sha256": _digest(v17_successor),
        "v17_successor": v17_successor,
        "prima17": prima17,
        "native_authority": False,
        "boundary": SUCCESSOR_MIGRATION_BOUNDARY,
    }
    verification = verify_v17_successor_lineage(state)
    if verification:
        raise ObservatorySuccessorMigrationError(f"generated successor migration state is invalid: {verification}")
    return state


def verify_v17_successor_lineage(state: dict[str, Any]) -> list[str]:
    """Verify preserved successor payload hashes and authority boundary independently."""
    errors: list[str] = []
    if state.get("migration_state") != SUCCESSOR_MIGRATION_STATE:
        errors.append("successor migration_state mismatch")
    if state.get("state") != "NONCANONICAL_CANDIDATE" or state.get("release_authorized") is not False:
        errors.append("successor migration must remain noncanonical and unauthorized")
    if state.get("native_objects_created") != 0:
        errors.append("successor migration must not claim native object creation")
    if state.get("native_authority") is not False:
        errors.append("native_authority must remain false")
    if state.get("boundary") != SUCCESSOR_MIGRATION_BOUNDARY:
        errors.append("successor migration boundary mismatch")
    v17 = state.get("v17_successor")
    prima = state.get("prima17")
    if not isinstance(v17, dict):
        errors.append("v17_successor must be an object")
    elif state.get("v17_successor_sha256") != _digest(v17):
        errors.append("v17_successor_sha256 mismatch")
    if not isinstance(prima, dict):
        errors.append("prima17 must be an object")
    elif state.get("standalone_prima_sha256") != _digest(prima):
        errors.append("standalone_prima_sha256 mismatch")
    if state.get("embedded_delta_sha256") != state.get("standalone_delta_sha256"):
        errors.append("embedded/standalone delta digest mismatch")
    if state.get("embedded_prima_sha256") != state.get("standalone_prima_sha256"):
        errors.append("embedded/standalone PRIMA digest mismatch")
    return sorted(set(errors))
