"""Deterministic review packet for the Gate-A human domain-review requirement.

Software selects representative predecessor/migration cases and freezes their identities.
It never supplies or infers the human disposition. Review responses belong in a separate
signed/adjudicated record after a reviewer inspects the packet.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .util import canonical_json_bytes, sha256_bytes

REVIEW_PACKET_BOUNDARY = (
    "Human-review input only. Software selects deterministic representative cases and required checks, "
    "but human disposition, reviewer identity, and review notes remain unset. Packet generation cannot "
    "approve migration, close Gate A, authorize publication, or establish substantive truth."
)

MIGRATION_MODES: dict[tuple[str, str], str] = {
    ("V14", "metadata"): "PRESERVED_RELEASE_LEVEL_STATE",
    ("V14", "methodology"): "PRESERVED_RELEASE_LEVEL_STATE",
    ("V14", "coverage"): "PRESERVED_RELEASE_LEVEL_STATE",
    ("V14", "organizations"): "PARTIAL_NATIVE_WITH_EXPLICIT_PRESERVATION",
    ("V14", "organization_resolution"): "GOVERNED_IDENTITY_HISTORY",
    ("V14", "regional_expansion"): "GOVERNED_COVERAGE_HISTORY",
    ("V14", "capital_and_ownership_events"): "NATIVE_EVENT",
    ("V14", "representative_model_records"): "GOVERNED_LEGACY_PAYLOAD",
    ("V14", "model_and_dataset_registry"): "GOVERNED_LEGACY_PAYLOAD",
    ("V14", "trial_site_relationships"): "GOVERNED_LEGACY_PAYLOAD",
    ("V14", "participant_authority_relationships"): "GOVERNED_LEGACY_PAYLOAD",
    ("V14", "supplier_dependency_relationships"): "GOVERNED_LEGACY_PAYLOAD",
    ("V14", "sources"): "NATIVE_SOURCE",
    ("V14", "data_quality"): "PRESERVED_RELEASE_LEVEL_STATE",
    ("V16", "metadata"): "PRESERVED_RELEASE_LEVEL_STATE",
    ("V16", "methodology"): "PRESERVED_RELEASE_LEVEL_STATE",
    ("V16", "baseline"): "PRESERVED_RELEASE_LEVEL_STATE",
    ("V16", "source_checks"): "PRESERVED_TRANSPORT_UNRESOLVED_OBSERVATION_EVIDENCE",
    ("V16", "new_sources"): "NATIVE_SOURCE",
    ("V16", "change_candidates"): "NATIVE_CANDIDATE",
    ("V16", "adjudicated_delta"): "VERIFIED_DUPLICATE_CONTAINER",
    ("V16", "reopening_decisions"): "GOVERNED_REOPENING_STATE",
    ("V16", "no_change_confirmations"): "GOVERNED_SCOPED_NO_CHANGE_STATE",
    ("V16", "withheld_claims"): "GOVERNED_WITHHELD_NONCLAIM",
    ("DELTA16", "regulatory_and_market_events"): "GOVERNED_LEGACY_PAYLOAD",
    ("DELTA16", "capital_and_ownership_events"): "GOVERNED_LEGACY_PAYLOAD",
    ("DELTA16", "model_records"): "GOVERNED_LEGACY_PAYLOAD",
    ("DELTA16", "supplier_dependency_relationships"): "GOVERNED_LEGACY_PAYLOAD",
    ("DELTA16", "governance_and_leadership_events"): "GOVERNED_LEGACY_PAYLOAD",
    ("V17", "metadata"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "baseline_reference"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "baseline_counts"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "delta_counts"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "successor_effective_counts"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "delta"): "VERIFIED_DUPLICATE_CONTAINER",
    ("V17", "reopening_decisions"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "provenance"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "predecessor_reference"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("V17", "assessment_successor_delta"): "VERIFIED_DUPLICATE_CONTAINER",
    ("PRIMA17", "metadata"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("PRIMA17", "predecessor_reference"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("PRIMA17", "event_delta"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("PRIMA17", "assessment_delta"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("PRIMA17", "source_delta"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("PRIMA17", "reopening_transition"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("PRIMA17", "bounded_system_record"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("PRIMA17", "prohibited_inferences"): "GOVERNED_SUCCESSOR_LINEAGE",
    ("SOURCE_REGISTER14", "$root"): "VERIFIED_DUPLICATE_SOURCE_REGISTER",
    ("MONITOR15", "$root"): "GOVERNED_OPERATIONAL_MONITOR_REGISTRY",
}

MODE_CHECKS: dict[str, tuple[str, ...]] = {
    "PARTIAL_NATIVE_WITH_EXPLICIT_PRESERVATION": (
        "Confirm exact predecessor organization identity and classification.",
        "Confirm native Entity fields contain identity only and do not promote descriptive subtype/claims.",
        "Confirm legacy/provenance/historical cases remain nonnative where required.",
    ),
    "NATIVE_SOURCE": (
        "Confirm source identity fields preserve predecessor semantics exactly.",
        "Confirm retrieval knowledge time is not promoted to publication time.",
        "Confirm nonnative predecessor evidence/claim fields remain traceable.",
    ),
    "NATIVE_EVENT": (
        "Confirm subject identity resolution is exact and source-backed.",
        "Confirm unresolved counterparties remain unresolved literals.",
        "Confirm date precision or absence is preserved without invention.",
        "Confirm claim boundary and evidence state are not strengthened.",
    ),
    "NATIVE_CANDIDATE": (
        "Confirm Candidate payload equals exact predecessor record.",
        "Confirm candidate class/status preserve predecessor change class/adjudication.",
        "Confirm free-text subject is not silently promoted to Entity identity.",
    ),
    "PRESERVED_TRANSPORT_UNRESOLVED_OBSERVATION_EVIDENCE": (
        "Confirm exact source ID, knowledge time, retrieval outcome, and digests are preserved.",
        "Confirm retrieval_method and requested_locator remain unresolved and unfilled.",
    ),
    "GOVERNED_IDENTITY_HISTORY": (
        "Confirm before/after verification semantics and rationale are preserved.",
        "Confirm verification_after reconciles to resulting predecessor organization state.",
    ),
    "GOVERNED_COVERAGE_HISTORY": (
        "Confirm acquisition/coverage action is not rewritten as organization identity.",
        "Confirm contemporaneous verification state is preserved even if later state changed.",
    ),
    "GOVERNED_REOPENING_STATE": (
        "Confirm decision, basis IDs, and required actions are exact.",
        "Confirm migration performs no assessment mutation.",
    ),
    "GOVERNED_SCOPED_NO_CHANGE_STATE": (
        "Confirm record remains scoped comparison evidence.",
        "Confirm no global absence or 'nothing changed' claim is introduced.",
    ),
    "GOVERNED_WITHHELD_NONCLAIM": (
        "Confirm withheld predecessor text remains a non-claim.",
        "Confirm no negative Assertion is generated.",
    ),
    "GOVERNED_SUCCESSOR_LINEAGE": (
        "Confirm predecessor/successor identity and hashes are exact.",
        "Confirm reopening transition and unchanged decisions preserve predecessor history.",
        "Confirm prohibited inferences and assessment non-mutation boundary are retained.",
    ),
    "VERIFIED_DUPLICATE_CONTAINER": (
        "Confirm duplicate payload is byte/structure-equivalent to its separately bound governing input.",
        "Confirm duplicate container is not double-materialized as new graph state.",
    ),
    "VERIFIED_DUPLICATE_SOURCE_REGISTER": (
        "Confirm Source Register equals the canonical V14 source array.",
        "Confirm register records are not materialized as duplicate Sources.",
    ),
    "GOVERNED_OPERATIONAL_MONITOR_REGISTRY": (
        "Confirm monitor/source identity is one-to-one.",
        "Confirm baseline URL/publisher/class/evidence/verification/boundary/retrieval values reconcile.",
        "Confirm monitoring policy is not substantive observatory truth.",
    ),
    "PRESERVED_RELEASE_LEVEL_STATE": (
        "Confirm release-level metadata/methodology/quality state is preserved exactly.",
        "Confirm it is not promoted into a substantive graph claim.",
    ),
    "GOVERNED_LEGACY_PAYLOAD": (
        "Confirm exact predecessor payload and Source references are preserved.",
        "Confirm documented native blocker is legitimate and no identity/semantic default was invented.",
    ),
}

REQUIRED_ORGANIZATION_REVIEW_CLASSES = frozenset(
    {
        "MATERIALIZE_ACTIVE_ENTITY",
        "LEGACY_IDENTITY_UNRESOLVED",
        "PROVENANCE_ONLY_NODE",
        "HISTORICAL_CURRENT_IDENTITY_UNRESOLVED",
    }
)


class ObservatoryGateAReviewError(ValueError):
    """Raised when a deterministic review packet cannot cover the frozen migration scope."""


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _stable_sample_indices(records: list[Any], *, count: int = 2) -> list[int]:
    if not records:
        return []
    ranked = sorted((_digest(record), index) for index, record in enumerate(records))
    selected = ranked[: min(count, len(ranked))]
    return sorted(index for _, index in selected)


def _one_per_field(records: list[Any], field: str) -> list[int]:
    grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        value = record.get(field)
        key = "<NULL>" if value is None else str(value)
        grouped[key].append((_digest(record), index))
    return sorted(min(candidates)[1] for candidates in grouped.values())


def _organization_classification_samples(checkpoint: dict[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    entity_migration = checkpoint.get("candidate", {}).get("core", {}).get("entity_migration", {})
    by_class: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for collection in ("predecessor_traces", "preserved_predecessor_records"):
        rows = entity_migration.get(collection, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            classification = row.get("classification")
            index = row.get("record_index")
            predecessor = row.get("predecessor_record")
            if isinstance(classification, str) and isinstance(index, int):
                by_class[classification].append((_digest(predecessor), index))
    missing = sorted(REQUIRED_ORGANIZATION_REVIEW_CLASSES - set(by_class))
    if missing:
        raise ObservatoryGateAReviewError(
            f"organization review packet lacks required migration classifications {missing}"
        )
    for classification in sorted(REQUIRED_ORGANIZATION_REVIEW_CLASSES):
        _, index = min(by_class[classification])
        result[index] = classification
    return result


def _review_unit(
    *,
    role: str,
    family: str,
    source_index: int | None,
    source_payload: Any,
    migration_mode: str,
    edge_case: str | None = None,
) -> dict[str, Any]:
    payload_digest = _digest(source_payload)
    index_label = "root" if source_index is None else str(source_index)
    review_id = f"REV-{role}-{family}-{index_label}-{payload_digest[:12]}"
    checks = MODE_CHECKS.get(migration_mode)
    if checks is None:
        raise ObservatoryGateAReviewError(f"No review checks defined for migration mode {migration_mode}")
    return {
        "review_id": review_id,
        "role": role,
        "family": family,
        "source_index": source_index,
        "source_payload_sha256": payload_digest,
        "source_payload": source_payload,
        "migration_mode": migration_mode,
        "edge_case": edge_case,
        "required_checks": list(checks),
        "human_disposition": None,
        "reviewer_identity": None,
        "review_notes": None,
        "reviewed_at": None,
        "boundary": REVIEW_PACKET_BOUNDARY,
    }


def build_gate_a_review_packet(
    *,
    checkpoint: dict[str, Any],
    v14_release: dict[str, Any],
    v16_refresh: dict[str, Any],
    delta16: dict[str, Any],
    v17_successor: dict[str, Any],
    prima17: dict[str, Any],
    source_register14: list[dict[str, Any]],
    monitor15: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic review packet that covers every frozen predecessor family and known edge case."""
    if checkpoint.get("representational_scope_complete") is not True:
        raise ObservatoryGateAReviewError("human review packet requires representationally complete checkpoint")
    if checkpoint.get("release_authorized") is not False or checkpoint.get("gate_a_complete") is not False:
        raise ObservatoryGateAReviewError("review packet requires noncanonical, incomplete checkpoint")

    role_payloads: dict[str, Any] = {
        "V14": v14_release,
        "V16": v16_refresh,
        "DELTA16": delta16,
        "V17": v17_successor,
        "PRIMA17": prima17,
        "SOURCE_REGISTER14": source_register14,
        "MONITOR15": monitor15,
    }
    expected = set(MIGRATION_MODES)
    observed: set[tuple[str, str]] = set()
    units: list[dict[str, Any]] = []
    organization_special = _organization_classification_samples(checkpoint)

    for role in ("V14", "V16", "DELTA16", "V17", "PRIMA17", "SOURCE_REGISTER14", "MONITOR15"):
        payload = role_payloads[role]
        if role in {"SOURCE_REGISTER14", "MONITOR15"}:
            families = [("$root", payload)]
        else:
            if not isinstance(payload, dict):
                raise ObservatoryGateAReviewError(f"{role} must be an object")
            families = sorted(payload.items())
        for family, family_payload in families:
            key = (role, family)
            mode = MIGRATION_MODES.get(key)
            if mode is None:
                raise ObservatoryGateAReviewError(f"Unreviewed predecessor review family {role}.{family}")
            observed.add(key)

            if isinstance(family_payload, list):
                if not family_payload:
                    units.append(
                        _review_unit(
                            role=role,
                            family=family,
                            source_index=None,
                            source_payload=[],
                            migration_mode=mode,
                            edge_case="EMPTY_FAMILY",
                        )
                    )
                    continue

                if key == ("V14", "organizations"):
                    for index in sorted(organization_special):
                        units.append(
                            _review_unit(
                                role=role,
                                family=family,
                                source_index=index,
                                source_payload=family_payload[index],
                                migration_mode=mode,
                                edge_case=organization_special[index],
                            )
                        )
                    continue

                if key == ("V14", "capital_and_ownership_events"):
                    selected = list(range(len(family_payload)))
                elif key in {
                    ("V16", "reopening_decisions"),
                    ("V16", "no_change_confirmations"),
                    ("V17", "reopening_decisions"),
                }:
                    selected = list(range(len(family_payload)))
                elif key == ("V14", "organization_resolution"):
                    selected = _one_per_field(family_payload, "disposition")
                elif key == ("V14", "regional_expansion"):
                    selected = _one_per_field(family_payload, "action")
                elif key == ("V16", "change_candidates"):
                    selected = sorted(
                        set(_one_per_field(family_payload, "change_class"))
                        | set(_one_per_field(family_payload, "adjudication"))
                    )
                elif key == ("V16", "new_sources"):
                    selected = _one_per_field(family_payload, "published")
                    selected = sorted(set(selected) | set(_stable_sample_indices(family_payload, count=2)))
                elif key == ("V16", "source_checks"):
                    selected = _stable_sample_indices(family_payload, count=min(3, len(family_payload)))
                elif key in {("MONITOR15", "$root"), ("SOURCE_REGISTER14", "$root")}:
                    selected = _stable_sample_indices(family_payload, count=min(3, len(family_payload)))
                else:
                    selected = _stable_sample_indices(family_payload, count=min(2, len(family_payload)))

                for index in selected:
                    edge_case = None
                    if key == ("V14", "capital_and_ownership_events"):
                        date = family_payload[index].get("date") if isinstance(family_payload[index], dict) else None
                        edge_case = (
                            "NULL_TIME"
                            if date is None
                            else ("YEAR_TIME" if isinstance(date, str) and len(date) == 4 else "DATE_TIME")
                        )
                    elif key == ("V16", "new_sources") and isinstance(family_payload[index], dict):
                        edge_case = (
                            "NULL_PUBLICATION_TIME"
                            if family_payload[index].get("published") is None
                            else "EXPLICIT_PUBLICATION_TIME"
                        )
                    elif key == ("V17", "reopening_decisions") and isinstance(family_payload[index], dict):
                        decision_id = family_payload[index].get("decision_id")
                        if decision_id == "ROP-17-001":
                            edge_case = "SUCCESSOR_REOPENING_DECISION"
                    units.append(
                        _review_unit(
                            role=role,
                            family=family,
                            source_index=index,
                            source_payload=family_payload[index],
                            migration_mode=mode,
                            edge_case=edge_case,
                        )
                    )
            else:
                units.append(
                    _review_unit(
                        role=role,
                        family=family,
                        source_index=None,
                        source_payload=family_payload,
                        migration_mode=mode,
                    )
                )

    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing or extra:
        raise ObservatoryGateAReviewError(f"review-family coverage mismatch: missing={missing}, extra={extra}")

    units = sorted(units, key=lambda item: item["review_id"])
    packet = {
        "schema_version": "1",
        "packet_type": "OBSERVATORY_V2_GATE_A_HUMAN_REVIEW_INPUT",
        "state": "PENDING_HUMAN_REVIEW",
        "release_authorized": False,
        "gate_a_complete": False,
        "software_approval_performed": False,
        "family_coverage_count": len(observed),
        "review_unit_count": len(units),
        "covered_families": [f"{role}.{family}" for role, family in sorted(observed)],
        "review_units": units,
        "boundary": REVIEW_PACKET_BOUNDARY,
    }
    packet["review_packet_sha256"] = _digest(
        {key: value for key, value in packet.items() if key != "review_packet_sha256"}
    )
    errors = verify_gate_a_review_packet(packet)
    if errors:
        raise ObservatoryGateAReviewError(f"generated review packet is invalid: {errors}")
    return packet


def verify_gate_a_review_packet(packet: dict[str, Any]) -> list[str]:
    """Verify deterministic packet integrity and confirm software did not pre-fill human adjudication."""
    errors: list[str] = []
    if packet.get("state") != "PENDING_HUMAN_REVIEW":
        errors.append("review packet state must remain PENDING_HUMAN_REVIEW")
    if packet.get("release_authorized") is not False or packet.get("gate_a_complete") is not False:
        errors.append("review packet must remain unauthorized and Gate-A incomplete")
    if packet.get("software_approval_performed") is not False:
        errors.append("software_approval_performed must remain false")
    if packet.get("boundary") != REVIEW_PACKET_BOUNDARY:
        errors.append("review packet boundary mismatch")

    units = packet.get("review_units")
    if not isinstance(units, list):
        return ["review_units must be an array"]
    if packet.get("review_unit_count") != len(units):
        errors.append("review_unit_count mismatch")
    ids: set[str] = set()
    covered: set[str] = set()
    organization_edges: set[str] = set()
    capital_edges: set[str] = set()
    v16_source_edges: set[str] = set()
    v17_reopening_edges: set[str] = set()
    for unit in units:
        if not isinstance(unit, dict):
            errors.append("review unit must be an object")
            continue
        review_id = unit.get("review_id")
        if not isinstance(review_id, str) or not review_id or review_id in ids:
            errors.append(f"duplicate or invalid review_id {review_id!r}")
        else:
            ids.add(review_id)
        role = unit.get("role")
        family = unit.get("family")
        if isinstance(role, str) and isinstance(family, str):
            covered.add(f"{role}.{family}")
        mode = unit.get("migration_mode")
        if not isinstance(mode, str) or mode not in MODE_CHECKS:
            errors.append(f"unknown review migration mode {mode!r}")
        if unit.get("source_payload_sha256") != _digest(unit.get("source_payload")):
            errors.append(f"review unit payload digest mismatch for {review_id}")
        if unit.get("human_disposition") is not None:
            errors.append(f"software prefilled human_disposition for {review_id}")
        if unit.get("reviewer_identity") is not None:
            errors.append(f"software prefilled reviewer_identity for {review_id}")
        if unit.get("review_notes") is not None or unit.get("reviewed_at") is not None:
            errors.append(f"software prefilled human review metadata for {review_id}")
        if unit.get("boundary") != REVIEW_PACKET_BOUNDARY:
            errors.append(f"review unit boundary mismatch for {review_id}")

        edge = unit.get("edge_case")
        if role == "V14" and family == "organizations" and isinstance(edge, str):
            organization_edges.add(edge)
        if role == "V14" and family == "capital_and_ownership_events" and isinstance(edge, str):
            capital_edges.add(edge)
        if role == "V16" and family == "new_sources" and isinstance(edge, str):
            v16_source_edges.add(edge)
        if role == "V17" and family == "reopening_decisions" and isinstance(edge, str):
            v17_reopening_edges.add(edge)

    missing_org_edges = sorted(REQUIRED_ORGANIZATION_REVIEW_CLASSES - organization_edges)
    if missing_org_edges:
        errors.append(f"review packet missing organization migration edge cases {missing_org_edges}")
    if "YEAR_TIME" not in capital_edges or "NULL_TIME" not in capital_edges:
        errors.append("review packet must include YEAR_TIME and NULL_TIME capital-event cases")
    if "NULL_PUBLICATION_TIME" not in v16_source_edges or "EXPLICIT_PUBLICATION_TIME" not in v16_source_edges:
        errors.append("review packet must include null and explicit v1.6 publication-time cases")
    if "SUCCESSOR_REOPENING_DECISION" not in v17_reopening_edges:
        errors.append("review packet must include ROP-17-001 successor reopening decision")

    declared_covered = packet.get("covered_families")
    if not isinstance(declared_covered, list) or set(declared_covered) != covered:
        errors.append("covered_families mismatch")
    if packet.get("family_coverage_count") != len(covered):
        errors.append("family_coverage_count mismatch")
    expected_digest = _digest({key: value for key, value in packet.items() if key != "review_packet_sha256"})
    if packet.get("review_packet_sha256") != expected_digest:
        errors.append("review_packet_sha256 mismatch")
    return sorted(set(errors))
