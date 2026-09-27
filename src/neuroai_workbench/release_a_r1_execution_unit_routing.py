"""Release-A R1 execution-unit routing for the frozen R1.4 worklist.

R1.4 freezes the decision-relevant review population. R1.5 shows that the
historical capture rows mix product/offering candidates with source/query
surfaces and literature/record probes. This module binds those two states and
routes every R1.4 work item to execution semantics that preserve the empirical
unit instead of treating every selected cluster as a product candidate.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.product_discovery_frames import (
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    ProductDiscoveryError,
)
from neuroai_workbench.release_a_r1_candidate_unit_audit import (
    AUDIT_SHA256 as R1_5_AUDIT_SHA256,
)
from neuroai_workbench.release_a_r1_candidate_unit_audit import (
    RULE_SHA256 as R1_5_RULE_SHA256,
)
from neuroai_workbench.release_a_r1_candidate_unit_audit import (
    classify_capture_unit,
    load_candidate_unit_audit_rule,
)
from neuroai_workbench.release_a_r1_decision_resolution import (
    WORKLIST_SHA256 as R1_4_WORKLIST_SHA256,
)
from neuroai_workbench.release_a_r1_decision_resolution import (
    load_decision_resolution_worklist,
)
from neuroai_workbench.release_a_r1_resolution import (
    DISCOVERY_RESOURCE_PACKAGE,
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)

RULE_RESOURCE = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_RULE.v1.0.json"
ROUTING_RESOURCE = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_CHECKPOINT.v1.0.json"

RULE_ID = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_RULE_v1.0"
ROUTING_ID = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_CHECKPOINT_v1.0"
RULE_SHA256 = "98ece7715e8bd36c4e332db654366bd5d38931fac6fa44f97ac5b4a936068422"
ROUTING_SHA256 = "d55aa834ff482c7536c1f5b35c1c1eaadc9c1e4479c2ba5ca8b0113f6a32a06f"

SOURCE_WORKBENCH_MAIN_COMMIT = "f735259557bf867281f3ca0d7cb38af2d90fa640"
WORLD_TIME_CUTOFF = "2026-09-24"
KNOWLEDGE_TIME_CUTOFF = "2026-10-24T23:59:59Z"

EMPIRICAL_CANDIDATE_ADJUDICATION = "EMPIRICAL_CANDIDATE_ADJUDICATION"
SOURCE_SURFACE_RESOLUTION = "SOURCE_SURFACE_RESOLUTION"
LITERATURE_RECORD_EXTRACTION = "LITERATURE_RECORD_EXTRACTION"
MIXED_OR_UNRESOLVED_UNIT_REVIEW = "MIXED_OR_UNRESOLVED_UNIT_REVIEW"
A_P1_TEMPORAL_STATE_REVIEW = "A_P1_TEMPORAL_STATE_REVIEW"

EXECUTION_ROUTES = (
    EMPIRICAL_CANDIDATE_ADJUDICATION,
    SOURCE_SURFACE_RESOLUTION,
    LITERATURE_RECORD_EXTRACTION,
    MIXED_OR_UNRESOLVED_UNIT_REVIEW,
    A_P1_TEMPORAL_STATE_REVIEW,
)

UNIT_CLASS_TO_ROUTE = {
    "UNRESOLVED_EMPIRICAL_UNIT": EMPIRICAL_CANDIDATE_ADJUDICATION,
    "SOURCE_OR_QUERY_PROBE": SOURCE_SURFACE_RESOLUTION,
    "LITERATURE_OR_RECORD_PROBE": LITERATURE_RECORD_EXTRACTION,
    "OFFERING_CANDIDATE_OBJECT": MIXED_OR_UNRESOLVED_UNIT_REVIEW,
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


def _load(resource: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DISCOVERY_RESOURCE_PACKAGE).joinpath(resource).read_text(encoding="utf-8")),
    )


def validate_execution_unit_routing_rule(rule: Mapping[str, Any]) -> None:
    if rule.get("rule_id") != RULE_ID:
        raise ProductDiscoveryError("R1.6 execution-unit routing rule ID drift")
    if artifact_sha256(rule, digest_field="rule_sha256") != rule.get("rule_sha256"):
        raise ProductDiscoveryError("R1.6 execution-unit routing rule digest mismatch")
    if rule.get("rule_sha256") != RULE_SHA256:
        raise ProductDiscoveryError("R1.6 frozen routing rule digest drift")

    expected = {
        "status": "FROZEN",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "r1_4_worklist_sha256": R1_4_WORKLIST_SHA256,
        "r1_5_candidate_unit_rule_sha256": R1_5_RULE_SHA256,
        "r1_5_candidate_unit_checkpoint_sha256": R1_5_AUDIT_SHA256,
        "candidate_unit_to_execution_route": UNIT_CLASS_TO_ROUTE,
        "mixed_or_multiple_unit_classes_route": MIXED_OR_UNRESOLVED_UNIT_REVIEW,
        "temporal_work_item_route": A_P1_TEMPORAL_STATE_REVIEW,
    }
    for field, value in expected.items():
        if rule.get(field) != value:
            raise ProductDiscoveryError(f"R1.6 execution-unit routing {field} drift")

    if list(rule.get("source_surface_completion_states", [])) != [
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
        "SOURCE_SPECIFIC_FINITE_CARDINALITY_ESTABLISHED",
        "SOURCE_BARRIER_UNRESOLVED",
    ]:
        raise ProductDiscoveryError("R1.6 source-surface completion-state contract drift")

    if list(rule.get("literature_record_completion_states", [])) != [
        "RECORD_EXTRACTED_ZERO_OFFERING_LEADS",
        "RECORD_EXTRACTED_WITH_OFFERING_LEADS",
        "RECORD_EXTRACTION_UNRESOLVED",
    ]:
        raise ProductDiscoveryError("R1.6 literature-record completion-state contract drift")

    controls = cast(Mapping[str, Any], rule["execution_controls"])
    expected_controls = {
        "source_surface_itself_may_receive_product_include_exclude": False,
        "literature_record_itself_may_be_counted_as_product_candidate": False,
        "zero_extracted_leads_implies_global_source_exhaustion": False,
        "extracted_candidate_leads_require_append_only_successor": True,
        "extracted_candidate_leads_may_mutate_frozen_r1_4_worklist": False,
        "extracted_candidate_leads_may_allocate_canonical_identity": False,
        "empirical_candidate_terminal_or_finite_bound_dispositions_require_r1_4_human_review": True,
        "temporal_reviews_retain_r1_4_temporal_contract": True,
    }
    if dict(controls) != expected_controls:
        raise ProductDiscoveryError("R1.6 execution controls drift")

    finality = cast(Mapping[str, Any], rule["finality"])
    if not (
        finality.get("checkpoint_only_until_knowledge_window_disposition") is True
        and finality.get("final_rebind_after_knowledge_window_disposition_required") is True
        and finality.get("release_a_r1_passed") is False
        and finality.get("release_a_final_denominator_authorized") is False
        and finality.get("release_b_c_d_denominator_consumption_authorized") is False
        and finality.get("population_generalization_authority") is False
        and finality.get("publication_authority") is False
    ):
        raise ProductDiscoveryError("R1.6 finality boundary drift")


def load_execution_unit_routing_rule() -> dict[str, Any]:
    rule = _load(RULE_RESOURCE)
    validate_execution_unit_routing_rule(rule)
    return rule


def route_for_unit_classes(unit_classes: Sequence[str]) -> str:
    """Map constituent R1.5 unit classes to one fail-closed execution route."""

    unique = sorted(set(unit_classes))
    if len(unique) != 1:
        return MIXED_OR_UNRESOLVED_UNIT_REVIEW
    return UNIT_CLASS_TO_ROUTE.get(unique[0], MIXED_OR_UNRESOLVED_UNIT_REVIEW)


def _candidate_route_entry(
    work_item: Mapping[str, Any],
    *,
    records_by_capture_id: Mapping[str, Mapping[str, Any]],
    r1_5_rule: Mapping[str, Any],
) -> dict[str, Any]:
    capture_ids = [str(item) for item in cast(Sequence[str], work_item["capture_ids"])]
    records: list[Mapping[str, Any]] = []
    for capture_id in capture_ids:
        record = records_by_capture_id.get(capture_id)
        if record is None:
            raise ProductDiscoveryError(f"R1.6 work item references unknown capture ID: {capture_id}")
        records.append(record)

    classifications = [classify_capture_unit(record, r1_5_rule) for record in records]
    unit_classes = sorted({str(item["unit_class"]) for item in classifications})

    return {
        "work_item_id": work_item["work_item_id"],
        "work_item_type": work_item["work_item_type"],
        "candidate_cluster_id": work_item["candidate_cluster_id"],
        "execution_route": route_for_unit_classes(unit_classes),
        "constituent_unit_classes": unit_classes,
        "capture_ids": capture_ids,
        "frame_rounds": list(cast(Sequence[str], work_item["frame_rounds"])),
        "selection_reasons": list(cast(Sequence[str], work_item["selection_reasons"])),
        "could_change_marginal_yield_stop": bool(work_item["could_change_marginal_yield_stop"]),
        "could_change_a3_increment": bool(work_item["could_change_a3_increment"]),
        "could_change_a4_increment": bool(work_item["could_change_a4_increment"]),
        "could_change_a_p1_membership": True,
        "canonical_offering_id": work_item.get("canonical_offering_id"),
    }


def _temporal_route_entry(work_item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "work_item_id": work_item["work_item_id"],
        "work_item_type": work_item["work_item_type"],
        "candidate_cluster_id": None,
        "execution_route": A_P1_TEMPORAL_STATE_REVIEW,
        "constituent_unit_classes": [],
        "capture_ids": [],
        "frame_rounds": [],
        "selection_reasons": list(cast(Sequence[str], work_item["selection_reasons"])),
        "could_change_marginal_yield_stop": False,
        "could_change_a3_increment": False,
        "could_change_a4_increment": False,
        "could_change_a_p1_membership": True,
        "canonical_offering_id": work_item["canonical_offering_id"],
    }


def _decision_role_counts(route_table: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for route in EXECUTION_ROUTES:
        rows = [item for item in route_table if item["execution_route"] == route]
        result[route] = {
            "total": len(rows),
            "marginal_yield_sensitive": sum(bool(item["could_change_marginal_yield_stop"]) for item in rows),
            "a3_sensitive": sum(bool(item["could_change_a3_increment"]) for item in rows),
            "a4_sensitive": sum(bool(item["could_change_a4_increment"]) for item in rows),
            "a_p1_sensitive": sum(bool(item["could_change_a_p1_membership"]) for item in rows),
        }
    return result


def derive_execution_unit_routing() -> dict[str, Any]:
    rule = load_execution_unit_routing_rule()
    worklist = load_decision_resolution_worklist()
    if worklist["worklist_sha256"] != R1_4_WORKLIST_SHA256:
        raise ProductDiscoveryError("R1.6 does not bind the exact R1.4 worklist")

    manifest = load_r1_candidate_resolution_manifest()
    source_records = compile_r1_source_records(manifest)
    records_by_capture_id = {str(item["capture_id"]): item for item in source_records}
    if len(records_by_capture_id) != len(source_records):
        raise ProductDiscoveryError("R1.6 source records contain duplicate capture IDs")

    r1_5_rule = load_candidate_unit_audit_rule()
    route_table: list[dict[str, Any]] = []
    for work_item in cast(Sequence[Mapping[str, Any]], worklist["work_items"]):
        item_type = str(work_item["work_item_type"])
        if item_type == "CANDIDATE_CLUSTER_REVIEW":
            route_table.append(
                _candidate_route_entry(
                    work_item,
                    records_by_capture_id=records_by_capture_id,
                    r1_5_rule=r1_5_rule,
                )
            )
        elif item_type == "A_P1_TEMPORAL_STATE_REVIEW":
            route_table.append(_temporal_route_entry(work_item))
        else:
            raise ProductDiscoveryError(f"R1.6 unsupported R1.4 work item type: {item_type}")

    route_table.sort(key=lambda item: str(item["work_item_id"]))
    work_item_ids = [str(item["work_item_id"]) for item in route_table]
    if len(work_item_ids) != len(set(work_item_ids)):
        raise ProductDiscoveryError("R1.6 route table contains duplicate work item IDs")

    route_counter = Counter(str(item["execution_route"]) for item in route_table)
    route_counts = {route: route_counter[route] for route in EXECUTION_ROUTES}

    return {
        "routing_id": ROUTING_ID,
        "version": "1.0",
        "status": "CHECKPOINT_PRE_R1_4_SUBSTANTIVE_EXECUTION_AND_KNOWLEDGE_WINDOW_CLOSE",
        "assembled_on": "2026-09-27",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "rule_id": RULE_ID,
        "rule_sha256": RULE_SHA256,
        "r1_4_worklist_sha256": R1_4_WORKLIST_SHA256,
        "r1_5_candidate_unit_rule_sha256": R1_5_RULE_SHA256,
        "r1_5_candidate_unit_checkpoint_sha256": R1_5_AUDIT_SHA256,
        "work_item_count": len(route_table),
        "route_counts": route_counts,
        "decision_role_counts_by_route": _decision_role_counts(route_table),
        "route_table": route_table,
        "aggregate_execution_disposition": (
            "R1_4_WORKLIST_ROUTED_BY_EMPIRICAL_UNIT_EXECUTION_MAY_PROCEED_WITH_ROUTE_SPECIFIC_SEMANTICS"
        ),
        "final_rebind_requirement": (
            "Rebuild this routing checkpoint against any final R1.4/R1.5 successor state after the frozen knowledge "
            "window is disposed before final #414 or Release-A R1 authority."
        ),
        "authority_controls": {
            "substantive_product_adjudication_executed": False,
            "canonical_identity_allocated": False,
            "release_a_r1_passed": False,
            "release_a_final_denominator_authorized": False,
            "release_b_c_d_denominator_consumption_authorized": False,
            "population_generalization_authority": False,
            "publication_authority": False,
        },
        "boundary": (
            "This checkpoint routes the exact frozen R1.4 work population into empirical candidate adjudication, "
            "source-surface resolution, literature-record extraction and temporal review. It does not itself resolve "
            "any item or change the historical A2/R1.4/R1.5 evidence."
        ),
    }


def validate_execution_unit_routing(routing: Mapping[str, Any]) -> None:
    if routing.get("routing_id") != ROUTING_ID:
        raise ProductDiscoveryError("R1.6 execution-unit routing ID drift")
    if artifact_sha256(routing, digest_field="routing_sha256") != routing.get("routing_sha256"):
        raise ProductDiscoveryError("R1.6 execution-unit routing digest mismatch")
    if routing.get("routing_sha256") != ROUTING_SHA256:
        raise ProductDiscoveryError("R1.6 frozen routing digest drift")

    materialized = {key: value for key, value in routing.items() if key != "routing_sha256"}
    if materialized != derive_execution_unit_routing():
        raise ProductDiscoveryError("R1.6 routing checkpoint does not reproduce from frozen inputs")

    route_table = cast(Sequence[Mapping[str, Any]], routing["route_table"])
    for item in route_table:
        route = str(item["execution_route"])
        unit_classes = set(cast(Sequence[str], item["constituent_unit_classes"]))
        if route == SOURCE_SURFACE_RESOLUTION and unit_classes != {"SOURCE_OR_QUERY_PROBE"}:
            raise ProductDiscoveryError("R1.6 source route contains a non-source empirical unit")
        if route == LITERATURE_RECORD_EXTRACTION and unit_classes != {"LITERATURE_OR_RECORD_PROBE"}:
            raise ProductDiscoveryError("R1.6 literature route contains a non-record empirical unit")
        if route == EMPIRICAL_CANDIDATE_ADJUDICATION and unit_classes != {"UNRESOLVED_EMPIRICAL_UNIT"}:
            raise ProductDiscoveryError("R1.6 candidate route contains a non-candidate empirical unit")
        if route == A_P1_TEMPORAL_STATE_REVIEW and unit_classes:
            raise ProductDiscoveryError("R1.6 temporal route must not acquire capture-unit classes")


def load_execution_unit_routing() -> dict[str, Any]:
    routing = _load(ROUTING_RESOURCE)
    validate_execution_unit_routing(routing)
    return routing
