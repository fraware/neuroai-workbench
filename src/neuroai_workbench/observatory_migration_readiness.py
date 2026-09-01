"""Record-level readiness analysis for remaining Observatory-v2 predecessor families.

This module does not materialize graph objects. It explains, deterministically, why a
predecessor record is or is not currently eligible for native v2 materialization under
the governed migration contracts. A READY result is an engineering prerequisite only;
it does not establish substantive truth or release authority.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

READINESS_BOUNDARY = (
    "Migration readiness records whether required native semantics and controlled identities are already "
    "present. It does not create missing entities, infer current status, fabricate temporal values, establish "
    "substantive truth, mutate assessments, or authorize publication."
)

READY = "READY"
BLOCKED = "BLOCKED"


class MigrationReadinessError(ValueError):
    """Raised when a readiness input has an unexpected predecessor shape."""


def _source_blockers(record: dict[str, Any], source_ids: set[str]) -> list[str]:
    refs = record.get("source_ids")
    if not isinstance(refs, list) or any(not isinstance(item, str) or not item for item in refs):
        return ["SOURCE_REFERENCE_SHAPE_INVALID"]
    missing = sorted(set(refs) - source_ids)
    return [f"SOURCE_NOT_MATERIALIZED:{item}" for item in missing]


def _nonempty(record: dict[str, Any], field: str) -> bool:
    value = record.get(field)
    return isinstance(value, str) and bool(value.strip())


def _record_result(*, family: str, index: int, blockers: list[str], record_id: str | None) -> dict[str, Any]:
    unique = sorted(set(blockers))
    return {
        "family": family,
        "record_index": index,
        "record_id": record_id,
        "state": READY if not unique else BLOCKED,
        "blockers": unique,
        "boundary": READINESS_BOUNDARY,
    }


def _relationship_readiness(
    family: str,
    records: Any,
    *,
    id_field: str,
    subject_field: str,
    object_field: str,
    source_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise MigrationReadinessError(f"{family} must be an array")
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise MigrationReadinessError(f"{family}[{index}] must be an object")
        blockers = _source_blockers(raw, source_ids)
        if not _nonempty(raw, id_field):
            blockers.append("NATIVE_RELATIONSHIP_ID_MISSING")
        if not _nonempty(raw, "relationship_type") and family != "V14.participant_authority_relationships":
            blockers.append("NATIVE_RELATIONSHIP_TYPE_MISSING")
        if family == "V14.participant_authority_relationships" and not _nonempty(raw, "authority_type"):
            blockers.append("NATIVE_RELATIONSHIP_TYPE_MISSING")
        if not _nonempty(raw, subject_field):
            blockers.append("SUBJECT_LITERAL_MISSING")
        else:
            blockers.append("SUBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED")
        if not _nonempty(raw, object_field):
            blockers.append("OBJECT_LITERAL_MISSING")
        else:
            blockers.append("OBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED")
        if not _nonempty(raw, "boundary"):
            blockers.append("CLAIM_BOUNDARY_MISSING")
        if family != "V14.supplier_dependency_relationships" and not _nonempty(raw, "evidence_state"):
            blockers.append("EVIDENCE_STATE_MISSING")
        if family == "V14.supplier_dependency_relationships":
            blockers.append("EVIDENCE_STATE_NOT_GOVERNED_FOR_NATIVE_RELATIONSHIP")
        results.append(
            _record_result(
                family=family,
                index=index,
                blockers=blockers,
                record_id=str(raw.get(id_field) or "") or None,
            )
        )
    return results


def _model_readiness(family: str, records: Any, *, source_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise MigrationReadinessError(f"{family} must be an array")
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise MigrationReadinessError(f"{family}[{index}] must be an object")
        blockers = _source_blockers(raw, source_ids)
        if not _nonempty(raw, "model_id"):
            blockers.append("NATIVE_ENTITY_ID_MISSING")
        if not _nonempty(raw, "name"):
            blockers.append("NATIVE_ENTITY_LABEL_MISSING")
        # The predecessor carries model publication/verification states, but those do
        # not deterministically map to Entity.status ACTIVE/SUPERSEDED/WITHDRAWN.
        blockers.append("NATIVE_ENTITY_STATUS_NOT_GOVERNED")
        blockers.append("MODEL_ENTITY_TYPE_MAPPING_REQUIRES_GOVERNED_RULE")
        results.append(
            _record_result(
                family=family,
                index=index,
                blockers=blockers,
                record_id=str(raw.get("model_id") or "") or None,
            )
        )
    return results


def _reopening_readiness(family: str, records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise MigrationReadinessError(f"{family} must be an array")
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise MigrationReadinessError(f"{family}[{index}] must be an object")
        blockers: list[str] = []
        decision_id = raw.get("decision_id") or raw.get("reopening_decision_id")
        if not isinstance(decision_id, str) or not decision_id.strip():
            blockers.append("NATIVE_REOPENING_DECISION_ID_MISSING")
        subject = raw.get("object") or raw.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            blockers.append("SUBJECT_LITERAL_MISSING")
        blockers.append("SUBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED")
        if raw.get("decided_at") is None:
            blockers.append("DECIDED_AT_NOT_GOVERNED")
        basis = raw.get("basis")
        if basis is not None:
            if not isinstance(basis, list) or any(not isinstance(item, str) or not item for item in basis):
                blockers.append("TRIGGER_REFERENCE_SHAPE_INVALID")
            elif basis:
                blockers.append("TRIGGER_REFERENCE_CLASS_UNRESOLVED")
        results.append(
            _record_result(
                family=family,
                index=index,
                blockers=blockers,
                record_id=str(decision_id or "") or None,
            )
        )
    return results


def _delta_event_readiness(family: str, records: Any, *, source_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise MigrationReadinessError(f"{family} must be an array")
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            raise MigrationReadinessError(f"{family}[{index}] must be an object")
        blockers = _source_blockers(raw, source_ids)
        event_id = raw.get("event_id") or raw.get("governance_id")
        if not isinstance(event_id, str) or not event_id.strip():
            blockers.append("NATIVE_EVENT_ID_MISSING")
        subject = raw.get("subject") or raw.get("system") or raw.get("organization")
        if not isinstance(subject, str) or not subject.strip():
            blockers.append("SUBJECT_LITERAL_MISSING")
        else:
            blockers.append("SUBJECT_CONTROLLED_ENTITY_ID_UNRESOLVED")
        if not _nonempty(raw, "evidence_state"):
            blockers.append("EVIDENCE_STATE_NOT_GOVERNED_FOR_NATIVE_EVENT")
        boundary = raw.get("boundary") or raw.get("bounded_effect")
        if not isinstance(boundary, str) or not boundary.strip():
            blockers.append("CLAIM_BOUNDARY_MISSING")
        blockers.append("VERIFICATION_STATE_NOT_GOVERNED_FOR_NATIVE_EVENT")
        results.append(
            _record_result(
                family=family,
                index=index,
                blockers=blockers,
                record_id=str(event_id or "") or None,
            )
        )
    return results


def analyze_remaining_migration_readiness(
    *,
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
    v17_successor: dict[str, Any],
    materialized_source_ids: set[str],
) -> dict[str, Any]:
    """Return deterministic blockers for remaining high-value predecessor families."""
    families: dict[str, list[dict[str, Any]]] = {}
    families["V14.trial_site_relationships"] = _relationship_readiness(
        "V14.trial_site_relationships",
        v14_release.get("trial_site_relationships"),
        id_field="relationship_id",
        subject_field="system_or_study",
        object_field="site",
        source_ids=materialized_source_ids,
    )
    families["V14.participant_authority_relationships"] = _relationship_readiness(
        "V14.participant_authority_relationships",
        v14_release.get("participant_authority_relationships"),
        id_field="authority_id",
        subject_field="case",
        object_field="holder",
        source_ids=materialized_source_ids,
    )
    families["V14.supplier_dependency_relationships"] = _relationship_readiness(
        "V14.supplier_dependency_relationships",
        v14_release.get("supplier_dependency_relationships"),
        id_field="dependency_id",
        subject_field="system",
        object_field="provider_or_origin",
        source_ids=materialized_source_ids,
    )
    families["V14.representative_model_records"] = _model_readiness(
        "V14.representative_model_records",
        v14_release.get("representative_model_records"),
        source_ids=materialized_source_ids,
    )
    families["DELTA16.model_records"] = _model_readiness(
        "DELTA16.model_records",
        delta16.get("model_records"),
        source_ids=materialized_source_ids,
    )
    families["DELTA16.regulatory_and_market_events"] = _delta_event_readiness(
        "DELTA16.regulatory_and_market_events",
        delta16.get("regulatory_and_market_events"),
        source_ids=materialized_source_ids,
    )
    families["DELTA16.capital_and_ownership_events"] = _delta_event_readiness(
        "DELTA16.capital_and_ownership_events",
        delta16.get("capital_and_ownership_events"),
        source_ids=materialized_source_ids,
    )
    families["DELTA16.governance_and_leadership_events"] = _delta_event_readiness(
        "DELTA16.governance_and_leadership_events",
        delta16.get("governance_and_leadership_events"),
        source_ids=materialized_source_ids,
    )
    families["V16.reopening_decisions"] = _reopening_readiness(
        "V16.reopening_decisions",
        v16_refresh.get("reopening_decisions"),
    )
    families["V17.reopening_decisions"] = _reopening_readiness(
        "V17.reopening_decisions",
        v17_successor.get("reopening_decisions"),
    )

    blocker_counts: Counter[str] = Counter()
    family_summary: dict[str, dict[str, int]] = {}
    for family, records in families.items():
        for record in records:
            blocker_counts.update(record["blockers"])
        family_summary[family] = {
            "record_count": len(records),
            "ready_count": sum(record["state"] == READY for record in records),
            "blocked_count": sum(record["state"] == BLOCKED for record in records),
        }

    return {
        "state": "NONCANONICAL_MIGRATION_ANALYSIS",
        "release_authorized": False,
        "families": families,
        "family_summary": family_summary,
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "ready_record_count": sum(summary["ready_count"] for summary in family_summary.values()),
        "blocked_record_count": sum(summary["blocked_count"] for summary in family_summary.values()),
        "boundary": READINESS_BOUNDARY,
    }
