"""Governed migration surfaces for v1.6 adjudication and non-claim state."""

from __future__ import annotations

from typing import Any

from .util import canonical_json_bytes, sha256_bytes

ADJUDICATION_MIGRATION_BOUNDARY = (
    "v1.6 adjudication-state preservation only. No-change confirmations remain scoped comparison evidence, "
    "reopening decisions remain human-governed decisions without assessment mutation, and withheld claims remain "
    "explicit non-claims. None of these records is promoted to substantive truth or publication authority."
)
NO_CHANGE_STATE = "PRESERVED_SCOPED_NO_CHANGE_COMPARISON"
REOPENING_STATE = "PRESERVED_REOPENING_DECISION"
WITHHELD_STATE = "PRESERVED_WITHHELD_CLAIM_BOUNDARY"

_NO_CHANGE_FIELDS = frozenset({"object", "result", "source_ids"})
_REOPENING_FIELDS = frozenset({"decision_id", "object", "decision", "basis", "required_actions"})


class ObservatoryAdjudicationMigrationError(ValueError):
    """Raised when predecessor adjudication state cannot be preserved exactly."""


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservatoryAdjudicationMigrationError(f"{field} must be a non-empty string")
    return value.strip()


def _strings(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ObservatoryAdjudicationMigrationError(f"{field} must be an array of non-empty strings")
    return list(value)


def _exact_fields(record: dict[str, Any], expected: frozenset[str], *, family: str) -> None:
    actual = set(record)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ObservatoryAdjudicationMigrationError(
            f"{family} predecessor shape mismatch: missing={missing}, extra={extra}"
        )


def _delta_ids(delta16: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for family, records in delta16.items():
        if not isinstance(records, list):
            raise ObservatoryAdjudicationMigrationError(f"delta16.{family} must be an array")
        for record in records:
            if not isinstance(record, dict):
                raise ObservatoryAdjudicationMigrationError(f"delta16.{family} entries must be objects")
            ids = [value for key, value in record.items() if key.endswith("_id") and isinstance(value, str)]
            result.update(ids)
    return result


def preserve_v16_adjudication_state(
    *,
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
    known_source_ids: set[str],
) -> dict[str, Any]:
    """Preserve no-change, reopening, and withheld-claim state with exact bounded semantics."""
    no_change = v16_refresh.get("no_change_confirmations")
    reopenings = v16_refresh.get("reopening_decisions")
    withheld = v16_refresh.get("withheld_claims")
    if not isinstance(no_change, list) or not isinstance(reopenings, list) or not isinstance(withheld, list):
        raise ObservatoryAdjudicationMigrationError(
            "v1.6 no_change_confirmations, reopening_decisions, and withheld_claims must be arrays"
        )

    no_change_records: list[dict[str, Any]] = []
    seen_objects: set[str] = set()
    for index, raw in enumerate(no_change):
        if not isinstance(raw, dict):
            raise ObservatoryAdjudicationMigrationError(f"no_change_confirmations record {index} must be an object")
        _exact_fields(raw, _NO_CHANGE_FIELDS, family="no_change_confirmations")
        obj = _string(raw.get("object"), field="no_change_confirmations.object")
        result = _string(raw.get("result"), field="no_change_confirmations.result")
        if obj in seen_objects:
            raise ObservatoryAdjudicationMigrationError(f"duplicate no-change comparison object {obj!r}")
        seen_objects.add(obj)
        source_ids = _strings(raw.get("source_ids"), field="no_change_confirmations.source_ids")
        missing_sources = sorted(set(source_ids) - known_source_ids)
        if missing_sources:
            raise ObservatoryAdjudicationMigrationError(
                f"no_change_confirmations references missing Sources {missing_sources}"
            )
        no_change_records.append(
            {
                "migration_state": NO_CHANGE_STATE,
                "record_index": index,
                "object": obj,
                "comparison_result": result,
                "source_ids": source_ids,
                "global_absence_claimed": False,
                "predecessor_record_sha256": _digest(raw),
                "predecessor_record": raw,
                "native_object_created": False,
                "native_authority": False,
                "boundary": ADJUDICATION_MIGRATION_BOUNDARY,
            }
        )

    delta_ids = _delta_ids(delta16)
    reopening_records: list[dict[str, Any]] = []
    seen_decisions: set[str] = set()
    for index, raw in enumerate(reopenings):
        if not isinstance(raw, dict):
            raise ObservatoryAdjudicationMigrationError(f"reopening_decisions record {index} must be an object")
        _exact_fields(raw, _REOPENING_FIELDS, family="reopening_decisions")
        decision_id = _string(raw.get("decision_id"), field="reopening_decisions.decision_id")
        if decision_id in seen_decisions:
            raise ObservatoryAdjudicationMigrationError(f"duplicate reopening decision id {decision_id}")
        seen_decisions.add(decision_id)
        obj = _string(raw.get("object"), field="reopening_decisions.object")
        decision = _string(raw.get("decision"), field="reopening_decisions.decision")
        basis = _strings(raw.get("basis"), field="reopening_decisions.basis")
        missing_basis = sorted(set(basis) - delta_ids)
        if missing_basis:
            raise ObservatoryAdjudicationMigrationError(
                f"reopening decision {decision_id} references unknown delta basis ids {missing_basis}"
            )
        actions = _strings(raw.get("required_actions"), field="reopening_decisions.required_actions")
        reopening_records.append(
            {
                "migration_state": REOPENING_STATE,
                "record_index": index,
                "decision_id": decision_id,
                "object": obj,
                "decision": decision,
                "basis": basis,
                "required_actions": actions,
                "assessment_mutation_performed_by_migration": False,
                "predecessor_record_sha256": _digest(raw),
                "predecessor_record": raw,
                "native_object_created": False,
                "native_authority": False,
                "boundary": ADJUDICATION_MIGRATION_BOUNDARY,
            }
        )

    withheld_records: list[dict[str, Any]] = []
    seen_withheld: set[str] = set()
    for index, raw in enumerate(withheld):
        claim = _string(raw, field="withheld_claims[]")
        if claim in seen_withheld:
            raise ObservatoryAdjudicationMigrationError(f"duplicate withheld claim {claim!r}")
        seen_withheld.add(claim)
        withheld_records.append(
            {
                "migration_state": WITHHELD_STATE,
                "record_index": index,
                "withheld_claim": claim,
                "predecessor_value_sha256": _digest(raw),
                "predecessor_value": raw,
                "substantive_claim_created": False,
                "native_authority": False,
                "boundary": ADJUDICATION_MIGRATION_BOUNDARY,
            }
        )

    state = {
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_object_count": 0,
        "no_change_confirmations": no_change_records,
        "reopening_decisions": reopening_records,
        "withheld_claims": withheld_records,
        "counts": {
            "no_change_confirmations": len(no_change_records),
            "reopening_decisions": len(reopening_records),
            "withheld_claims": len(withheld_records),
            "total_governed_records": len(no_change_records) + len(reopening_records) + len(withheld_records),
        },
        "boundary": ADJUDICATION_MIGRATION_BOUNDARY,
    }
    errors = verify_v16_adjudication_state(state, known_source_ids=known_source_ids, delta_ids=delta_ids)
    if errors:
        raise ObservatoryAdjudicationMigrationError(f"generated v1.6 adjudication state is invalid: {errors}")
    return state


def verify_v16_adjudication_state(
    state: dict[str, Any],
    *,
    known_source_ids: set[str],
    delta_ids: set[str],
) -> list[str]:
    """Verify preserved adjudication payloads and non-mutation/non-claim boundaries."""
    errors: list[str] = []
    if state.get("state") != "NONCANONICAL_CANDIDATE" or state.get("release_authorized") is not False:
        errors.append("adjudication migration must remain noncanonical and unauthorized")
    if state.get("native_object_count") != 0:
        errors.append("adjudication migration must not claim native object creation")
    if state.get("boundary") != ADJUDICATION_MIGRATION_BOUNDARY:
        errors.append("adjudication migration boundary mismatch")

    no_change = state.get("no_change_confirmations")
    reopenings = state.get("reopening_decisions")
    withheld = state.get("withheld_claims")
    if not isinstance(no_change, list) or not isinstance(reopenings, list) or not isinstance(withheld, list):
        return ["adjudication child arrays are missing"]

    for record in no_change:
        if not isinstance(record, dict):
            errors.append("no-change migration record must be an object")
            continue
        predecessor = record.get("predecessor_record")
        if not isinstance(predecessor, dict) or record.get("predecessor_record_sha256") != _digest(predecessor):
            errors.append("no-change predecessor digest mismatch")
        if record.get("migration_state") != NO_CHANGE_STATE:
            errors.append("no-change migration_state mismatch")
        if record.get("global_absence_claimed") is not False:
            errors.append("no-change state must not claim global absence")
        if record.get("native_object_created") is not False or record.get("native_authority") is not False:
            errors.append("no-change state must remain nonnative and unauthorized")
        missing_sources = sorted(set(record.get("source_ids") or []) - known_source_ids)
        if missing_sources:
            errors.append(f"no-change state references missing Sources {missing_sources}")

    for record in reopenings:
        if not isinstance(record, dict):
            errors.append("reopening migration record must be an object")
            continue
        predecessor = record.get("predecessor_record")
        if not isinstance(predecessor, dict) or record.get("predecessor_record_sha256") != _digest(predecessor):
            errors.append("reopening predecessor digest mismatch")
        if record.get("migration_state") != REOPENING_STATE:
            errors.append("reopening migration_state mismatch")
        if record.get("assessment_mutation_performed_by_migration") is not False:
            errors.append("reopening migration must not mutate assessment")
        if record.get("native_object_created") is not False or record.get("native_authority") is not False:
            errors.append("reopening state must remain nonnative and unauthorized")
        missing_basis = sorted(set(record.get("basis") or []) - delta_ids)
        if missing_basis:
            errors.append(f"reopening state references unknown delta basis ids {missing_basis}")

    for record in withheld:
        if not isinstance(record, dict):
            errors.append("withheld-claim migration record must be an object")
            continue
        value = record.get("predecessor_value")
        if record.get("predecessor_value_sha256") != _digest(value):
            errors.append("withheld-claim predecessor digest mismatch")
        if record.get("migration_state") != WITHHELD_STATE:
            errors.append("withheld-claim migration_state mismatch")
        if record.get("substantive_claim_created") is not False or record.get("native_authority") is not False:
            errors.append("withheld claim must remain a non-claim without authority")

    expected_counts = {
        "no_change_confirmations": len(no_change),
        "reopening_decisions": len(reopenings),
        "withheld_claims": len(withheld),
        "total_governed_records": len(no_change) + len(reopenings) + len(withheld),
    }
    if state.get("counts") != expected_counts:
        errors.append("adjudication count reconciliation mismatch")
    return sorted(set(errors))
