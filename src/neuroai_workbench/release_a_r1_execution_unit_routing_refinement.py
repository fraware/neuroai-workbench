"""Release-A R1.6.1 execution-unit routing refinement.

R1.5 intentionally grouped actual literature records and explicit empty-result
sentinels into one non-product empirical-unit class. R1.6 then assigned that
entire class to literature-record extraction. This successor preserves the
frozen R1.6 history while distinguishing record locators from zero-result
sentinels before R1.7 substantive execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.product_discovery_frames import (
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    ProductDiscoveryError,
)
from neuroai_workbench.release_a_r1_execution_unit_routing import (
    A_P1_TEMPORAL_STATE_REVIEW,
    EMPIRICAL_CANDIDATE_ADJUDICATION,
    KNOWLEDGE_TIME_CUTOFF,
    LITERATURE_RECORD_EXTRACTION,
    MIXED_OR_UNRESOLVED_UNIT_REVIEW,
    ROUTING_SHA256 as R1_6_ROUTING_SHA256,
    RULE_SHA256 as R1_6_RULE_SHA256,
    SOURCE_SURFACE_RESOLUTION,
    WORLD_TIME_CUTOFF,
    load_execution_unit_routing,
)
from neuroai_workbench.release_a_r1_resolution import (
    DISCOVERY_RESOURCE_PACKAGE,
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)

RULE_RESOURCE = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_RULE.v1.0.json"
CHECKPOINT_RESOURCE = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_CHECKPOINT.v1.0.json"

RULE_ID = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_RULE_v1.0"
CHECKPOINT_ID = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_REFINEMENT_CHECKPOINT_v1.0"
RULE_SHA256 = "60c89f6eae236c35228c64b5997e8175b1bbbda649c1e5b1b63b930d40ad2d94"
CHECKPOINT_SHA256 = "b12482468cf73f0e9c086f7b87d31caf482d67cb0f9ae4e75082cb1992edf3af"

SOURCE_WORKBENCH_MAIN_COMMIT = "b00fa51af314277ef154af787cb850151cfaf1f8"

ACTUAL_LITERATURE_RECORD = "ACTUAL_LITERATURE_RECORD"
EMPTY_LITERATURE_QUERY_SENTINEL = "EMPTY_LITERATURE_QUERY_SENTINEL"
EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL = "EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL"
UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE = (
    "UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE"
)
UNCHANGED_FROM_R1_6 = "UNCHANGED_FROM_R1_6"

EXECUTION_ROUTES = (
    EMPIRICAL_CANDIDATE_ADJUDICATION,
    SOURCE_SURFACE_RESOLUTION,
    LITERATURE_RECORD_EXTRACTION,
    MIXED_OR_UNRESOLVED_UNIT_REVIEW,
    A_P1_TEMPORAL_STATE_REVIEW,
)

EXPECTED_WORK_ITEM_COUNTS_BY_ROUTE = {
    EMPIRICAL_CANDIDATE_ADJUDICATION: 76,
    SOURCE_SURFACE_RESOLUTION: 171,
    LITERATURE_RECORD_EXTRACTION: 21,
    MIXED_OR_UNRESOLVED_UNIT_REVIEW: 0,
    A_P1_TEMPORAL_STATE_REVIEW: 2,
}
EXPECTED_CAPTURE_COUNTS_BY_ROUTE = {
    EMPIRICAL_CANDIDATE_ADJUDICATION: 142,
    SOURCE_SURFACE_RESOLUTION: 226,
    LITERATURE_RECORD_EXTRACTION: 21,
    MIXED_OR_UNRESOLVED_UNIT_REVIEW: 0,
    A_P1_TEMPORAL_STATE_REVIEW: 0,
}
EXPECTED_REFINED_SUBTYPE_COUNTS = {
    ACTUAL_LITERATURE_RECORD: {"work_items": 21, "captures": 21},
    EMPTY_LITERATURE_QUERY_SENTINEL: {"work_items": 11, "captures": 11},
    EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL: {"work_items": 2, "captures": 6},
    UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE: {"work_items": 0, "captures": 0},
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
    return canonical_sha256(
        {key: item for key, item in value.items() if key != digest_field}
    )


def _load(resource: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files(DISCOVERY_RESOURCE_PACKAGE)
            .joinpath(resource)
            .read_text(encoding="utf-8")
        ),
    )


def validate_routing_refinement_rule(rule: Mapping[str, Any]) -> None:
    if rule.get("rule_id") != RULE_ID:
        raise ProductDiscoveryError("R1.6.1 routing-refinement rule ID drift")
    if artifact_sha256(rule, digest_field="rule_sha256") != rule.get("rule_sha256"):
        raise ProductDiscoveryError("R1.6.1 routing-refinement rule digest mismatch")
    if rule.get("rule_sha256") != RULE_SHA256:
        raise ProductDiscoveryError("R1.6.1 frozen rule digest drift")

    expected = {
        "status": "FROZEN_PRE_R1_7_EXECUTION",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "r1_6_rule_sha256": R1_6_RULE_SHA256,
        "r1_6_routing_sha256": R1_6_ROUTING_SHA256,
        "expected_work_item_counts_by_route": EXPECTED_WORK_ITEM_COUNTS_BY_ROUTE,
        "expected_capture_counts_by_route": EXPECTED_CAPTURE_COUNTS_BY_ROUTE,
        "expected_refined_predecessor_subtype_counts": EXPECTED_REFINED_SUBTYPE_COUNTS,
    }
    for field, value in expected.items():
        if rule.get(field) != value:
            raise ProductDiscoveryError(f"R1.6.1 routing-refinement {field} drift")

    refinement = cast(Mapping[str, Any], rule["refinement_contract"])
    expected_refinement = {
        "predecessor_route_to_refine": LITERATURE_RECORD_EXTRACTION,
        "actual_literature_record_label_pattern": r"^lit-[0-9]+$",
        "empty_literature_query_label_pattern": r"^empty-europepmc",
        "empty_trial_publication_query_label_pattern": r"^empty-trial-lit",
        "actual_literature_record_subtype": ACTUAL_LITERATURE_RECORD,
        "empty_literature_query_subtype": EMPTY_LITERATURE_QUERY_SENTINEL,
        "empty_trial_publication_query_subtype": (
            EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL
        ),
        "unresolved_or_mixed_subtype": UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE,
        "actual_literature_record_route": LITERATURE_RECORD_EXTRACTION,
        "empty_query_sentinel_route": SOURCE_SURFACE_RESOLUTION,
        "unresolved_or_mixed_route": MIXED_OR_UNRESOLVED_UNIT_REVIEW,
        "non_literature_r1_6_routes_preserved": True,
        "product_objecthood_inference_from_label_prohibited": True,
        "refinement_distinguishes_record_locator_from_explicit_zero_result_sentinel_only": True,
    }
    if dict(refinement) != expected_refinement:
        raise ProductDiscoveryError("R1.6.1 refinement contract drift")

    semantics = cast(Mapping[str, Any], rule["execution_semantics"])
    expected_semantics = {
        "empty_query_sentinel_is_document_record": False,
        "empty_query_sentinel_is_historical_zero_result_observation": True,
        "empty_query_sentinel_reexecution_uses_source_query_semantics": True,
        "zero_result_reexecution_implies_historical_absence": False,
        "zero_result_reexecution_implies_source_exhaustion": False,
        "actual_literature_record_requires_record_extraction": True,
        "source_exhaustion_or_finite_cardinality_requires_human_review": True,
        "canonical_identity_allocation": False,
    }
    if dict(semantics) != expected_semantics:
        raise ProductDiscoveryError("R1.6.1 execution-semantics drift")

    finality = cast(Mapping[str, Any], rule["finality"])
    if not (
        finality.get("checkpoint_only") is True
        and finality.get("substantive_route_execution_performed") is False
        and finality.get("empirical_candidate_adjudication_performed") is False
        and finality.get("temporal_state_review_performed") is False
        and finality.get("canonical_identity_allocated") is False
        and finality.get("release_a_r1_passed") is False
        and finality.get("release_a_final_denominator_authorized") is False
        and finality.get("release_b_c_d_denominator_consumption_authorized") is False
        and finality.get("population_generalization_authority") is False
        and finality.get("publication_authority") is False
    ):
        raise ProductDiscoveryError("R1.6.1 finality boundary drift")


def load_routing_refinement_rule() -> dict[str, Any]:
    rule = _load(RULE_RESOURCE)
    validate_routing_refinement_rule(rule)
    return rule


def _literature_probe_subtype(
    normalized_candidate_label: str,
    rule: Mapping[str, Any],
) -> str:
    refinement = cast(Mapping[str, Any], rule["refinement_contract"])
    label = normalized_candidate_label.lower()

    if re.fullmatch(
        str(refinement["actual_literature_record_label_pattern"]),
        label,
    ):
        return ACTUAL_LITERATURE_RECORD
    if re.search(
        str(refinement["empty_literature_query_label_pattern"]),
        label,
    ):
        return EMPTY_LITERATURE_QUERY_SENTINEL
    if re.search(
        str(refinement["empty_trial_publication_query_label_pattern"]),
        label,
    ):
        return EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL
    return UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE


def _refined_route_for_subtypes(subtypes: Sequence[str]) -> str:
    unique = set(subtypes)
    if unique == {ACTUAL_LITERATURE_RECORD}:
        return LITERATURE_RECORD_EXTRACTION
    if unique in (
        {EMPTY_LITERATURE_QUERY_SENTINEL},
        {EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL},
    ):
        return SOURCE_SURFACE_RESOLUTION
    return MIXED_OR_UNRESOLVED_UNIT_REVIEW


def derive_routing_refinement() -> dict[str, Any]:
    rule = load_routing_refinement_rule()
    predecessor = load_execution_unit_routing()
    if predecessor["routing_sha256"] != R1_6_ROUTING_SHA256:
        raise ProductDiscoveryError("R1.6.1 does not bind the exact R1.6 checkpoint")

    manifest = load_r1_candidate_resolution_manifest()
    source_records = compile_r1_source_records(manifest)
    records_by_capture_id = {
        str(record["capture_id"]): record for record in source_records
    }
    if len(records_by_capture_id) != len(source_records):
        raise ProductDiscoveryError("R1.6.1 source records contain duplicate capture IDs")

    route_table: list[dict[str, Any]] = []
    for predecessor_item in cast(
        Sequence[Mapping[str, Any]],
        predecessor["route_table"],
    ):
        item = dict(predecessor_item)
        predecessor_route = str(predecessor_item["execution_route"])
        item["r1_6_execution_route"] = predecessor_route

        if predecessor_route != LITERATURE_RECORD_EXTRACTION:
            item["execution_subtype"] = UNCHANGED_FROM_R1_6
            route_table.append(item)
            continue

        capture_ids = [
            str(value)
            for value in cast(Sequence[str], predecessor_item["capture_ids"])
        ]
        subtypes: list[str] = []
        for capture_id in capture_ids:
            source_record = records_by_capture_id.get(capture_id)
            if source_record is None:
                raise ProductDiscoveryError(
                    f"R1.6.1 predecessor references unknown capture ID: {capture_id}"
                )
            subtypes.append(
                _literature_probe_subtype(
                    str(source_record["normalized_candidate_label"]),
                    rule,
                )
            )

        unique_subtypes = sorted(set(subtypes))
        item["execution_subtype"] = (
            unique_subtypes[0]
            if len(unique_subtypes) == 1
            else UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE
        )
        item["execution_route"] = _refined_route_for_subtypes(unique_subtypes)
        route_table.append(item)

    predecessor_ids = [
        str(item["work_item_id"])
        for item in cast(Sequence[Mapping[str, Any]], predecessor["route_table"])
    ]
    refined_ids = [str(item["work_item_id"]) for item in route_table]
    if refined_ids != predecessor_ids:
        raise ProductDiscoveryError("R1.6.1 must preserve exact R1.6 work-item order")

    route_counts = Counter(str(item["execution_route"]) for item in route_table)
    work_item_counts_by_route = {
        route: route_counts[route] for route in EXECUTION_ROUTES
    }
    capture_counts_by_route = {
        route: sum(
            len(cast(Sequence[str], item["capture_ids"]))
            for item in route_table
            if item["execution_route"] == route
        )
        for route in EXECUTION_ROUTES
    }

    subtype_counts = {
        subtype: {
            "work_items": sum(
                item["execution_subtype"] == subtype for item in route_table
            ),
            "captures": sum(
                len(cast(Sequence[str], item["capture_ids"]))
                for item in route_table
                if item["execution_subtype"] == subtype
            ),
        }
        for subtype in EXPECTED_REFINED_SUBTYPE_COUNTS
    }

    changed_items = [
        item
        for item in route_table
        if item["execution_route"] != item["r1_6_execution_route"]
    ]

    return {
        "checkpoint_id": CHECKPOINT_ID,
        "version": "1.0",
        "status": "CHECKPOINT_PRE_R1_7_EXECUTION",
        "assembled_on": "2026-09-28",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "rule_id": RULE_ID,
        "rule_sha256": RULE_SHA256,
        "r1_6_rule_sha256": R1_6_RULE_SHA256,
        "r1_6_routing_sha256": R1_6_ROUTING_SHA256,
        "work_item_count": len(route_table),
        "capture_count": sum(
            len(cast(Sequence[str], item["capture_ids"])) for item in route_table
        ),
        "work_item_counts_by_route": work_item_counts_by_route,
        "capture_counts_by_route": capture_counts_by_route,
        "refined_predecessor_subtype_counts": subtype_counts,
        "changed_work_item_count": len(changed_items),
        "changed_capture_count": sum(
            len(cast(Sequence[str], item["capture_ids"])) for item in changed_items
        ),
        "route_table": route_table,
        "aggregate_disposition": (
            "R1_6_EXECUTION_ROUTING_REFINED_FOR_RECORD_VS_EMPTY_QUERY_SENTINEL"
        ),
        "authority_controls": {
            "substantive_route_execution_performed": False,
            "canonical_identity_allocated": False,
            "release_a_r1_passed": False,
            "release_a_final_denominator_authorized": False,
            "release_b_c_d_denominator_consumption_authorized": False,
            "population_generalization_authority": False,
            "publication_authority": False,
        },
        "boundary": (
            "This checkpoint preserves every frozen R1.6 work item and capture "
            "while refining only execution routing for actual literature records "
            "versus explicit empty-query sentinels."
        ),
    }


def validate_routing_refinement(checkpoint: Mapping[str, Any]) -> None:
    if checkpoint.get("checkpoint_id") != CHECKPOINT_ID:
        raise ProductDiscoveryError("R1.6.1 checkpoint ID drift")
    if (
        artifact_sha256(checkpoint, digest_field="checkpoint_sha256")
        != checkpoint.get("checkpoint_sha256")
    ):
        raise ProductDiscoveryError("R1.6.1 checkpoint digest mismatch")
    if checkpoint.get("checkpoint_sha256") != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("R1.6.1 frozen checkpoint digest drift")

    materialized = {
        key: value
        for key, value in checkpoint.items()
        if key != "checkpoint_sha256"
    }
    if materialized != derive_routing_refinement():
        raise ProductDiscoveryError(
            "R1.6.1 checkpoint does not reproduce from frozen inputs"
        )

    if checkpoint["work_item_counts_by_route"] != EXPECTED_WORK_ITEM_COUNTS_BY_ROUTE:
        raise ProductDiscoveryError("R1.6.1 refined work-item route counts drift")
    if checkpoint["capture_counts_by_route"] != EXPECTED_CAPTURE_COUNTS_BY_ROUTE:
        raise ProductDiscoveryError("R1.6.1 refined capture route counts drift")
    if (
        checkpoint["refined_predecessor_subtype_counts"]
        != EXPECTED_REFINED_SUBTYPE_COUNTS
    ):
        raise ProductDiscoveryError("R1.6.1 refined subtype counts drift")
    if checkpoint.get("changed_work_item_count") != 13:
        raise ProductDiscoveryError("R1.6.1 changed work-item count drift")
    if checkpoint.get("changed_capture_count") != 17:
        raise ProductDiscoveryError("R1.6.1 changed capture count drift")

    predecessor = load_execution_unit_routing()
    predecessor_by_id = {
        str(item["work_item_id"]): item
        for item in cast(Sequence[Mapping[str, Any]], predecessor["route_table"])
    }
    for item in cast(Sequence[Mapping[str, Any]], checkpoint["route_table"]):
        work_item_id = str(item["work_item_id"])
        prior = predecessor_by_id[work_item_id]
        predecessor_route = str(prior["execution_route"])
        refined_route = str(item["execution_route"])
        subtype = str(item["execution_subtype"])

        if str(item["r1_6_execution_route"]) != predecessor_route:
            raise ProductDiscoveryError("R1.6.1 predecessor-route binding drift")
        if list(item["capture_ids"]) != list(prior["capture_ids"]):
            raise ProductDiscoveryError("R1.6.1 capture provenance drift")

        if predecessor_route != LITERATURE_RECORD_EXTRACTION:
            if refined_route != predecessor_route or subtype != UNCHANGED_FROM_R1_6:
                raise ProductDiscoveryError(
                    "R1.6.1 changed an out-of-scope predecessor route"
                )
            continue

        if subtype == ACTUAL_LITERATURE_RECORD:
            if refined_route != LITERATURE_RECORD_EXTRACTION:
                raise ProductDiscoveryError(
                    "R1.6.1 actual literature record route drift"
                )
        elif subtype in {
            EMPTY_LITERATURE_QUERY_SENTINEL,
            EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL,
        }:
            if refined_route != SOURCE_SURFACE_RESOLUTION:
                raise ProductDiscoveryError(
                    "R1.6.1 empty-query sentinel route drift"
                )
        else:
            if refined_route != MIXED_OR_UNRESOLVED_UNIT_REVIEW:
                raise ProductDiscoveryError(
                    "R1.6.1 unresolved literature subtype must fail closed"
                )


def load_routing_refinement() -> dict[str, Any]:
    checkpoint = _load(CHECKPOINT_RESOURCE)
    validate_routing_refinement(checkpoint)
    return checkpoint
