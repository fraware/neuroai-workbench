"""Release-A R1.7 append-only route-execution ledger contract.

R1.6 routes the frozen R1.4 work population by empirical unit. This module
freezes how source-surface and literature-record execution records are appended,
superseded, conflict-checked, and aggregated before substantive R1.7 execution
is committed.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.product_discovery_frames import (
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    ProductDiscoveryError,
)
from neuroai_workbench.release_a_r1_execution_unit_routing import (
    KNOWLEDGE_TIME_CUTOFF,
    LITERATURE_RECORD_EXTRACTION,
    ROUTING_SHA256 as R1_6_ROUTING_SHA256,
    RULE_SHA256 as R1_6_RULE_SHA256,
    SOURCE_SURFACE_RESOLUTION,
    WORLD_TIME_CUTOFF,
    load_execution_unit_routing,
    validate_execution_unit_routing,
    validate_route_execution_record,
)
from neuroai_workbench.release_a_r1_resolution import DISCOVERY_RESOURCE_PACKAGE

RULE_RESOURCE = "RELEASE_A_R1_ROUTE_EXECUTION_LEDGER_RULE.v1.0.json"
RULE_ID = "RELEASE_A_R1_ROUTE_EXECUTION_LEDGER_RULE_v1.0"
RULE_SHA256 = "3da55f31c6f5a9072b63a5f50f8aadde6359045cff905c41e150c10c60731c36"
SOURCE_WORKBENCH_MAIN_COMMIT = "b00fa51af314277ef154af787cb850151cfaf1f8"

GOVERNED_ROUTES = (SOURCE_SURFACE_RESOLUTION, LITERATURE_RECORD_EXTRACTION)
EXPECTED_WORK_ITEM_COUNT = 192
EXPECTED_CAPTURE_COUNT = 247

INCOMPATIBLE_PROPOSITION_SETS = {
    SOURCE_SURFACE_RESOLUTION: (
        frozenset({"SOURCE_QUERY_ZERO_LEADS", "SOURCE_QUERY_WITH_LEADS"}),
        frozenset({"SOURCE_BARRIER_UNRESOLVED", "SOURCE_QUERY_ZERO_LEADS"}),
        frozenset({"SOURCE_BARRIER_UNRESOLVED", "SOURCE_QUERY_WITH_LEADS"}),
        frozenset({"SOURCE_BARRIER_UNRESOLVED", "SOURCE_SCOPE_EXHAUSTED"}),
        frozenset({"SOURCE_BARRIER_UNRESOLVED", "SOURCE_FINITE_CARDINALITY_ESTABLISHED"}),
    ),
    LITERATURE_RECORD_EXTRACTION: (
        frozenset({"RECORD_ZERO_OFFERING_LEADS", "RECORD_WITH_OFFERING_LEADS"}),
        frozenset({"RECORD_EXTRACTION_UNRESOLVED", "RECORD_ZERO_OFFERING_LEADS"}),
        frozenset({"RECORD_EXTRACTION_UNRESOLVED", "RECORD_WITH_OFFERING_LEADS"}),
    ),
}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def artifact_sha256(value: Mapping[str, Any], *, digest_field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != digest_field})


def _load_rule() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DISCOVERY_RESOURCE_PACKAGE).joinpath(RULE_RESOURCE).read_text(encoding="utf-8")),
    )


def validate_route_execution_ledger_rule(rule: Mapping[str, Any]) -> None:
    if rule.get("rule_id") != RULE_ID:
        raise ProductDiscoveryError("R1.7 route-execution ledger rule ID drift")
    if artifact_sha256(rule, digest_field="rule_sha256") != rule.get("rule_sha256"):
        raise ProductDiscoveryError("R1.7 route-execution ledger rule digest mismatch")
    if rule.get("rule_sha256") != RULE_SHA256:
        raise ProductDiscoveryError("R1.7 frozen ledger rule digest drift")

    expected = {
        "status": "FROZEN_PRE_EXECUTION",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "r1_6_rule_sha256": R1_6_RULE_SHA256,
        "r1_6_routing_sha256": R1_6_ROUTING_SHA256,
        "governed_execution_routes": list(GOVERNED_ROUTES),
        "expected_work_item_count": EXPECTED_WORK_ITEM_COUNT,
        "expected_capture_count": EXPECTED_CAPTURE_COUNT,
    }
    for field, value in expected.items():
        if rule.get(field) != value:
            raise ProductDiscoveryError(f"R1.7 route-execution ledger {field} drift")

    schema = cast(Mapping[str, Any], rule["ledger_entry_schema"])
    expected_schema = {
        "required_fields": [
            "ledger_entry_id",
            "route_execution_record",
            "supersedes_ledger_entry_ids",
        ],
        "additional_fields_allowed": False,
        "ledger_entry_id_content_bound": True,
        "supersedes_ledger_entry_ids_must_reference_prior_entries": True,
        "supersession_must_preserve_work_item_and_route": True,
        "supersession_requires_capture_overlap": True,
        "supersession_must_cover_all_superseded_captures": True,
    }
    if dict(schema) != expected_schema:
        raise ProductDiscoveryError("R1.7 ledger-entry schema drift")

    aggregation = cast(Mapping[str, Any], rule["aggregation_contract"])
    expected_aggregation = {
        "last_write_wins": False,
        "partial_records_may_establish_work_item_completion": False,
        "full_coverage_completion_record_required": True,
        "at_most_one_active_completion_record_per_work_item": True,
        "overlapping_active_records_must_be_proposition_compatible": True,
        "conflicting_active_records_fail_closed": True,
        "explicit_supersession_required_to_resolve_conflict": True,
        "active_entry_definition": "ENTRY_NOT_SUPERSEDED_BY_ANY_LATER_VALID_ENTRY",
        "historical_entries_remain_append_only": True,
    }
    if dict(aggregation) != expected_aggregation:
        raise ProductDiscoveryError("R1.7 aggregation contract drift")

    declared_conflicts = cast(Mapping[str, Any], rule["incompatible_proposition_sets"])
    expected_conflicts = {
        route: [sorted(pair) for pair in INCOMPATIBLE_PROPOSITION_SETS[route]] for route in GOVERNED_ROUTES
    }
    normalized_declared = {
        route: [
            sorted(str(value) for value in pair) for pair in cast(Sequence[Sequence[str]], declared_conflicts[route])
        ]
        for route in GOVERNED_ROUTES
    }
    if normalized_declared != expected_conflicts:
        raise ProductDiscoveryError("R1.7 proposition-conflict contract drift")

    lead_contract = cast(Mapping[str, Any], rule["extracted_lead_contract"])
    if not (
        lead_contract.get("canonical_identity_allocation") is False
        and lead_contract.get("frozen_r1_4_worklist_mutation") is False
        and lead_contract.get("historical_lead_provenance_append_only") is True
        and lead_contract.get("active_lead_ledger_deduplicates_by_lead_id") is True
        and lead_contract.get("repeated_leads_from_distinct_source_provenance_remain_distinct") is True
        and lead_contract.get("conflicting_payload_for_same_lead_id_fails_closed") is True
        and lead_contract.get("lead_support_status_derived_from_active_entries") is True
    ):
        raise ProductDiscoveryError("R1.7 extracted-lead contract drift")

    completion = cast(Mapping[str, Any], rule["completion_contract"])
    expected_completion = {
        "source_scope_exhaustion_requires_human_review": True,
        "finite_cardinality_requires_human_review": True,
        "source_scope_exhaustion_requires_per_capture_support": True,
        "finite_cardinality_requires_per_capture_support": True,
        "zero_lead_never_implies_global_completeness": True,
        "unresolved_barriers_remain_explicit": True,
    }
    if dict(completion) != expected_completion:
        raise ProductDiscoveryError("R1.7 completion contract drift")

    finality = cast(Mapping[str, Any], rule["finality"])
    if not (
        finality.get("substantive_route_execution_performed") is False
        and finality.get("empirical_candidate_adjudication_performed") is False
        and finality.get("temporal_state_review_performed") is False
        and finality.get("canonical_identity_allocated") is False
        and finality.get("release_a_r1_passed") is False
        and finality.get("release_a_final_denominator_authorized") is False
        and finality.get("release_b_c_d_denominator_consumption_authorized") is False
        and finality.get("population_generalization_authority") is False
        and finality.get("publication_authority") is False
    ):
        raise ProductDiscoveryError("R1.7 finality boundary drift")


def load_route_execution_ledger_rule() -> dict[str, Any]:
    rule = _load_rule()
    validate_route_execution_ledger_rule(rule)
    return rule


def derive_execution_population(
    routing_checkpoint: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    load_route_execution_ledger_rule()
    routing = load_execution_unit_routing() if routing_checkpoint is None else routing_checkpoint
    if routing_checkpoint is not None:
        validate_execution_unit_routing(routing)
    rows = []
    for item in cast(Sequence[Mapping[str, Any]], routing["route_table"]):
        route = str(item["execution_route"])
        if route not in GOVERNED_ROUTES:
            continue
        rows.append(
            {
                "work_item_id": str(item["work_item_id"]),
                "execution_route": route,
                "capture_ids": [str(value) for value in cast(Sequence[str], item["capture_ids"])],
                "could_change_marginal_yield_stop": bool(item["could_change_marginal_yield_stop"]),
                "could_change_a3_increment": bool(item["could_change_a3_increment"]),
                "could_change_a4_increment": bool(item["could_change_a4_increment"]),
                "could_change_a_p1_membership": bool(item["could_change_a_p1_membership"]),
            }
        )

    if len(rows) != EXPECTED_WORK_ITEM_COUNT:
        raise ProductDiscoveryError("R1.7 execution population work-item count drift")
    capture_count = sum(len(item["capture_ids"]) for item in rows)
    if capture_count != EXPECTED_CAPTURE_COUNT:
        raise ProductDiscoveryError("R1.7 execution population capture count drift")
    return rows


def ledger_entry_id(entry: Mapping[str, Any]) -> str:
    material = {key: value for key, value in entry.items() if key != "ledger_entry_id"}
    return "R1LEDGER-" + canonical_sha256(material)


def _entry_record(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    record = entry.get("route_execution_record")
    if not isinstance(record, Mapping):
        raise ProductDiscoveryError("R1.7 ledger entry requires route_execution_record")
    return cast(Mapping[str, Any], record)


def validate_ledger_entry(
    entry: Mapping[str, Any],
    *,
    routing_checkpoint: Mapping[str, Any] | None = None,
) -> None:
    required = {"ledger_entry_id", "route_execution_record", "supersedes_ledger_entry_ids"}
    if set(entry) != required:
        raise ProductDiscoveryError("R1.7 ledger entry fields drift")
    if entry.get("ledger_entry_id") != ledger_entry_id(entry):
        raise ProductDiscoveryError("R1.7 ledger_entry_id does not match deterministic content")

    record = _entry_record(entry)
    route = str(record.get("execution_route"))
    if route not in GOVERNED_ROUTES:
        raise ProductDiscoveryError("R1.7 ledger entry route is outside the governed source/record population")
    if routing_checkpoint is not None:
        validate_execution_unit_routing(routing_checkpoint)
    validate_route_execution_record(record, routing_checkpoint=routing_checkpoint)

    supersedes = entry.get("supersedes_ledger_entry_ids")
    if not isinstance(supersedes, list):
        raise ProductDiscoveryError("R1.7 supersedes_ledger_entry_ids must be a list")
    values = [str(value) for value in supersedes]
    if values != sorted(set(values)):
        raise ProductDiscoveryError("R1.7 supersedes_ledger_entry_ids must be unique and canonical")


def _propositions_by_capture(record: Mapping[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for evidence in cast(Sequence[Mapping[str, Any]], record["evidence"]):
        capture_id = str(evidence["capture_id"])
        result[capture_id].update(str(value) for value in cast(Sequence[str], evidence["supported_propositions"]))
    return dict(result)


def _assert_no_active_conflicts(active_entries: Sequence[Mapping[str, Any]]) -> None:
    propositions: dict[tuple[str, str], set[str]] = defaultdict(set)
    route_by_work_item: dict[str, str] = {}

    for entry in active_entries:
        record = _entry_record(entry)
        work_item_id = str(record["work_item_id"])
        route = str(record["execution_route"])
        route_by_work_item[work_item_id] = route
        for capture_id, values in _propositions_by_capture(record).items():
            propositions[(work_item_id, capture_id)].update(values)

    for (work_item_id, capture_id), values in propositions.items():
        route = route_by_work_item[work_item_id]
        for incompatible in INCOMPATIBLE_PROPOSITION_SETS[route]:
            if incompatible.issubset(values):
                raise ProductDiscoveryError(
                    f"R1.7 conflicting active propositions require explicit supersession: {work_item_id}/{capture_id}"
                )


def _derive_lead_state(
    entries: Sequence[Mapping[str, Any]],
    *,
    active_entry_ids: set[str],
) -> list[dict[str, Any]]:
    by_lead_id: dict[str, dict[str, Any]] = {}
    support_entries: dict[str, set[str]] = defaultdict(set)
    active_support_entries: dict[str, set[str]] = defaultdict(set)

    for entry in entries:
        entry_id = str(entry["ledger_entry_id"])
        record = _entry_record(entry)
        for lead in cast(Sequence[Mapping[str, Any]], record["extracted_leads"]):
            lead_id = str(lead["lead_id"])
            payload = dict(lead)
            previous = by_lead_id.get(lead_id)
            if previous is not None and previous != payload:
                raise ProductDiscoveryError("R1.7 identical lead_id has conflicting payload")
            by_lead_id[lead_id] = payload
            support_entries[lead_id].add(entry_id)
            if entry_id in active_entry_ids:
                active_support_entries[lead_id].add(entry_id)

    result = []
    for lead_id in sorted(by_lead_id):
        result.append(
            {
                **by_lead_id[lead_id],
                "supporting_ledger_entry_ids": sorted(support_entries[lead_id]),
                "active_supporting_ledger_entry_ids": sorted(active_support_entries[lead_id]),
                "active_support": bool(active_support_entries[lead_id]),
            }
        )
    return result


def derive_ledger_state(
    entries: Sequence[Mapping[str, Any]],
    *,
    routing_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    routing = load_execution_unit_routing() if routing_checkpoint is None else routing_checkpoint
    population = derive_execution_population(routing)
    population_by_id = {str(item["work_item_id"]): item for item in population}

    entry_by_id: dict[str, Mapping[str, Any]] = {}
    execution_record_ids: set[str] = set()
    superseded_ids: set[str] = set()

    for entry in entries:
        validate_ledger_entry(entry, routing_checkpoint=routing)
        entry_id = str(entry["ledger_entry_id"])
        if entry_id in entry_by_id:
            raise ProductDiscoveryError("R1.7 ledger contains duplicate ledger_entry_id")
        record = _entry_record(entry)
        execution_record_id = str(record["execution_record_id"])
        if execution_record_id in execution_record_ids:
            raise ProductDiscoveryError("R1.7 ledger contains duplicate execution_record_id")
        execution_record_ids.add(execution_record_id)

        work_item_id = str(record["work_item_id"])
        if work_item_id not in population_by_id:
            raise ProductDiscoveryError("R1.7 ledger entry work item is outside the frozen execution population")

        for superseded_id in cast(Sequence[str], entry["supersedes_ledger_entry_ids"]):
            prior = entry_by_id.get(str(superseded_id))
            if prior is None:
                raise ProductDiscoveryError("R1.7 supersession must reference a prior ledger entry")
            prior_record = _entry_record(prior)
            if prior_record["work_item_id"] != record["work_item_id"]:
                raise ProductDiscoveryError("R1.7 supersession cannot cross work-item identity")
            if prior_record["execution_route"] != record["execution_route"]:
                raise ProductDiscoveryError("R1.7 supersession cannot cross execution route")
            prior_captures = set(cast(Sequence[str], prior_record["covered_capture_ids"]))
            current_captures = set(cast(Sequence[str], record["covered_capture_ids"]))
            if prior_captures.isdisjoint(current_captures):
                raise ProductDiscoveryError("R1.7 supersession requires overlapping capture coverage")
            if not prior_captures.issubset(current_captures):
                raise ProductDiscoveryError("R1.7 supersession must cover every capture in the superseded entry")
            superseded_ids.add(str(superseded_id))

        entry_by_id[entry_id] = entry

    active_entries = [entry for entry_id, entry in entry_by_id.items() if entry_id not in superseded_ids]
    _assert_no_active_conflicts(active_entries)

    completion_by_work_item: dict[str, str] = {}
    for entry in active_entries:
        record = _entry_record(entry)
        if record["work_item_completion_claimed"] is not True:
            continue
        work_item_id = str(record["work_item_id"])
        if work_item_id in completion_by_work_item:
            raise ProductDiscoveryError("R1.7 work item has multiple active completion records")
        expected_captures = list(cast(Sequence[str], population_by_id[work_item_id]["capture_ids"]))
        if list(cast(Sequence[str], record["covered_capture_ids"])) != expected_captures:
            raise ProductDiscoveryError("R1.7 active work-item completion must cover the full frozen capture set")
        completion_by_work_item[work_item_id] = str(entry["ledger_entry_id"])

    route_counts = Counter(str(_entry_record(entry)["execution_route"]) for entry in active_entries)
    lead_ledger = _derive_lead_state(
        entries, active_entry_ids={str(entry["ledger_entry_id"]) for entry in active_entries}
    )

    return {
        "frozen_work_item_count": len(population),
        "frozen_capture_count": sum(len(item["capture_ids"]) for item in population),
        "ledger_entry_count": len(entries),
        "active_ledger_entry_count": len(active_entries),
        "superseded_ledger_entry_count": len(superseded_ids),
        "completed_work_item_count": len(completion_by_work_item),
        "pending_work_item_count": len(population) - len(completion_by_work_item),
        "active_entry_count_by_route": {route: route_counts[route] for route in GOVERNED_ROUTES},
        "completion_entry_by_work_item": dict(sorted(completion_by_work_item.items())),
        "extracted_lead_count": len(lead_ledger),
        "active_extracted_lead_count": sum(bool(item["active_support"]) for item in lead_ledger),
        "extracted_lead_ledger": lead_ledger,
    }
