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
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
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
    normalize_candidate_key,
)

RULE_RESOURCE = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_RULE.v1.0.json"
ROUTING_RESOURCE = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_CHECKPOINT.v1.0.json"

RULE_ID = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_RULE_v1.0"
ROUTING_ID = "RELEASE_A_R1_EXECUTION_UNIT_ROUTING_CHECKPOINT_v1.0"
RULE_SHA256 = "e92a46c80b841f51d4646e02f9c91e0c7e9ce8a80cce419221d58d5524c7dd68"
ROUTING_SHA256 = "5b37f3e4aaa3d4cced9864aa6dcc6e5d547726e277bbbce0551005bf12a3465e"

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

SOURCE_SURFACE_COMPLETION_STATES = (
    "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
    "SOURCE_SPECIFIC_FINITE_CARDINALITY_ESTABLISHED",
    "SOURCE_BARRIER_UNRESOLVED",
)
LITERATURE_RECORD_COMPLETION_STATES = (
    "RECORD_EXTRACTED_ZERO_OFFERING_LEADS",
    "RECORD_EXTRACTED_WITH_OFFERING_LEADS",
    "RECORD_EXTRACTION_UNRESOLVED",
)
ROUTE_EXECUTION_REVIEW_STATES = frozenset({"HUMAN_REVIEWED", "MACHINE_PROVISIONAL"})
SOURCE_EVIDENCE_ROLES = frozenset({"SOURCE_QUERY_EXECUTION", "SOURCE_ENUMERATION", "SOURCE_ACCESS_BARRIER"})
LITERATURE_EVIDENCE_ROLES = frozenset({"RECORD_EXTRACTION", "RECORD_ACCESS_BARRIER"})
SOURCE_EVIDENCE_PROPOSITIONS = frozenset(
    {
        "SOURCE_QUERY_ZERO_LEADS",
        "SOURCE_QUERY_WITH_LEADS",
        "SOURCE_SCOPE_EXHAUSTED",
        "SOURCE_FINITE_CARDINALITY_ESTABLISHED",
        "SOURCE_BARRIER_UNRESOLVED",
    }
)
LITERATURE_EVIDENCE_PROPOSITIONS = frozenset(
    {
        "RECORD_ZERO_OFFERING_LEADS",
        "RECORD_WITH_OFFERING_LEADS",
        "RECORD_EXTRACTION_UNRESOLVED",
    }
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

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

    if tuple(rule.get("source_surface_completion_states", [])) != SOURCE_SURFACE_COMPLETION_STATES:
        raise ProductDiscoveryError("R1.6 source-surface completion-state contract drift")

    if tuple(rule.get("literature_record_completion_states", [])) != LITERATURE_RECORD_COMPLETION_STATES:
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
        "source_exhaustion_or_finite_cardinality_requires_human_review": True,
        "route_execution_record_leads_must_be_unique": True,
        "route_execution_record_evidence_must_precede_knowledge_cutoff": True,
        "route_execution_record_requires_explicit_capture_coverage": True,
        "work_item_completion_claim_requires_full_capture_coverage": True,
        "route_execution_record_collections_require_canonical_order": True,
    }
    if dict(controls) != expected_controls:
        raise ProductDiscoveryError("R1.6 execution controls drift")

    evidence_contract = cast(Mapping[str, Any], rule["route_execution_evidence_contract"])
    expected_evidence_contract = {
        "source_surface_allowed_evidence_roles": [
            "SOURCE_QUERY_EXECUTION",
            "SOURCE_ENUMERATION",
            "SOURCE_ACCESS_BARRIER",
        ],
        "literature_record_allowed_evidence_roles": [
            "RECORD_EXTRACTION",
            "RECORD_ACCESS_BARRIER",
        ],
        "source_surface_allowed_supported_propositions": [
            "SOURCE_QUERY_ZERO_LEADS",
            "SOURCE_QUERY_WITH_LEADS",
            "SOURCE_SCOPE_EXHAUSTED",
            "SOURCE_FINITE_CARDINALITY_ESTABLISHED",
            "SOURCE_BARRIER_UNRESOLVED",
        ],
        "literature_record_allowed_supported_propositions": [
            "RECORD_ZERO_OFFERING_LEADS",
            "RECORD_WITH_OFFERING_LEADS",
            "RECORD_EXTRACTION_UNRESOLVED",
        ],
        "evidence_must_bind_exact_covered_capture_id": True,
        "evidence_query_or_seed_id_must_match_frozen_capture": True,
        "every_covered_capture_requires_supported_proposition": True,
        "extracted_lead_requires_lead_bearing_evidence_proposition": True,
        "source_scope_exhaustion_claim_requires_support_for_every_covered_capture": True,
        "finite_cardinality_claim_requires_support_for_every_covered_capture": True,
    }
    if dict(evidence_contract) != expected_evidence_contract:
        raise ProductDiscoveryError("R1.6 route-execution evidence contract drift")

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


def extracted_lead_id(
    work_item_id: str,
    candidate_key: str,
    source_observation_ref: str,
) -> str:
    """Return a deterministic non-canonical ID for one extracted candidate lead."""

    material = {
        "work_item_id": work_item_id,
        "normalized_candidate_key": normalize_candidate_key(candidate_key),
        "source_observation_ref": source_observation_ref,
    }
    return "R1LEAD-" + canonical_sha256(material)


def route_execution_record_id(record: Mapping[str, Any]) -> str:
    """Bind a route-execution record to its complete content."""

    material = {key: value for key, value in record.items() if key != "execution_record_id"}
    return "R1ROUTE-" + canonical_sha256(material)


def _parse_knowledge_time(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ProductDiscoveryError("R1.6 route execution evidence requires knowledge_observed_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductDiscoveryError("R1.6 route execution evidence has invalid knowledge_observed_at") from exc
    if parsed.tzinfo is None:
        raise ProductDiscoveryError("R1.6 route execution evidence timestamp must be timezone-aware")
    return parsed


def _validate_route_execution_evidence(
    evidence: Sequence[Mapping[str, Any]],
    *,
    route: str,
    covered_capture_ids: Sequence[str],
    source_records_by_capture_id: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, set[str]]]:
    """Validate evidence and bind every claimed capture to its frozen query/seed provenance."""

    if not evidence:
        raise ProductDiscoveryError("R1.6 route execution requires attributable evidence")

    if route == SOURCE_SURFACE_RESOLUTION:
        allowed_roles = SOURCE_EVIDENCE_ROLES
        allowed_propositions = SOURCE_EVIDENCE_PROPOSITIONS
    elif route == LITERATURE_RECORD_EXTRACTION:
        allowed_roles = LITERATURE_EVIDENCE_ROLES
        allowed_propositions = LITERATURE_EVIDENCE_PROPOSITIONS
    else:
        raise ProductDiscoveryError("R1.6 route execution evidence is only defined for source/record routes")

    cutoff = _parse_knowledge_time(KNOWLEDGE_TIME_CUTOFF)
    covered_set = set(covered_capture_ids)
    evidence_by_ref: dict[str, Mapping[str, Any]] = {}
    propositions_by_capture: dict[str, set[str]] = {capture_id: set() for capture_id in covered_capture_ids}
    allowed_fields = {
        "evidence_ref",
        "capture_id",
        "query_or_seed_id",
        "source_locator",
        "knowledge_observed_at",
        "sha256",
        "evidence_role",
        "supported_propositions",
    }
    evidence_refs_in_order: list[str] = []

    for item in evidence:
        if set(item) != allowed_fields:
            raise ProductDiscoveryError("R1.6 route execution evidence fields drift")

        evidence_ref = item.get("evidence_ref")
        if not isinstance(evidence_ref, str) or not evidence_ref:
            raise ProductDiscoveryError("R1.6 route execution evidence_ref is required")
        if evidence_ref in evidence_by_ref:
            raise ProductDiscoveryError("R1.6 route execution evidence_ref values must be unique")
        evidence_refs_in_order.append(evidence_ref)

        capture_id = item.get("capture_id")
        if not isinstance(capture_id, str) or capture_id not in covered_set:
            raise ProductDiscoveryError("R1.6 route execution evidence must bind one covered capture ID")
        source_record = source_records_by_capture_id.get(capture_id)
        if source_record is None:
            raise ProductDiscoveryError("R1.6 route execution evidence references an unknown frozen capture")

        query_or_seed_id = item.get("query_or_seed_id")
        if query_or_seed_id != source_record.get("query_or_seed_id"):
            raise ProductDiscoveryError("R1.6 route execution evidence query_or_seed_id drift")

        source_locator = item.get("source_locator")
        if not isinstance(source_locator, str) or not source_locator:
            raise ProductDiscoveryError("R1.6 route execution source_locator is required")
        if _parse_knowledge_time(item.get("knowledge_observed_at")) > cutoff:
            raise ProductDiscoveryError("R1.6 route execution evidence exceeds the frozen knowledge-time cutoff")

        sha = item.get("sha256")
        if not isinstance(sha, str) or SHA256_RE.fullmatch(sha) is None:
            raise ProductDiscoveryError("R1.6 route execution evidence requires SHA-256")

        evidence_role = item.get("evidence_role")
        if evidence_role not in allowed_roles:
            raise ProductDiscoveryError("R1.6 route execution evidence role does not match the frozen route")

        propositions_raw = item.get("supported_propositions")
        if not isinstance(propositions_raw, list) or not propositions_raw:
            raise ProductDiscoveryError("R1.6 route execution evidence requires supported propositions")
        propositions = [str(value) for value in propositions_raw]
        if len(propositions) != len(set(propositions)) or propositions != sorted(propositions):
            raise ProductDiscoveryError("R1.6 route execution evidence propositions must be unique and canonical")
        if not set(propositions).issubset(allowed_propositions):
            raise ProductDiscoveryError("R1.6 route execution evidence proposition does not match the frozen route")

        evidence_by_ref[evidence_ref] = item
        propositions_by_capture[capture_id].update(propositions)

    if evidence_refs_in_order != sorted(evidence_refs_in_order):
        raise ProductDiscoveryError("R1.6 route execution evidence must use canonical evidence_ref order")
    if any(not propositions_by_capture[capture_id] for capture_id in covered_capture_ids):
        raise ProductDiscoveryError("R1.6 every covered capture requires attributable route-execution evidence")

    return evidence_by_ref, propositions_by_capture


def _validate_extracted_leads(
    work_item_id: str,
    leads: Sequence[Mapping[str, Any]],
    evidence_by_ref: Mapping[str, Mapping[str, Any]],
    *,
    route: str,
) -> None:
    seen_lead_ids: set[str] = set()
    lead_ids_in_order: list[str] = []
    seen_signatures: set[tuple[str, str]] = set()
    allowed_fields = {
        "lead_id",
        "candidate_key",
        "source_observation_ref",
        "evidence_ref",
        "canonical_offering_id",
    }
    required_proposition = (
        "SOURCE_QUERY_WITH_LEADS" if route == SOURCE_SURFACE_RESOLUTION else "RECORD_WITH_OFFERING_LEADS"
    )

    for lead in leads:
        if set(lead) != allowed_fields:
            raise ProductDiscoveryError("R1.6 extracted-lead fields drift")
        candidate_key = lead.get("candidate_key")
        source_observation_ref = lead.get("source_observation_ref")
        evidence_ref = lead.get("evidence_ref")
        if not isinstance(candidate_key, str) or not candidate_key.strip():
            raise ProductDiscoveryError("R1.6 extracted lead requires candidate_key")
        if not isinstance(source_observation_ref, str) or not source_observation_ref:
            raise ProductDiscoveryError("R1.6 extracted lead requires source_observation_ref")
        if not isinstance(evidence_ref, str) or evidence_ref not in evidence_by_ref:
            raise ProductDiscoveryError("R1.6 extracted lead must bind route-execution evidence")
        evidence_item = evidence_by_ref[evidence_ref]
        if required_proposition not in set(cast(Sequence[str], evidence_item["supported_propositions"])):
            raise ProductDiscoveryError("R1.6 extracted lead evidence does not support an extracted-lead proposition")
        if lead.get("canonical_offering_id") is not None:
            raise ProductDiscoveryError("R1.6 extracted lead cannot allocate canonical identity")

        expected_lead_id = extracted_lead_id(work_item_id, candidate_key, source_observation_ref)
        if lead.get("lead_id") != expected_lead_id:
            raise ProductDiscoveryError("R1.6 extracted lead ID does not match deterministic content")
        if expected_lead_id in seen_lead_ids:
            raise ProductDiscoveryError("R1.6 extracted lead IDs must be unique")
        seen_lead_ids.add(expected_lead_id)
        lead_ids_in_order.append(expected_lead_id)

        signature = (normalize_candidate_key(candidate_key), source_observation_ref)
        if signature in seen_signatures:
            raise ProductDiscoveryError("R1.6 duplicate extracted candidate lead")
        seen_signatures.add(signature)

    if lead_ids_in_order != sorted(lead_ids_in_order):
        raise ProductDiscoveryError("R1.6 extracted leads must use canonical lead_id order")


def validate_route_execution_record(
    record: Mapping[str, Any],
    *,
    routing_checkpoint: Mapping[str, Any] | None = None,
) -> None:
    """Validate source/record execution without converting the retrieval unit into a product."""

    required_fields = {
        "execution_record_id",
        "work_item_id",
        "execution_route",
        "completion_state",
        "review_state",
        "reviewer_id",
        "evidence",
        "extracted_leads",
        "source_scope_exhausted",
        "finite_cardinality_upper_bound",
        "global_source_exhaustion_claimed",
        "covered_capture_ids",
        "work_item_completion_claimed",
    }
    allowed_fields = required_fields | {"notes"}
    if not required_fields.issubset(record) or not set(record).issubset(allowed_fields):
        raise ProductDiscoveryError("R1.6 route execution record fields drift")
    if record["execution_record_id"] != route_execution_record_id(record):
        raise ProductDiscoveryError("R1.6 execution_record_id does not match deterministic content")

    active_routing = load_execution_unit_routing() if routing_checkpoint is None else routing_checkpoint
    item_by_work_item = {
        str(item["work_item_id"]): item for item in cast(Sequence[Mapping[str, Any]], active_routing["route_table"])
    }
    work_item_id = str(record["work_item_id"])
    routed_item = item_by_work_item.get(work_item_id)
    if routed_item is None:
        raise ProductDiscoveryError("R1.6 route execution references an item outside the frozen routing checkpoint")
    route = str(record["execution_route"])
    if route != str(routed_item["execution_route"]):
        raise ProductDiscoveryError("R1.6 route execution does not match the frozen execution route")

    routed_capture_sequence = [str(item) for item in cast(Sequence[str], routed_item["capture_ids"])]
    routed_capture_ids = set(routed_capture_sequence)
    covered_capture_ids_raw = record["covered_capture_ids"]
    if not isinstance(covered_capture_ids_raw, list) or not covered_capture_ids_raw:
        raise ProductDiscoveryError("R1.6 route execution requires explicit covered_capture_ids")
    covered_capture_ids = [str(item) for item in covered_capture_ids_raw]
    if len(covered_capture_ids) != len(set(covered_capture_ids)):
        raise ProductDiscoveryError("R1.6 covered_capture_ids must be unique")
    covered_capture_set = set(covered_capture_ids)
    if not covered_capture_set.issubset(routed_capture_ids):
        raise ProductDiscoveryError("R1.6 route execution covers capture IDs outside the frozen work item")
    canonical_covered_order = [item for item in routed_capture_sequence if item in covered_capture_set]
    if covered_capture_ids != canonical_covered_order:
        raise ProductDiscoveryError("R1.6 covered_capture_ids must preserve frozen capture order")

    completion_claimed = record["work_item_completion_claimed"]
    if not isinstance(completion_claimed, bool):
        raise ProductDiscoveryError("R1.6 work_item_completion_claimed must be boolean")
    if completion_claimed and covered_capture_set != routed_capture_ids:
        raise ProductDiscoveryError("R1.6 work-item completion requires full frozen capture coverage")
    if route not in {SOURCE_SURFACE_RESOLUTION, LITERATURE_RECORD_EXTRACTION}:
        raise ProductDiscoveryError("R1.6 candidate and temporal work must use their existing governed contracts")

    review_state = str(record["review_state"])
    reviewer_id = record.get("reviewer_id")
    if review_state not in ROUTE_EXECUTION_REVIEW_STATES:
        raise ProductDiscoveryError("R1.6 route execution review state is not frozen")
    if review_state == "HUMAN_REVIEWED":
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ProductDiscoveryError("Human-reviewed R1.6 route execution requires reviewer_id")
    elif reviewer_id is not None:
        raise ProductDiscoveryError("Machine-provisional R1.6 route execution must keep reviewer_id null")

    manifest = load_r1_candidate_resolution_manifest()
    source_records = compile_r1_source_records(manifest)
    source_records_by_capture_id = {str(item["capture_id"]): item for item in source_records}
    if len(source_records_by_capture_id) != len(source_records):
        raise ProductDiscoveryError("R1.6 frozen source records contain duplicate capture IDs")

    evidence = cast(Sequence[Mapping[str, Any]], record["evidence"])
    evidence_by_ref, propositions_by_capture = _validate_route_execution_evidence(
        evidence,
        route=route,
        covered_capture_ids=covered_capture_ids,
        source_records_by_capture_id=source_records_by_capture_id,
    )
    leads = cast(Sequence[Mapping[str, Any]], record["extracted_leads"])
    _validate_extracted_leads(work_item_id, leads, evidence_by_ref, route=route)

    source_scope_exhausted = record["source_scope_exhausted"]
    global_source_exhaustion_claimed = record["global_source_exhaustion_claimed"]
    if not isinstance(source_scope_exhausted, bool) or not isinstance(global_source_exhaustion_claimed, bool):
        raise ProductDiscoveryError("R1.6 route execution exhaustion flags must be boolean")
    if global_source_exhaustion_claimed:
        raise ProductDiscoveryError("R1.6 bounded route execution cannot claim global source exhaustion")

    finite_bound = record["finite_cardinality_upper_bound"]
    if finite_bound is not None and (
        not isinstance(finite_bound, int) or isinstance(finite_bound, bool) or finite_bound < 0
    ):
        raise ProductDiscoveryError("R1.6 finite cardinality upper bound must be a non-negative integer or null")
    if finite_bound is not None and len(leads) > finite_bound:
        raise ProductDiscoveryError("R1.6 extracted leads exceed the claimed finite cardinality upper bound")

    completion_state = str(record["completion_state"])

    def require_capture_state(allowed: set[str], *, message: str) -> None:
        for capture_id in covered_capture_ids:
            if not (propositions_by_capture[capture_id] & allowed):
                raise ProductDiscoveryError(message)

    if route == SOURCE_SURFACE_RESOLUTION:
        if completion_state not in SOURCE_SURFACE_COMPLETION_STATES:
            raise ProductDiscoveryError("R1.6 source-surface completion state is not frozen")
        if completion_state == "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS":
            if leads:
                raise ProductDiscoveryError("R1.6 zero-lead source completion cannot contain extracted leads")
            if finite_bound is not None:
                raise ProductDiscoveryError("R1.6 zero-lead query completion cannot silently assert finite cardinality")
            require_capture_state(
                {"SOURCE_QUERY_ZERO_LEADS"},
                message="R1.6 zero-lead source completion lacks per-capture zero-lead evidence",
            )
        elif completion_state == "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS":
            if not leads:
                raise ProductDiscoveryError("R1.6 source completion with leads requires at least one extracted lead")
            if finite_bound is not None:
                raise ProductDiscoveryError("R1.6 extracted-lead completion cannot silently assert finite cardinality")
            require_capture_state(
                {"SOURCE_QUERY_ZERO_LEADS", "SOURCE_QUERY_WITH_LEADS"},
                message="R1.6 source completion with leads leaves a covered capture unaccounted",
            )
            if not any("SOURCE_QUERY_WITH_LEADS" in propositions for propositions in propositions_by_capture.values()):
                raise ProductDiscoveryError("R1.6 source completion with leads lacks extracted-lead evidence")
        elif completion_state == "SOURCE_SPECIFIC_FINITE_CARDINALITY_ESTABLISHED":
            if finite_bound is None:
                raise ProductDiscoveryError("R1.6 finite-cardinality completion requires an explicit upper bound")
            require_capture_state(
                {
                    "SOURCE_QUERY_ZERO_LEADS",
                    "SOURCE_QUERY_WITH_LEADS",
                    "SOURCE_FINITE_CARDINALITY_ESTABLISHED",
                },
                message="R1.6 finite-cardinality completion leaves a covered capture unaccounted",
            )
            if not any(
                "SOURCE_FINITE_CARDINALITY_ESTABLISHED" in propositions
                for propositions in propositions_by_capture.values()
            ):
                raise ProductDiscoveryError("R1.6 finite-cardinality completion lacks cardinality-specific evidence")
        else:
            if source_scope_exhausted or finite_bound is not None:
                raise ProductDiscoveryError(
                    "R1.6 unresolved source barrier cannot assert exhaustion or finite cardinality"
                )
            require_capture_state(
                {"SOURCE_QUERY_ZERO_LEADS", "SOURCE_QUERY_WITH_LEADS", "SOURCE_BARRIER_UNRESOLVED"},
                message="R1.6 unresolved source completion leaves a covered capture unaccounted",
            )
            if not any(
                "SOURCE_BARRIER_UNRESOLVED" in propositions for propositions in propositions_by_capture.values()
            ):
                raise ProductDiscoveryError("R1.6 unresolved source completion lacks barrier evidence")

        if source_scope_exhausted and any(
            "SOURCE_SCOPE_EXHAUSTED" not in propositions for propositions in propositions_by_capture.values()
        ):
            raise ProductDiscoveryError(
                "R1.6 source exhaustion claim lacks per-capture source-scope exhaustion evidence"
            )
        if finite_bound is not None and any(
            "SOURCE_FINITE_CARDINALITY_ESTABLISHED" not in propositions
            for propositions in propositions_by_capture.values()
        ):
            raise ProductDiscoveryError("R1.6 finite cardinality claim lacks per-capture cardinality-specific evidence")
        if (source_scope_exhausted or finite_bound is not None) and review_state != "HUMAN_REVIEWED":
            raise ProductDiscoveryError("R1.6 source exhaustion or finite cardinality requires human review")
    else:
        if completion_state not in LITERATURE_RECORD_COMPLETION_STATES:
            raise ProductDiscoveryError("R1.6 literature-record completion state is not frozen")
        if source_scope_exhausted or finite_bound is not None:
            raise ProductDiscoveryError("R1.6 literature extraction cannot assert source exhaustion or cardinality")
        if completion_state == "RECORD_EXTRACTED_ZERO_OFFERING_LEADS":
            if leads:
                raise ProductDiscoveryError("R1.6 zero-lead record extraction cannot contain extracted leads")
            require_capture_state(
                {"RECORD_ZERO_OFFERING_LEADS"},
                message="R1.6 zero-lead record completion lacks per-capture extraction evidence",
            )
        elif completion_state == "RECORD_EXTRACTED_WITH_OFFERING_LEADS":
            if not leads:
                raise ProductDiscoveryError("R1.6 record extraction with leads requires at least one extracted lead")
            require_capture_state(
                {"RECORD_ZERO_OFFERING_LEADS", "RECORD_WITH_OFFERING_LEADS"},
                message="R1.6 record extraction with leads leaves a covered capture unaccounted",
            )
            if not any(
                "RECORD_WITH_OFFERING_LEADS" in propositions for propositions in propositions_by_capture.values()
            ):
                raise ProductDiscoveryError("R1.6 record extraction with leads lacks lead-bearing extraction evidence")
        else:
            require_capture_state(
                {
                    "RECORD_ZERO_OFFERING_LEADS",
                    "RECORD_WITH_OFFERING_LEADS",
                    "RECORD_EXTRACTION_UNRESOLVED",
                },
                message="R1.6 unresolved record extraction leaves a covered capture unaccounted",
            )
            if not any(
                "RECORD_EXTRACTION_UNRESOLVED" in propositions for propositions in propositions_by_capture.values()
            ):
                raise ProductDiscoveryError("R1.6 unresolved record completion lacks unresolved-extraction evidence")


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
    load_execution_unit_routing_rule()
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

    work_item_ids = [str(item["work_item_id"]) for item in route_table]
    if len(work_item_ids) != len(set(work_item_ids)):
        raise ProductDiscoveryError("R1.6 route table contains duplicate work item IDs")
    frozen_work_item_ids = [
        str(item["work_item_id"]) for item in cast(Sequence[Mapping[str, Any]], worklist["work_items"])
    ]
    if work_item_ids != frozen_work_item_ids:
        raise ProductDiscoveryError("R1.6 route table must preserve the frozen R1.4 worklist order")

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
    derived = derive_execution_unit_routing()
    if materialized != derived:
        differing_keys = sorted(
            key for key in set(materialized) | set(derived) if materialized.get(key) != derived.get(key)
        )
        detail = ",".join(differing_keys)
        if differing_keys == ["route_table"]:
            actual_rows = cast(Sequence[Mapping[str, Any]], materialized["route_table"])
            derived_rows = cast(Sequence[Mapping[str, Any]], derived["route_table"])
            first_difference = next(
                (
                    index
                    for index, (actual, expected) in enumerate(zip(actual_rows, derived_rows, strict=False))
                    if actual != expected
                ),
                min(len(actual_rows), len(derived_rows)),
            )
            actual_id = (
                str(actual_rows[first_difference]["work_item_id"])
                if first_difference < len(actual_rows)
                else "<missing>"
            )
            derived_id = (
                str(derived_rows[first_difference]["work_item_id"])
                if first_difference < len(derived_rows)
                else "<missing>"
            )
            detail += f";first_route_index={first_difference};materialized_id={actual_id};derived_id={derived_id}"
        raise ProductDiscoveryError("R1.6 routing checkpoint does not reproduce from frozen inputs: " + detail)

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
