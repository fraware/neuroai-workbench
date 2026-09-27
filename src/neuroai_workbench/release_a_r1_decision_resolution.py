"""Release-A R1 decision-relevant resolution worklist and adjudication contract.

This module freezes the exact R1.4 review population from the immutable R1.2
candidate-resolution ledger and the merged R1.3 resolution-completeness
checkpoint. It also validates append-only adjudication records without
allocating canonical PRODUCT identity or creating downstream authority.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.product_discovery_frames import DEFAULT_ANALYSIS_UNIVERSE_ID, ProductDiscoveryError
from neuroai_workbench.release_a_r1_resolution import (
    DISCOVERY_RESOURCE_PACKAGE,
    R1_CLUSTER_LEDGER_SHA256,
    R1_LEDGER_MANIFEST_SHA256,
    build_r1_candidate_clusters,
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
    load_r1_product_registry,
)
from neuroai_workbench.release_a_r1_resolution_completeness import (
    CHECKPOINT_SHA256 as R1_3_CHECKPOINT_SHA256,
    RULE_SHA256 as R1_3_RULE_SHA256,
    load_resolution_completeness_checkpoint,
)

RULE_RESOURCE = "RELEASE_A_R1_DECISION_RELEVANT_RESOLUTION_WORKLIST_RULE.v1.0.json"
WORKLIST_RESOURCE = "RELEASE_A_R1_DECISION_RELEVANT_RESOLUTION_WORKLIST.v1.0.json"
ADJUDICATION_SCHEMA_RESOURCE = "RELEASE_A_R1_RESOLUTION_ADJUDICATION.schema.json"

RULE_ID = "RELEASE_A_R1_DECISION_RELEVANT_RESOLUTION_WORKLIST_RULE_v1.0"
WORKLIST_ID = "RELEASE_A_R1_DECISION_RELEVANT_RESOLUTION_WORKLIST_v1.0"
RULE_SHA256 = "0e4ea20af846b18e59cabfb338e59ab2cff4b9566e7ea1a3b18f8cc7f825f771"
WORKLIST_SHA256 = "ce030bfa76383c8abd50da9167323893fe2ab9d607879ab83d05a0be320d4e4a"
SOURCE_WORKBENCH_MAIN_COMMIT = "a81dbcc84a31eaa9f959a1f87cdc57e23ccee4bf"
WORLD_TIME_CUTOFF = "2026-09-24"
KNOWLEDGE_TIME_CUTOFF = "2026-10-24T23:59:59Z"
POPULATION_VIEW_ID = "A-P1"

MARGINAL_YIELD_FRAMES = ("F1", "F4", "F5", "F6", "F8", "F11")
MARGINAL_YIELD_ROUNDS = frozenset({"R2", "R3"})
TEMPORAL_REVIEW_OFFERINGS = ("PRD-FLOW-FL-100", "PRD-MODIUS-SPERO")

ADJUDICATION_DISPOSITIONS = frozenset(
    {
        "TERMINAL_INCLUDE_EXISTING_CANONICAL",
        "TERMINAL_INCLUDE_NEW_CANONICAL_PENDING_IDENTITY_AUTHORITY",
        "TERMINAL_EXCLUDE",
        "ONE_OBJECT_UPPER_BOUND_UNRESOLVED",
        "UNRESOLVED_CARDINALITY_UNPROVEN",
        "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER",
    }
)
TERMINAL_OR_BOUND_DISPOSITIONS = frozenset(
    {
        "TERMINAL_INCLUDE_EXISTING_CANONICAL",
        "TERMINAL_INCLUDE_NEW_CANONICAL_PENDING_IDENTITY_AUTHORITY",
        "TERMINAL_EXCLUDE",
        "ONE_OBJECT_UPPER_BOUND_UNRESOLVED",
    }
)
EVIDENCE_ROLES = frozenset(
    {
        "DIRECT_PRE_CUTOFF_STATE",
        "RETROSPECTIVE_EXPLICIT_HISTORICAL_STATE",
        "POST_CUTOFF_CURRENT_STATE_ONLY",
        "CARDINALITY_SPECIFIC",
        "SOURCE_ENUMERATION_SPECIFIC",
    }
)
SUPPORTED_PROPOSITIONS = frozenset(
    {"IDENTITY", "SCOPE", "CURRENTNESS", "LIFECYCLE", "CARDINALITY", "SOURCE_ENUMERATION"}
)
QUALIFYING_LIFECYCLE_STATES = frozenset(
    {"ANNOUNCED", "IN_DEVELOPMENT", "MANUFACTURING_PRE_DELIVERY", "RELEASED"}
)
ADJUDICATOR_STATES = frozenset({"HUMAN_REVIEWED", "MACHINE_PROVISIONAL"})


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
    material = {key: item for key, item in value.items() if key != digest_field}
    return canonical_sha256(material)


def _load(resource: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DISCOVERY_RESOURCE_PACKAGE).joinpath(resource).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Mapping[str, Any]) -> list[str]:
    validator = Draft202012Validator(_load(ADJUDICATION_SCHEMA_RESOURCE))
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def validate_decision_resolution_rule(rule: Mapping[str, Any]) -> None:
    if rule.get("rule_id") != RULE_ID:
        raise ProductDiscoveryError("R1.4 decision-resolution rule ID drift")
    if artifact_sha256(rule, digest_field="rule_sha256") != rule.get("rule_sha256"):
        raise ProductDiscoveryError("R1.4 decision-resolution rule digest mismatch")
    if rule.get("rule_sha256") != RULE_SHA256:
        raise ProductDiscoveryError("R1.4 frozen decision-resolution rule digest drift")
    if rule.get("status") != "FROZEN":
        raise ProductDiscoveryError("R1.4 decision-resolution rule must be FROZEN")
    if rule.get("source_workbench_main_commit") != SOURCE_WORKBENCH_MAIN_COMMIT:
        raise ProductDiscoveryError("R1.4 source Workbench commit drift")
    if rule.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("R1.4 analysis universe drift")
    if rule.get("world_time_cutoff") != WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("R1.4 world-time cutoff drift")
    if rule.get("knowledge_time_cutoff") != KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("R1.4 knowledge-time cutoff drift")
    if rule.get("population_view_id") != POPULATION_VIEW_ID:
        raise ProductDiscoveryError("R1.4 population view drift")
    if rule.get("r1_2_candidate_resolution_manifest_sha256") != R1_LEDGER_MANIFEST_SHA256:
        raise ProductDiscoveryError("R1.4 R1.2 manifest binding drift")
    if rule.get("r1_2_candidate_cluster_ledger_sha256") != R1_CLUSTER_LEDGER_SHA256:
        raise ProductDiscoveryError("R1.4 R1.2 cluster binding drift")
    if rule.get("r1_3_resolution_completeness_rule_sha256") != R1_3_RULE_SHA256:
        raise ProductDiscoveryError("R1.4 R1.3 rule binding drift")
    if rule.get("r1_3_resolution_completeness_checkpoint_sha256") != R1_3_CHECKPOINT_SHA256:
        raise ProductDiscoveryError("R1.4 R1.3 checkpoint binding drift")

    selection = cast(Mapping[str, Any], rule["selection_contract"])
    if selection.get("marginal_yield_frames") != list(MARGINAL_YIELD_FRAMES):
        raise ProductDiscoveryError("R1.4 marginal-yield frame selection drift")
    if selection.get("marginal_yield_rounds") != ["R2", "R3"]:
        raise ProductDiscoveryError("R1.4 marginal-yield round selection drift")
    if selection.get("include_if_any") != [
        "MARGINAL_YIELD_R2_R3",
        "A3_CAPABILITY_INCREMENT",
        "A4_MULTILINGUAL_INCREMENT",
    ]:
        raise ProductDiscoveryError("R1.4 decision-relevant selection predicate drift")
    if selection.get("temporal_state_reviews") != list(TEMPORAL_REVIEW_OFFERINGS):
        raise ProductDiscoveryError("R1.4 temporal-review offering set drift")
    if selection.get("preserve_exact_cross_frame_cluster_identity") is not True:
        raise ProductDiscoveryError("R1.4 must preserve exact cross-frame cluster identity")
    if selection.get("probability_sampling_substitution_permitted") is not False:
        raise ProductDiscoveryError("R1.4 cannot substitute probability sampling for the frozen worklist")

    if set(cast(Sequence[str], rule["adjudication_dispositions"])) != ADJUDICATION_DISPOSITIONS:
        raise ProductDiscoveryError("R1.4 adjudication disposition set drift")
    if set(cast(Sequence[str], rule["adjudicator_states"])) != ADJUDICATOR_STATES:
        raise ProductDiscoveryError("R1.4 adjudicator-state set drift")
    if set(cast(Sequence[str], rule["evidence_roles"])) != EVIDENCE_ROLES:
        raise ProductDiscoveryError("R1.4 evidence-role set drift")
    if set(cast(Sequence[str], rule["supported_propositions"])) != SUPPORTED_PROPOSITIONS:
        raise ProductDiscoveryError("R1.4 supported-proposition set drift")

    identity = cast(Mapping[str, Any], rule["identity_authority"])
    if identity.get("worklist_may_allocate_canonical_product_identity") is not False:
        raise ProductDiscoveryError("R1.4 worklist must not allocate canonical PRODUCT identity")
    if identity.get("new_identity_disposition_requires_separate_identity_authority_successor") is not True:
        raise ProductDiscoveryError("R1.4 new-identity disposition must require separate identity authority")

    cardinality = cast(Mapping[str, Any], rule["cardinality_rule"])
    if cardinality.get("one_object_upper_bound_requires_cardinality_specific_evidence") is not True:
        raise ProductDiscoveryError("R1.4 one-object bound must require cardinality evidence")
    if cardinality.get("one_object_upper_bound_max_incremental_offering_contribution") != 1:
        raise ProductDiscoveryError("R1.4 one-object bound contribution must equal one")
    if cardinality.get("source_or_abstention_barrier_remains_unbounded_without_source_specific_finite_bound") is not True:
        raise ProductDiscoveryError("R1.4 source barriers must fail closed without source-specific finite bounds")

    temporal = cast(Mapping[str, Any], rule["temporal_state_rule"])
    if temporal.get("target_offerings") != list(TEMPORAL_REVIEW_OFFERINGS):
        raise ProductDiscoveryError("R1.4 temporal-state target set drift")
    if temporal.get("qualifying_currentness_state") != "CURRENT":
        raise ProductDiscoveryError("R1.4 qualifying currentness state drift")
    if set(cast(Sequence[str], temporal["qualifying_lifecycle_states"])) != QUALIFYING_LIFECYCLE_STATES:
        raise ProductDiscoveryError("R1.4 qualifying lifecycle-state set drift")
    if temporal.get("preserve_nonqualification_without_admissible_currentness_and_lifecycle_support") is not True:
        raise ProductDiscoveryError("R1.4 temporal-state review must fail closed on missing support")

    finality = cast(Mapping[str, Any], rule["finality"])
    if finality.get("checkpoint_only_until_knowledge_window_disposition") is not True:
        raise ProductDiscoveryError("R1.4 must remain checkpoint-only until temporal disposition")
    if finality.get("final_r1_3_rebind_required") is not True:
        raise ProductDiscoveryError("R1.4 must retain the final R1.3 rebind requirement")
    for field in (
        "release_a_r1_passed",
        "release_a_final_denominator_authorized",
        "release_b_c_d_denominator_consumption_authorized",
        "publication_authority",
        "population_generalization_authority",
    ):
        if finality.get(field) is not False:
            raise ProductDiscoveryError(f"R1.4 forbidden authority enabled: {field}")


def load_decision_resolution_rule() -> dict[str, Any]:
    rule = _load(RULE_RESOURCE)
    validate_decision_resolution_rule(rule)
    return rule


def _tail_marginal_selected(cluster: Mapping[str, Any]) -> bool:
    if not bool(cluster["could_change_marginal_yield_stop"]):
        return False
    for frame_round in cast(Sequence[str], cluster["frame_rounds"]):
        frame_id, round_id = frame_round.split(":", 1)
        if frame_id in MARGINAL_YIELD_FRAMES and round_id in MARGINAL_YIELD_ROUNDS:
            return True
    return False


def _candidate_selection_reasons(cluster: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _tail_marginal_selected(cluster):
        reasons.append("MARGINAL_YIELD_R2_R3")
    if bool(cluster["could_change_a3_increment"]):
        reasons.append("A3_CAPABILITY_INCREMENT")
    if bool(cluster["could_change_a4_increment"]):
        reasons.append("A4_MULTILINGUAL_INCREMENT")
    return reasons


def _derive_candidate_work_items(
    records: Sequence[Mapping[str, Any]],
    clusters: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records_by_cluster: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        records_by_cluster[str(record["candidate_cluster_id"])].append(record)

    work_items: list[dict[str, Any]] = []
    for cluster in clusters:
        reasons = _candidate_selection_reasons(cluster)
        if not reasons:
            continue
        cluster_id = str(cluster["candidate_cluster_id"])
        cluster_records = records_by_cluster[cluster_id]
        work_items.append(
            {
                "work_item_id": f"R1WI-{cluster_id.removeprefix('R1CC-')}",
                "work_item_type": "CANDIDATE_CLUSTER_REVIEW",
                "candidate_cluster_id": cluster_id,
                "selection_reasons": reasons,
                "predecessor_uncertainty_cardinality_class": cluster["uncertainty_cardinality_class"],
                "predecessor_cluster_state": cluster["cluster_state"],
                "predecessor_noncanonical_cluster": cluster["noncanonical_cluster"],
                "source_or_abstention_barrier": bool(cluster["source_or_abstention_barrier"]),
                "frame_rounds": list(cluster["frame_rounds"]),
                "outcomes": list(cluster["outcomes"]),
                "capture_ids": list(cluster["capture_ids"]),
                "source_packet_ids": sorted({str(record["source_packet_id"]) for record in cluster_records}),
                "source_observation_refs": sorted(
                    {
                        str(record["source_observation_ref"])
                        for record in cluster_records
                        if record.get("source_observation_ref")
                    }
                ),
                "raw_candidate_keys": list(cluster["raw_candidate_keys"]),
                "normalized_candidate_key": cluster["normalized_candidate_key"],
                "canonical_offering_id": cluster["canonical_offering_id"],
                "could_change_a3_increment": bool(cluster["could_change_a3_increment"]),
                "could_change_a4_increment": bool(cluster["could_change_a4_increment"]),
                "could_change_marginal_yield_stop": bool(cluster["could_change_marginal_yield_stop"]),
            }
        )
    return work_items


def _derive_temporal_work_items() -> list[dict[str, Any]]:
    registry = load_r1_product_registry()
    rows = {
        str(row["canonical_entity_id"]): row
        for row in cast(Sequence[Mapping[str, Any]], registry["rows"])
    }
    result: list[dict[str, Any]] = []
    for canonical_id in TEMPORAL_REVIEW_OFFERINGS:
        row = rows[canonical_id]
        result.append(
            {
                "work_item_id": f"R1WI-TEMPORAL-{canonical_id}",
                "work_item_type": "A_P1_TEMPORAL_STATE_REVIEW",
                "canonical_offering_id": canonical_id,
                "selection_reasons": ["A_P1_TEMPORAL_STATE"],
                "predecessor_registry_row_id": row["registry_row_id"],
                "predecessor_currentness_state": row["currentness_state"],
                "predecessor_lifecycle_state": row["lifecycle_state"],
                "source_observation_refs": list(row["source_observation_refs"]),
                "projected_assertion_refs": list(row["projected_assertion_refs"]),
            }
        )
    return result


def derive_decision_resolution_worklist() -> dict[str, Any]:
    rule = load_decision_resolution_rule()
    checkpoint = load_resolution_completeness_checkpoint()
    if checkpoint["packet_sha256"] != R1_3_CHECKPOINT_SHA256:
        raise ProductDiscoveryError("R1.4 derivation does not bind the exact R1.3 checkpoint")

    manifest = load_r1_candidate_resolution_manifest()
    records = compile_r1_source_records(manifest)
    clusters = build_r1_candidate_clusters(records)

    candidate_items = _derive_candidate_work_items(records, clusters)
    temporal_items = _derive_temporal_work_items()
    work_items = candidate_items + temporal_items
    work_items.sort(key=lambda item: str(item["work_item_id"]))

    selected_clusters = [
        cluster
        for cluster in clusters
        if _candidate_selection_reasons(cluster)
    ]
    accounting = {
        "candidate_cluster_work_item_count": len(candidate_items),
        "temporal_state_work_item_count": len(temporal_items),
        "total_work_item_count": len(work_items),
        "marginal_yield_r2_r3_cluster_count": sum(_tail_marginal_selected(cluster) for cluster in selected_clusters),
        "a3_sensitive_cluster_count": sum(bool(cluster["could_change_a3_increment"]) for cluster in selected_clusters),
        "a4_sensitive_cluster_count": sum(bool(cluster["could_change_a4_increment"]) for cluster in selected_clusters),
        "marginal_and_a3_overlap_count": sum(
            _tail_marginal_selected(cluster) and bool(cluster["could_change_a3_increment"])
            for cluster in selected_clusters
        ),
        "marginal_and_a4_overlap_count": sum(
            _tail_marginal_selected(cluster) and bool(cluster["could_change_a4_increment"])
            for cluster in selected_clusters
        ),
        "a3_and_a4_overlap_count": sum(
            bool(cluster["could_change_a3_increment"]) and bool(cluster["could_change_a4_increment"])
            for cluster in selected_clusters
        ),
        "predecessor_cardinality_unproven_count": sum(
            cluster["uncertainty_cardinality_class"] == "UNRESOLVED_CARDINALITY_UNPROVEN"
            for cluster in selected_clusters
        ),
        "predecessor_unbounded_barrier_count": sum(
            cluster["uncertainty_cardinality_class"] == "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"
            for cluster in selected_clusters
        ),
        "predecessor_one_object_upper_bound_count": sum(
            cluster["uncertainty_cardinality_class"] == "ONE_OBJECT_UPPER_BOUND"
            for cluster in selected_clusters
        ),
    }
    return {
        "worklist_id": WORKLIST_ID,
        "version": "1.0",
        "status": "FROZEN_PRE_EXECUTION",
        "assembled_on": "2026-09-27",
        "rule_id": RULE_ID,
        "rule_sha256": RULE_SHA256,
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "r1_2_candidate_resolution_manifest_sha256": R1_LEDGER_MANIFEST_SHA256,
        "r1_2_candidate_cluster_ledger_sha256": R1_CLUSTER_LEDGER_SHA256,
        "r1_3_resolution_completeness_rule_sha256": R1_3_RULE_SHA256,
        "r1_3_resolution_completeness_checkpoint_sha256": R1_3_CHECKPOINT_SHA256,
        "accounting": accounting,
        "work_items": work_items,
        "execution_state": "NO_ADJUDICATION_EXECUTED_BY_THIS_ARTIFACT",
        "boundary": (
            "This artifact is a deterministic pre-execution worklist. Selection does not resolve identity, scope, "
            "currentness, lifecycle, cardinality, source completeness, marginal yield, A3/A4 increments, or "
            "Release-A authority."
        ),
    }


def validate_decision_resolution_worklist(worklist: Mapping[str, Any]) -> None:
    if worklist.get("worklist_id") != WORKLIST_ID:
        raise ProductDiscoveryError("R1.4 worklist ID drift")
    if artifact_sha256(worklist, digest_field="worklist_sha256") != worklist.get("worklist_sha256"):
        raise ProductDiscoveryError("R1.4 worklist digest mismatch")
    if worklist.get("worklist_sha256") != WORKLIST_SHA256:
        raise ProductDiscoveryError("R1.4 frozen worklist digest drift")
    if worklist.get("status") != "FROZEN_PRE_EXECUTION":
        raise ProductDiscoveryError("R1.4 worklist must remain pre-execution")
    if worklist.get("execution_state") != "NO_ADJUDICATION_EXECUTED_BY_THIS_ARTIFACT":
        raise ProductDiscoveryError("R1.4 frozen worklist cannot contain executed adjudication state")

    derived = derive_decision_resolution_worklist()
    materialized = {key: value for key, value in worklist.items() if key != "worklist_sha256"}
    if materialized != derived:
        raise ProductDiscoveryError("R1.4 worklist does not reproduce from frozen upstream artifacts")

    work_items = cast(Sequence[Mapping[str, Any]], worklist["work_items"])
    item_ids = [str(item["work_item_id"]) for item in work_items]
    if len(item_ids) != len(set(item_ids)):
        raise ProductDiscoveryError("R1.4 worklist contains duplicate work_item_id values")
    cluster_ids = [
        str(item["candidate_cluster_id"])
        for item in work_items
        if item["work_item_type"] == "CANDIDATE_CLUSTER_REVIEW"
    ]
    if len(cluster_ids) != len(set(cluster_ids)):
        raise ProductDiscoveryError("R1.4 worklist duplicates a governed candidate cluster")


def load_decision_resolution_worklist() -> dict[str, Any]:
    worklist = _load(WORKLIST_RESOURCE)
    validate_decision_resolution_worklist(worklist)
    return worklist


def adjudication_record_id(record: Mapping[str, Any]) -> str:
    material = {key: value for key, value in record.items() if key != "adjudication_id"}
    return "R1ADJ-" + canonical_sha256(material)


def _parse_datetime(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductDiscoveryError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ProductDiscoveryError(f"{field} must include a timezone")
    return parsed


def _parse_world_date(value: str, *, field: str) -> date:
    try:
        if len(value) == 10:
            return date.fromisoformat(value)
        return _parse_datetime(value, field=field).date()
    except ValueError as exc:
        raise ProductDiscoveryError(f"{field} must identify an ISO-8601 date or timestamp") from exc


def _historical_evidence(evidence: Mapping[str, Any]) -> bool:
    if evidence["evidence_role"] == "POST_CUTOFF_CURRENT_STATE_ONLY":
        return False
    if evidence["supports_state_at_or_before_world_cutoff"] is not True:
        return False
    world_ref = evidence.get("supported_world_time_ref")
    if not isinstance(world_ref, str) or not world_ref:
        return False
    return _parse_world_date(world_ref, field="supported_world_time_ref") <= date.fromisoformat(WORLD_TIME_CUTOFF)


def _historical_propositions(evidence: Sequence[Mapping[str, Any]]) -> set[str]:
    propositions: set[str] = set()
    for item in evidence:
        if _historical_evidence(item):
            propositions.update(str(value) for value in cast(Sequence[str], item["supported_propositions"]))
    return propositions


def validate_resolution_adjudication(
    record: Mapping[str, Any],
    *,
    worklist: Mapping[str, Any] | None = None,
) -> None:
    schema_errors = _schema_errors(record)
    if schema_errors:
        raise ProductDiscoveryError("R1.4 adjudication schema validation failed: " + "; ".join(schema_errors))
    if record["adjudication_id"] != adjudication_record_id(record):
        raise ProductDiscoveryError("R1.4 adjudication_id does not match deterministic content")

    active_worklist = load_decision_resolution_worklist() if worklist is None else worklist
    validate_decision_resolution_worklist(active_worklist)
    work_items = {
        str(item["work_item_id"]): item
        for item in cast(Sequence[Mapping[str, Any]], active_worklist["work_items"])
    }
    work_item_id = str(record["work_item_id"])
    if work_item_id not in work_items:
        raise ProductDiscoveryError("R1.4 adjudication references a work item outside the frozen worklist")
    work_item = work_items[work_item_id]

    disposition = str(record["disposition"])
    if disposition not in ADJUDICATION_DISPOSITIONS:
        raise ProductDiscoveryError("R1.4 adjudication disposition is not frozen")
    adjudicator_state = str(record["adjudicator_state"])
    adjudicator_id = record.get("adjudicator_id")
    if adjudicator_state == "HUMAN_REVIEWED":
        if not isinstance(adjudicator_id, str) or not adjudicator_id.strip():
            raise ProductDiscoveryError("Human-reviewed R1.4 adjudication requires adjudicator_id")
    elif adjudicator_id is not None:
        raise ProductDiscoveryError("Machine-provisional R1.4 adjudication must keep adjudicator_id null")
    if disposition in TERMINAL_OR_BOUND_DISPOSITIONS and adjudicator_state != "HUMAN_REVIEWED":
        raise ProductDiscoveryError("Terminal or finite-bound R1.4 disposition requires human review")

    evidence = cast(Sequence[Mapping[str, Any]], record["evidence"])
    seen_refs: set[str] = set()
    knowledge_cutoff = _parse_datetime(KNOWLEDGE_TIME_CUTOFF, field="knowledge_time_cutoff")
    for item in evidence:
        ref = str(item["evidence_ref"])
        if ref in seen_refs:
            raise ProductDiscoveryError("R1.4 adjudication evidence_ref values must be unique")
        seen_refs.add(ref)
        if item["evidence_role"] not in EVIDENCE_ROLES:
            raise ProductDiscoveryError("R1.4 adjudication evidence role is not frozen")
        propositions = set(cast(Sequence[str], item["supported_propositions"]))
        if not propositions <= SUPPORTED_PROPOSITIONS:
            raise ProductDiscoveryError("R1.4 adjudication contains an unknown supported proposition")
        observed = _parse_datetime(str(item["knowledge_observed_at"]), field="knowledge_observed_at")
        if observed > knowledge_cutoff:
            raise ProductDiscoveryError("R1.4 evidence exceeds the frozen knowledge-time cutoff")

        role = str(item["evidence_role"])
        supports_historical = bool(item["supports_state_at_or_before_world_cutoff"])
        world_ref = item.get("supported_world_time_ref")
        if role == "POST_CUTOFF_CURRENT_STATE_ONLY":
            if supports_historical or world_ref is not None:
                raise ProductDiscoveryError("Post-cutoff current-only evidence cannot be back-projected")
        else:
            if not supports_historical or not isinstance(world_ref, str) or not world_ref:
                raise ProductDiscoveryError("Historical R1.4 evidence must bind a supported world-time reference")
            if _parse_world_date(world_ref, field="supported_world_time_ref") > date.fromisoformat(WORLD_TIME_CUTOFF):
                raise ProductDiscoveryError("R1.4 historical evidence supports state only after the world-time cutoff")

    historical_props = _historical_propositions(evidence)
    existing_canonical = record.get("existing_canonical_offering_id")
    one_object = bool(record["one_object_upper_bound"])
    max_contribution = record.get("max_incremental_offering_contribution")

    if disposition == "TERMINAL_INCLUDE_EXISTING_CANONICAL":
        if not isinstance(existing_canonical, str) or not existing_canonical:
            raise ProductDiscoveryError("Existing-canonical inclusion requires an existing canonical offering ID")
        registry = load_r1_product_registry()
        known_ids = {
            str(row["canonical_entity_id"])
            for row in cast(Sequence[Mapping[str, Any]], registry["rows"])
        }
        if existing_canonical not in known_ids:
            raise ProductDiscoveryError("R1.4 cannot invent an existing canonical offering identity")
        if not {"IDENTITY", "SCOPE"} <= historical_props:
            raise ProductDiscoveryError("Existing-canonical inclusion requires historical identity and scope support")
        if one_object or max_contribution is not None:
            raise ProductDiscoveryError("Terminal inclusion cannot also declare an unresolved one-object bound")
    elif disposition == "TERMINAL_INCLUDE_NEW_CANONICAL_PENDING_IDENTITY_AUTHORITY":
        if existing_canonical is not None:
            raise ProductDiscoveryError("Pending new canonical identity must not populate existing_canonical_offering_id")
        if not {"IDENTITY", "SCOPE"} <= historical_props:
            raise ProductDiscoveryError("Pending new identity requires historical identity and scope support")
        if one_object or max_contribution is not None:
            raise ProductDiscoveryError("Pending new identity cannot also declare an unresolved one-object bound")
    elif disposition == "TERMINAL_EXCLUDE":
        if work_item["work_item_type"] == "CANDIDATE_CLUSTER_REVIEW" and existing_canonical is not None:
            raise ProductDiscoveryError("Excluded candidate cluster must not allocate an existing canonical identity")
        if "SCOPE" not in historical_props:
            raise ProductDiscoveryError("Terminal exclusion requires historical scope support")
        if one_object or max_contribution is not None:
            raise ProductDiscoveryError("Terminal exclusion cannot also declare an unresolved one-object bound")
    elif disposition == "ONE_OBJECT_UPPER_BOUND_UNRESOLVED":
        if existing_canonical is not None:
            raise ProductDiscoveryError("One-object unresolved bound cannot allocate canonical identity")
        if not one_object or max_contribution != 1:
            raise ProductDiscoveryError("One-object unresolved bound requires an exact maximum contribution of one")
        if "CARDINALITY" not in historical_props:
            raise ProductDiscoveryError("One-object unresolved bound requires historical cardinality support")
        if bool(work_item.get("source_or_abstention_barrier")):
            source_bound = any(
                item["evidence_role"] == "SOURCE_ENUMERATION_SPECIFIC"
                and _historical_evidence(item)
                and (
                    "SOURCE_ENUMERATION" in item["supported_propositions"]
                    or "CARDINALITY" in item["supported_propositions"]
                )
                for item in evidence
            )
            if not source_bound:
                raise ProductDiscoveryError("Source/abstention barrier requires source-specific finite-bound evidence")
    else:
        if existing_canonical is not None:
            raise ProductDiscoveryError("Unresolved disposition cannot allocate canonical identity")
        if one_object or max_contribution is not None:
            raise ProductDiscoveryError("Unresolved disposition cannot imply a finite one-object bound")

    if work_item["work_item_type"] == "A_P1_TEMPORAL_STATE_REVIEW":
        subject_id = str(work_item["canonical_offering_id"])
        if existing_canonical is not None and existing_canonical != subject_id:
            raise ProductDiscoveryError("Temporal-state review cannot change its canonical offering subject")
        if disposition == "TERMINAL_INCLUDE_EXISTING_CANONICAL":
            if not {"CURRENTNESS", "LIFECYCLE"} <= historical_props:
                raise ProductDiscoveryError("A-P1 inclusion requires historical currentness and lifecycle support")
            if record.get("proposed_currentness_state") != "CURRENT":
                raise ProductDiscoveryError("A-P1 inclusion requires proposed CURRENT state")
            if record.get("proposed_lifecycle_state") not in QUALIFYING_LIFECYCLE_STATES:
                raise ProductDiscoveryError("A-P1 inclusion requires a qualifying lifecycle state")
        elif disposition == "TERMINAL_EXCLUDE":
            currentness = record.get("proposed_currentness_state")
            lifecycle = record.get("proposed_lifecycle_state")
            if currentness == "CURRENT" and lifecycle in QUALIFYING_LIFECYCLE_STATES:
                raise ProductDiscoveryError("Temporal exclusion contradicts a fully qualifying A-P1 state")
            if not ({"CURRENTNESS", "LIFECYCLE"} & historical_props):
                raise ProductDiscoveryError("Temporal exclusion requires historical currentness or lifecycle support")
        else:
            raise ProductDiscoveryError(
                "Temporal-state work items may terminate only as existing-canonical inclusion or exclusion"
            )
    elif record.get("proposed_currentness_state") is not None or record.get("proposed_lifecycle_state") is not None:
        raise ProductDiscoveryError("Candidate-cluster review cannot mutate offering currentness/lifecycle state")
