"""Release-A R1.7 append-only route-execution ledger contract.

R1.6 routes the frozen R1.4 work population by empirical unit. This module
freezes how source-surface and literature-record execution records are appended,
superseded, conflict-checked, and aggregated before substantive R1.7 execution
is committed.
"""

from __future__ import annotations

import base64
import binascii
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
    SOURCE_SURFACE_RESOLUTION,
    WORLD_TIME_CUTOFF,
    load_execution_unit_routing,
    validate_execution_unit_routing,
    validate_route_execution_record,
)
from neuroai_workbench.release_a_r1_execution_unit_routing import (
    ROUTING_SHA256 as R1_6_ROUTING_SHA256,
)
from neuroai_workbench.release_a_r1_execution_unit_routing import (
    RULE_SHA256 as R1_6_RULE_SHA256,
)
from neuroai_workbench.release_a_r1_resolution import DISCOVERY_RESOURCE_PACKAGE, normalize_candidate_key

RULE_RESOURCE = "RELEASE_A_R1_ROUTE_EXECUTION_LEDGER_RULE.v1.0.json"
RULE_ID = "RELEASE_A_R1_ROUTE_EXECUTION_LEDGER_RULE_v1.0"
RULE_SHA256 = "04d8db5f44aa568ed2df216e7a6182e3f45e8359c885cd02c1f0131354d3dcb2"
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
        "machine_provisional_entry_may_supersede_human_reviewed_entry": False,
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
        "overlapping_active_finite_bounds_must_agree": True,
        "active_leads_must_respect_applicable_finite_bounds": True,
        "unresolved_barrier_record_may_establish_work_item_completion": False,
        "derived_state_reports_unresolved_barrier_work_items": True,
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
    expected_lead_contract = {
        "canonical_identity_allocation": False,
        "frozen_r1_4_worklist_mutation": False,
        "historical_lead_provenance_append_only": True,
        "active_lead_ledger_deduplicates_by_lead_id": True,
        "repeated_leads_from_distinct_source_provenance_remain_distinct": True,
        "lead_support_status_derived_from_active_entries": True,
        "conflicting_identity_material_for_same_lead_id_fails_closed": True,
        "support_specific_evidence_ref_is_not_lead_identity_material": True,
        "equivalent_raw_candidate_keys_may_share_lead_identity": True,
        "derived_lead_ledger_preserves_normalized_candidate_key": True,
        "derived_lead_support_preserves_work_item_route_capture_query_and_evidence_provenance": True,
        "derived_lead_support_preserves_decision_sensitivity_flags": True,
    }
    if dict(lead_contract) != expected_lead_contract:
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

    evidence_archive = cast(Mapping[str, Any], rule["evidence_archive_contract"])
    expected_evidence_archive = {
        "evidence_sha256_semantics": "SHA256_OF_CANONICAL_EVIDENCE_ARTIFACT_JSON",
        "evidence_artifact_schema_id": "R1_ROUTE_EVIDENCE_ARTIFACT_v1.0",
        "evidence_artifact_required_fields": [
            "artifact_schema_id",
            "evidence_ref",
            "capture_id",
            "query_or_seed_id",
            "source_locator",
            "knowledge_observed_at",
            "retrieval_request",
            "response_context",
            "content_representation",
            "content",
        ],
        "allowed_content_representations": ["UTF8_TEXT", "BASE64_BYTES", "STRUCTURED_JSON"],
        "source_locator_is_origin_not_evidence_identity": True,
        "archived_artifact_required_for_every_evidence_ref": True,
        "archived_artifact_required_for_completion_claim": True,
        "archive_must_preserve_retrieval_request_and_response_context": True,
        "archive_must_preserve_content_type_and_encoding_in_response_context": True,
        "archive_must_be_replayable_for_supported_proposition_review": True,
        "unarchivable_or_nonreplayable_source_remains_unresolved": True,
        "evidence_observed_at_is_knowledge_time_not_world_time": True,
        "ledger_state_rejects_missing_or_unreferenced_archive_artifacts": True,
        "retrieval_request_required_fields": ["method", "locator", "request_context"],
        "response_context_required_fields": [
            "retrieval_status",
            "content_type",
            "encoding",
            "final_locator",
            "response_metadata",
        ],
        "request_context_must_be_structured_mapping": True,
        "response_metadata_must_be_structured_mapping": True,
        "digest_is_canonical_artifact_json_not_raw_transport_bytes": True,
        "request_context_must_bind_query_or_seed_id": True,
    }
    if dict(evidence_archive) != expected_evidence_archive:
        raise ProductDiscoveryError("R1.7 evidence-archive contract drift")

    temporal = cast(Mapping[str, Any], rule["temporal_interpretation_contract"])
    expected_temporal = {
        "post_world_cutoff_retrieval_may_supply_knowledge_about_pre_cutoff_world_state": True,
        "route_execution_result_itself_does_not_establish_world_time_product_eligibility": True,
        "extracted_lead_requires_separate_world_time_product_adjudication": True,
        "zero_lead_result_is_bounded_to_declared_source_query_at_knowledge_observation_time": True,
        "zero_lead_result_does_not_establish_historical_product_absence": True,
        "source_exhaustion_does_not_establish_global_population_completeness": True,
    }
    if dict(temporal) != expected_temporal:
        raise ProductDiscoveryError("R1.7 temporal-interpretation contract drift")

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
    capture_count = sum(len(cast(Sequence[str], item["capture_ids"])) for item in rows)
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


EVIDENCE_ARTIFACT_SCHEMA_ID = "R1_ROUTE_EVIDENCE_ARTIFACT_v1.0"
EVIDENCE_ARTIFACT_FIELDS = {
    "artifact_schema_id",
    "evidence_ref",
    "capture_id",
    "query_or_seed_id",
    "source_locator",
    "knowledge_observed_at",
    "retrieval_request",
    "response_context",
    "content_representation",
    "content",
}
ALLOWED_CONTENT_REPRESENTATIONS = {"UTF8_TEXT", "BASE64_BYTES", "STRUCTURED_JSON"}


def _validate_evidence_artifact(
    evidence: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> None:
    if set(artifact) != EVIDENCE_ARTIFACT_FIELDS:
        raise ProductDiscoveryError("R1.7 evidence artifact fields drift")
    if artifact.get("artifact_schema_id") != EVIDENCE_ARTIFACT_SCHEMA_ID:
        raise ProductDiscoveryError("R1.7 evidence artifact schema ID drift")

    for field in (
        "evidence_ref",
        "capture_id",
        "query_or_seed_id",
        "source_locator",
        "knowledge_observed_at",
    ):
        if artifact.get(field) != evidence.get(field):
            raise ProductDiscoveryError(f"R1.7 evidence artifact {field} binding drift")

    request = artifact.get("retrieval_request")
    if not isinstance(request, Mapping) or not request:
        raise ProductDiscoveryError("R1.7 evidence artifact requires retrieval_request")
    expected_request_fields = {"method", "locator", "request_context"}
    if set(request) != expected_request_fields:
        raise ProductDiscoveryError("R1.7 evidence artifact retrieval_request fields drift")
    if not isinstance(request.get("method"), str) or not str(request["method"]).strip():
        raise ProductDiscoveryError("R1.7 evidence artifact retrieval_request requires method")
    if request.get("locator") != evidence.get("source_locator"):
        raise ProductDiscoveryError("R1.7 evidence artifact retrieval locator drift")
    request_context = request.get("request_context")
    if not isinstance(request_context, Mapping):
        raise ProductDiscoveryError("R1.7 evidence artifact request_context must be an object")
    if request_context.get("query_or_seed_id") != evidence.get("query_or_seed_id"):
        raise ProductDiscoveryError("R1.7 evidence artifact request_context query_or_seed_id drift")

    response = artifact.get("response_context")
    if not isinstance(response, Mapping) or not response:
        raise ProductDiscoveryError("R1.7 evidence artifact requires response_context")
    expected_response_fields = {
        "retrieval_status",
        "content_type",
        "encoding",
        "final_locator",
        "response_metadata",
    }
    if set(response) != expected_response_fields:
        raise ProductDiscoveryError("R1.7 evidence artifact response_context fields drift")
    for field in ("retrieval_status", "content_type", "encoding", "final_locator"):
        if not isinstance(response.get(field), str) or not str(response[field]).strip():
            raise ProductDiscoveryError(f"R1.7 evidence artifact response_context requires {field}")
    if not isinstance(response.get("response_metadata"), Mapping):
        raise ProductDiscoveryError("R1.7 evidence artifact response_metadata must be an object")

    representation = artifact.get("content_representation")
    if representation not in ALLOWED_CONTENT_REPRESENTATIONS:
        raise ProductDiscoveryError("R1.7 evidence artifact content representation is not frozen")
    content = artifact.get("content")
    if representation == "UTF8_TEXT" and not isinstance(content, str):
        raise ProductDiscoveryError("R1.7 UTF8_TEXT evidence artifact content must be text")
    if representation == "BASE64_BYTES":
        if not isinstance(content, str):
            raise ProductDiscoveryError("R1.7 BASE64_BYTES evidence artifact content must be text")
        try:
            base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ProductDiscoveryError("R1.7 BASE64_BYTES evidence artifact content is invalid") from exc
    if representation == "STRUCTURED_JSON" and content is None:
        raise ProductDiscoveryError("R1.7 STRUCTURED_JSON evidence artifact content cannot be null")

    expected_sha = evidence.get("sha256")
    if expected_sha != canonical_sha256(artifact):
        raise ProductDiscoveryError("R1.7 evidence artifact digest does not match route evidence")


def validate_evidence_archive(
    entries: Sequence[Mapping[str, Any]],
    evidence_archive: Mapping[str, Mapping[str, Any]],
) -> None:
    """Require an exact, content-bound evidence artifact for every ledger evidence reference."""

    evidence_by_ref: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        record = _entry_record(entry)
        for evidence in cast(Sequence[Mapping[str, Any]], record["evidence"]):
            evidence_ref = str(evidence["evidence_ref"])
            previous = evidence_by_ref.get(evidence_ref)
            if previous is not None:
                binding_fields = (
                    "capture_id",
                    "query_or_seed_id",
                    "source_locator",
                    "knowledge_observed_at",
                    "sha256",
                )
                if any(previous.get(field) != evidence.get(field) for field in binding_fields):
                    raise ProductDiscoveryError("R1.7 repeated evidence_ref has conflicting immutable binding")
            evidence_by_ref[evidence_ref] = evidence

    expected_refs = set(evidence_by_ref)
    archive_refs = set(evidence_archive)
    if archive_refs != expected_refs:
        missing = sorted(expected_refs - archive_refs)
        extra = sorted(archive_refs - expected_refs)
        raise ProductDiscoveryError(
            f"R1.7 evidence archive reference set drift; missing={missing}; unreferenced={extra}"
        )

    for evidence_ref in sorted(expected_refs):
        artifact = evidence_archive[evidence_ref]
        if not isinstance(artifact, Mapping):
            raise ProductDiscoveryError("R1.7 evidence archive artifacts must be objects")
        _validate_evidence_artifact(evidence_by_ref[evidence_ref], artifact)


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


def _lead_capture_id(record: Mapping[str, Any], lead: Mapping[str, Any]) -> str:
    evidence_ref = str(lead["evidence_ref"])
    matches = [
        str(evidence["capture_id"])
        for evidence in cast(Sequence[Mapping[str, Any]], record["evidence"])
        if str(evidence["evidence_ref"]) == evidence_ref
    ]
    if len(matches) != 1:
        raise ProductDiscoveryError("R1.7 extracted lead must resolve to exactly one record evidence capture")
    return matches[0]


def _assert_active_bound_consistency(active_entries: Sequence[Mapping[str, Any]]) -> None:
    bound_claims: dict[str, list[tuple[set[str], int, str]]] = defaultdict(list)
    active_leads_by_capture: dict[tuple[str, str], set[str]] = defaultdict(set)

    for entry in active_entries:
        entry_id = str(entry["ledger_entry_id"])
        record = _entry_record(entry)
        if str(record["execution_route"]) != SOURCE_SURFACE_RESOLUTION:
            continue
        work_item_id = str(record["work_item_id"])
        finite_bound = record.get("finite_cardinality_upper_bound")
        if finite_bound is not None:
            bound_claims[work_item_id].append(
                (
                    set(str(value) for value in cast(Sequence[str], record["covered_capture_ids"])),
                    int(finite_bound),
                    entry_id,
                )
            )
        for lead in cast(Sequence[Mapping[str, Any]], record["extracted_leads"]):
            capture_id = _lead_capture_id(record, lead)
            active_leads_by_capture[(work_item_id, capture_id)].add(str(lead["lead_id"]))

    for work_item_id, claims in bound_claims.items():
        for index, (captures, bound, entry_id) in enumerate(claims):
            for other_captures, other_bound, other_entry_id in claims[index + 1 :]:
                if captures & other_captures and bound != other_bound:
                    raise ProductDiscoveryError(
                        "R1.7 overlapping active finite-cardinality bounds disagree: "
                        f"{work_item_id}/{entry_id}/{other_entry_id}"
                    )
            active_lead_ids: set[str] = set()
            for capture_id in captures:
                active_lead_ids.update(active_leads_by_capture[(work_item_id, capture_id)])
            if len(active_lead_ids) > bound:
                raise ProductDiscoveryError(
                    "R1.7 active extracted leads exceed an applicable finite-cardinality bound: "
                    f"{work_item_id}/{entry_id}"
                )


def _derive_lead_state(
    entries: Sequence[Mapping[str, Any]],
    *,
    active_entry_ids: set[str],
    population_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    identity_by_lead_id: dict[str, dict[str, Any]] = {}
    raw_keys_by_lead_id: dict[str, set[str]] = defaultdict(set)
    supports_by_lead_id: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        entry_id = str(entry["ledger_entry_id"])
        record = _entry_record(entry)
        work_item_id = str(record["work_item_id"])
        route = str(record["execution_route"])
        population_item = population_by_id[work_item_id]
        evidence_by_ref = {
            str(evidence["evidence_ref"]): evidence
            for evidence in cast(Sequence[Mapping[str, Any]], record["evidence"])
        }

        for lead in cast(Sequence[Mapping[str, Any]], record["extracted_leads"]):
            lead_id = str(lead["lead_id"])
            raw_candidate_key = str(lead["candidate_key"])
            normalized_candidate_key = normalize_candidate_key(raw_candidate_key)
            identity = {
                "lead_id": lead_id,
                "work_item_id": work_item_id,
                "execution_route": route,
                "normalized_candidate_key": normalized_candidate_key,
                "source_observation_ref": str(lead["source_observation_ref"]),
                "canonical_offering_id": lead.get("canonical_offering_id"),
            }
            previous = identity_by_lead_id.get(lead_id)
            if previous is not None and previous != identity:
                raise ProductDiscoveryError("R1.7 identical lead_id has conflicting identity material")
            identity_by_lead_id[lead_id] = identity
            raw_keys_by_lead_id[lead_id].add(raw_candidate_key)

            evidence_ref = str(lead["evidence_ref"])
            evidence = evidence_by_ref.get(evidence_ref)
            if evidence is None:
                raise ProductDiscoveryError("R1.7 extracted lead support references missing record evidence")
            supports_by_lead_id[lead_id].append(
                {
                    "ledger_entry_id": entry_id,
                    "execution_record_id": str(record["execution_record_id"]),
                    "work_item_id": work_item_id,
                    "execution_route": route,
                    "evidence_ref": evidence_ref,
                    "capture_id": str(evidence["capture_id"]),
                    "query_or_seed_id": str(evidence["query_or_seed_id"]),
                    "source_locator": str(evidence["source_locator"]),
                    "evidence_sha256": str(evidence["sha256"]),
                    "knowledge_observed_at": str(evidence["knowledge_observed_at"]),
                    "evidence_role": str(evidence["evidence_role"]),
                    "supported_propositions": [
                        str(value) for value in cast(Sequence[str], evidence["supported_propositions"])
                    ],
                    "source_observation_ref": str(lead["source_observation_ref"]),
                    "raw_candidate_key": raw_candidate_key,
                    "active_support": entry_id in active_entry_ids,
                    "could_change_marginal_yield_stop": bool(population_item["could_change_marginal_yield_stop"]),
                    "could_change_a3_increment": bool(population_item["could_change_a3_increment"]),
                    "could_change_a4_increment": bool(population_item["could_change_a4_increment"]),
                    "could_change_a_p1_membership": bool(population_item["could_change_a_p1_membership"]),
                }
            )

    result: list[dict[str, Any]] = []
    for lead_id in sorted(identity_by_lead_id):
        supports = sorted(
            supports_by_lead_id[lead_id],
            key=lambda item: (
                str(item["ledger_entry_id"]),
                str(item["evidence_ref"]),
                str(item["capture_id"]),
            ),
        )
        supporting_entry_ids = sorted({str(item["ledger_entry_id"]) for item in supports})
        active_supporting_entry_ids = sorted(
            {str(item["ledger_entry_id"]) for item in supports if item["active_support"]}
        )
        decision_sensitivity = {
            "could_change_marginal_yield_stop": any(
                bool(item["could_change_marginal_yield_stop"]) for item in supports
            ),
            "could_change_a3_increment": any(bool(item["could_change_a3_increment"]) for item in supports),
            "could_change_a4_increment": any(bool(item["could_change_a4_increment"]) for item in supports),
            "could_change_a_p1_membership": any(bool(item["could_change_a_p1_membership"]) for item in supports),
        }
        result.append(
            {
                **identity_by_lead_id[lead_id],
                "raw_candidate_keys": sorted(raw_keys_by_lead_id[lead_id]),
                "supporting_ledger_entry_ids": supporting_entry_ids,
                "active_supporting_ledger_entry_ids": active_supporting_entry_ids,
                "active_support": bool(active_supporting_entry_ids),
                "decision_sensitivity": decision_sensitivity,
                "support_provenance": supports,
            }
        )
    return result


def derive_ledger_state(
    entries: Sequence[Mapping[str, Any]],
    *,
    routing_checkpoint: Mapping[str, Any] | None = None,
    evidence_archive: Mapping[str, Mapping[str, Any]] | None = None,
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
            if prior_record.get("review_state") == "HUMAN_REVIEWED" and record.get("review_state") != "HUMAN_REVIEWED":
                raise ProductDiscoveryError("R1.7 machine-provisional entry cannot supersede human-reviewed evidence")
            superseded_ids.add(str(superseded_id))

        entry_by_id[entry_id] = entry

    archive = {} if evidence_archive is None else evidence_archive
    validate_evidence_archive(entries, archive)

    active_entries = [entry for entry_id, entry in entry_by_id.items() if entry_id not in superseded_ids]
    _assert_no_active_conflicts(active_entries)
    _assert_active_bound_consistency(active_entries)

    unresolved_completion_states = {"SOURCE_BARRIER_UNRESOLVED", "RECORD_EXTRACTION_UNRESOLVED"}
    unresolved_barrier_work_item_ids: set[str] = set()
    for entry in active_entries:
        record = _entry_record(entry)
        if str(record["completion_state"]) in unresolved_completion_states:
            unresolved_barrier_work_item_ids.add(str(record["work_item_id"]))

    completion_by_work_item: dict[str, str] = {}
    for entry in active_entries:
        record = _entry_record(entry)
        if record["work_item_completion_claimed"] is not True:
            continue
        work_item_id = str(record["work_item_id"])
        if str(record["completion_state"]) in unresolved_completion_states:
            raise ProductDiscoveryError("R1.7 unresolved barrier record cannot establish work-item completion")
        if work_item_id in completion_by_work_item:
            raise ProductDiscoveryError("R1.7 work item has multiple active completion records")
        expected_captures = list(cast(Sequence[str], population_by_id[work_item_id]["capture_ids"]))
        if list(cast(Sequence[str], record["covered_capture_ids"])) != expected_captures:
            raise ProductDiscoveryError("R1.7 active work-item completion must cover the full frozen capture set")
        completion_by_work_item[work_item_id] = str(entry["ledger_entry_id"])

    route_counts = Counter(str(_entry_record(entry)["execution_route"]) for entry in active_entries)
    lead_ledger = _derive_lead_state(
        entries,
        active_entry_ids={str(entry["ledger_entry_id"]) for entry in active_entries},
        population_by_id=population_by_id,
    )

    return {
        "frozen_work_item_count": len(population),
        "frozen_capture_count": sum(len(item["capture_ids"]) for item in population),
        "ledger_entry_count": len(entries),
        "active_ledger_entry_count": len(active_entries),
        "superseded_ledger_entry_count": len(superseded_ids),
        "completed_work_item_count": len(completion_by_work_item),
        "pending_work_item_count": len(population) - len(completion_by_work_item),
        "unresolved_barrier_work_item_count": len(unresolved_barrier_work_item_ids),
        "unresolved_barrier_work_item_ids": sorted(unresolved_barrier_work_item_ids),
        "active_entry_count_by_route": {route: route_counts[route] for route in GOVERNED_ROUTES},
        "completion_entry_by_work_item": dict(sorted(completion_by_work_item.items())),
        "extracted_lead_count": len(lead_ledger),
        "active_extracted_lead_count": sum(bool(item["active_support"]) for item in lead_ledger),
        "extracted_lead_ledger": lead_ledger,
    }
