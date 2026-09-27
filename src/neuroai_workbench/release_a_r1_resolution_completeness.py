"""Release-A R1 resolution-completeness and saturation-identifiability checkpoint.

This module adds a scientific interpretation gate above the immutable historical
A2 mechanical stopping rule. It binds the R1.2 candidate-resolution ledger,
preserves historical run bytes, and fails closed when unresolved cardinality or
source barriers prevent a finite low-yield interpretation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import _packet_content_sha256
from neuroai_workbench.product_discovery_frames import DEFAULT_ANALYSIS_UNIVERSE_ID, ProductDiscoveryError
from neuroai_workbench.release_a_r1_resolution import (
    DISCOVERY_RESOURCE_PACKAGE,
    R1_CLUSTER_LEDGER_SHA256,
    R1_LEDGER_MANIFEST_SHA256,
    build_r1_candidate_clusters,
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)

RULE_RESOURCE = "RELEASE_A_R1_RESOLUTION_COMPLETENESS_RULE.v1.0.json"
CHECKPOINT_RESOURCE = "RELEASE_A_R1_RESOLUTION_COMPLETENESS_CHECKPOINT.v1.0.json"
FRAME_REGISTER_RESOURCE = "PRODUCT_DISCOVERY_FRAME_REGISTER.v1.0.json"

RULE_ID = "RELEASE_A_R1_RESOLUTION_COMPLETENESS_RULE_v1.0"
CHECKPOINT_ID = "RELEASE_A_R1_RESOLUTION_COMPLETENESS_CHECKPOINT_v1.0"
RULE_SHA256 = "7075e7b7759bfbf3bcfa17bbc8eff6feae3793d483596ad37d2160ad345c884c"
CHECKPOINT_SHA256 = "c952a3d74c6d8f81dac8f6ac480b2645c029c9d533e50c5c8d7d153d015a22ca"
SOURCE_WORKBENCH_MAIN_COMMIT = "2ef774f4b8ec0df255c11908a5847e2edd11dbd8"
WORLD_TIME_CUTOFF = "2026-09-24"
KNOWLEDGE_TIME_CUTOFF = "2026-10-24T23:59:59Z"
POPULATION_VIEW_ID = "A-P1"

MARGINAL_FRAME_PACKET_RESOURCES = {
    "F1": "RELEASE_A_A2_F1_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F4": "RELEASE_A_A2_F4_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F5": "RELEASE_A_A2_F5_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F6": "RELEASE_A_A2_F6_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F8": "RELEASE_A_A2_F8_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F11": "RELEASE_A_A2_F11_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
}
A3_RESOURCE = "RELEASE_A_A3_CAPABILITY_FIRST_RECALL_STUDY.v1.0.json"
A4_RESOURCE = "RELEASE_A_A4_MULTILINGUAL_COVERAGE_SENSITIVITY_STUDY.v1.0.json"
A3_SHA256 = "b7a6cd6b509f1fa3b8481fbd821589b8f7c1eaf40cec8c14df992e38360285d8"
A4_SHA256 = "a82fc5081630fc0af2d8843e6ad6009a9cbcb544509ce31f2a7b1fc94d8236ed"

ONE_OBJECT = "ONE_OBJECT_UPPER_BOUND"
CARDINALITY_UNPROVEN = "UNRESOLVED_CARDINALITY_UNPROVEN"
UNBOUNDED_BARRIER = "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"
TERMINAL = "TERMINAL"


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


def validate_resolution_completeness_rule(rule: Mapping[str, Any]) -> None:
    if rule.get("rule_id") != RULE_ID:
        raise ProductDiscoveryError("R1 resolution-completeness rule ID drift")
    if artifact_sha256(rule, digest_field="rule_sha256") != rule.get("rule_sha256"):
        raise ProductDiscoveryError("R1 resolution-completeness rule digest mismatch")
    if rule.get("rule_sha256") != RULE_SHA256:
        raise ProductDiscoveryError("R1 resolution-completeness frozen rule digest drift")
    if rule.get("status") != "FROZEN":
        raise ProductDiscoveryError("R1 resolution-completeness rule must be FROZEN")
    if rule.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("R1 resolution-completeness analysis universe drift")
    if rule.get("population_view_id") != POPULATION_VIEW_ID:
        raise ProductDiscoveryError("R1 resolution-completeness population view drift")
    if rule.get("candidate_resolution_ledger_manifest_sha256") != R1_LEDGER_MANIFEST_SHA256:
        raise ProductDiscoveryError("R1 resolution-completeness ledger manifest binding drift")
    if rule.get("candidate_resolution_cluster_ledger_sha256") != R1_CLUSTER_LEDGER_SHA256:
        raise ProductDiscoveryError("R1 resolution-completeness cluster ledger binding drift")

    expected_frames = ["F1", "F4", "F5", "F6", "F8", "F11"]
    if rule.get("marginal_yield_frames") != expected_frames:
        raise ProductDiscoveryError("R1 resolution-completeness marginal frame set drift")

    mechanical = rule.get("mechanical_rule")
    expected_mechanical = {
        "minimum_completed_rounds": 3,
        "consecutive_low_yield_rounds": 2,
        "maximum_marginal_new_identity_yield": 0.05,
        "minimum_raw_candidates_per_round": 20,
    }
    if mechanical != expected_mechanical:
        raise ProductDiscoveryError("R1 resolution-completeness mechanical rule drift")

    statistical = cast(Mapping[str, Any], rule["low_yield_identifiability_paths"])["reviewed_statistical"]
    if cast(Mapping[str, Any], statistical).get("current_checkpoint_state") != (
        "NO_SEPARATELY_PREREGISTERED_STATISTICAL_PATH_BOUND"
    ):
        raise ProductDiscoveryError("R1 checkpoint must not invent a post-hoc statistical identifiability path")


def load_resolution_completeness_rule() -> dict[str, Any]:
    rule = _load(RULE_RESOURCE)
    validate_resolution_completeness_rule(rule)
    return rule


def evaluate_round_identifiability(
    *,
    C_r: int,
    Y_r: int,
    one_object_upper_bound_cluster_count: int,
    cardinality_unproven_cluster_count: int,
    unbounded_source_or_abstention_barrier_cluster_count: int,
    threshold: float,
    statistical_design_preregistered: bool = False,
    statistical_upper_bound: float | None = None,
) -> dict[str, Any]:
    """Evaluate one round without manufacturing a finite bound from unresolved barriers."""

    counts = (
        C_r,
        Y_r,
        one_object_upper_bound_cluster_count,
        cardinality_unproven_cluster_count,
        unbounded_source_or_abstention_barrier_cluster_count,
    )
    if C_r <= 0 or any(value < 0 for value in counts[1:]):
        raise ProductDiscoveryError("R1 round identifiability counts must be non-negative with C_r > 0")
    if not 0 <= threshold <= 1:
        raise ProductDiscoveryError("R1 marginal-yield threshold must lie in [0, 1]")
    if statistical_upper_bound is not None and not 0 <= statistical_upper_bound <= 1:
        raise ProductDiscoveryError("R1 statistical upper bound must lie in [0, 1]")

    m_lower = Y_r / C_r
    finite_upper_bound_available = (
        cardinality_unproven_cluster_count == 0 and unbounded_source_or_abstention_barrier_cluster_count == 0
    )
    m_upper = (Y_r + one_object_upper_bound_cluster_count) / C_r if finite_upper_bound_available else None

    exhaustive_resolution = (
        one_object_upper_bound_cluster_count == 0
        and cardinality_unproven_cluster_count == 0
        and unbounded_source_or_abstention_barrier_cluster_count == 0
    )
    worst_case_bound = finite_upper_bound_available and m_upper is not None and m_upper <= threshold
    reviewed_statistical = (
        statistical_design_preregistered
        and statistical_upper_bound is not None
        and statistical_upper_bound <= threshold
    )

    if m_lower > threshold:
        state = "NOT_LOW_YIELD"
        path = None
    elif exhaustive_resolution:
        state = "IDENTIFIABLE_LOW_YIELD"
        path = "EXHAUSTIVE_RESOLUTION"
    elif worst_case_bound:
        state = "IDENTIFIABLE_LOW_YIELD"
        path = "WORST_CASE_BOUND"
    elif reviewed_statistical:
        state = "IDENTIFIABLE_LOW_YIELD"
        path = "REVIEWED_STATISTICAL"
    else:
        state = "RESOLUTION_SOURCE_BARRIER_CENSORED"
        path = None

    return {
        "C_r": C_r,
        "Y_r": Y_r,
        "U_r_star": one_object_upper_bound_cluster_count,
        "m_r_lower": m_lower,
        "m_r_upper": m_upper,
        "finite_upper_bound_available": finite_upper_bound_available,
        "one_object_upper_bound_cluster_count": one_object_upper_bound_cluster_count,
        "cardinality_unproven_cluster_count": cardinality_unproven_cluster_count,
        "unbounded_source_or_abstention_barrier_cluster_count": (unbounded_source_or_abstention_barrier_cluster_count),
        "identifiability_state": state,
        "identifiability_path": path,
    }


def _validate_historical_packet(resource: str) -> dict[str, Any]:
    packet = _load(resource)
    declared = packet.get("packet_sha256")
    if not isinstance(declared, str) or _packet_content_sha256(packet) != declared:
        raise ProductDiscoveryError(f"Historical R1 input packet digest drift: {resource}")
    if packet.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError(f"Historical R1 input packet universe drift: {resource}")
    return packet


def _global_cluster_lookup(records: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    clusters = build_r1_candidate_clusters(records)
    return {str(cluster["candidate_cluster_id"]): cluster for cluster in clusters}


def _round_cluster_counts(
    *,
    records: Sequence[Mapping[str, Any]],
    cluster_lookup: Mapping[str, Mapping[str, Any]],
    frame_id: str,
    round_id: str,
) -> dict[str, int]:
    cluster_ids = {
        str(record["candidate_cluster_id"])
        for record in records
        if record["frame_id"] == frame_id and record["round_id"] == round_id
    }
    counts = {ONE_OBJECT: 0, CARDINALITY_UNPROVEN: 0, UNBOUNDED_BARRIER: 0, TERMINAL: 0}
    for cluster_id in cluster_ids:
        cluster = cluster_lookup[cluster_id]
        classification = str(cluster["uncertainty_cardinality_class"])
        counts[classification] = counts.get(classification, 0) + 1
    return counts


def _tail_round_ids(
    *,
    round_summaries: Sequence[Mapping[str, Any]],
    minimum_completed_rounds: int,
    consecutive_low_yield_rounds: int,
    threshold: float,
    minimum_raw_candidates_per_round: int,
) -> list[str]:
    ordered = sorted(round_summaries, key=lambda item: int(str(item["round_id"])[1:]))
    if len(ordered) < minimum_completed_rounds:
        return []
    tail = ordered[-consecutive_low_yield_rounds:]
    if len(tail) != consecutive_low_yield_rounds:
        return []
    if any(int(item["raw_candidates"]) < minimum_raw_candidates_per_round for item in tail):
        return []
    if any(float(item["marginal_new_identity_yield"]) > threshold for item in tail):
        return []
    return [str(item["round_id"]) for item in tail]


def _derive_increment_checkpoint(
    *,
    packet: Mapping[str, Any],
    packet_sha256: str,
    clusters: Sequence[Mapping[str, Any]],
    flag_field: str,
    historical_delta_field: str,
) -> dict[str, Any]:
    relevant = [cluster for cluster in clusters if bool(cluster[flag_field])]
    one_object = sum(cluster["uncertainty_cardinality_class"] == ONE_OBJECT for cluster in relevant)
    cardinality_unproven = sum(cluster["uncertainty_cardinality_class"] == CARDINALITY_UNPROVEN for cluster in relevant)
    unbounded = sum(cluster["uncertainty_cardinality_class"] == UNBOUNDED_BARRIER for cluster in relevant)
    resolved_increment = int(packet[historical_delta_field])
    finite_upper = cardinality_unproven == 0 and unbounded == 0
    increment_upper = resolved_increment + one_object if finite_upper else None
    return {
        "historical_packet_sha256": packet_sha256,
        f"historical_{historical_delta_field}": resolved_increment,
        "resolved_incremental_offering_count": resolved_increment,
        "unresolved_expanded_arm_clusters_capable_of_changing_increment": len(relevant),
        "one_object_upper_bound_cluster_count": one_object,
        "cardinality_unproven_cluster_count": cardinality_unproven,
        "unbounded_source_or_abstention_barrier_cluster_count": unbounded,
        "increment_lower_bound": resolved_increment,
        "increment_upper_bound": increment_upper,
        "finite_upper_bound_available": finite_upper,
        "disposition_coverage_state": (
            "COMPLETE_OR_FINITE_BOUNDED" if finite_upper else "INCOMPLETE_CARDINALITY_UNPROVEN_AND_UNBOUNDED"
        ),
        "successor_interpretation_state": ("INCREMENT_IDENTIFIED" if finite_upper else "INCREMENT_RESOLUTION_CENSORED"),
    }


def derive_resolution_completeness_checkpoint() -> dict[str, Any]:
    rule = load_resolution_completeness_rule()
    manifest = load_r1_candidate_resolution_manifest()
    records = compile_r1_source_records(manifest)
    clusters = build_r1_candidate_clusters(records)
    cluster_lookup = _global_cluster_lookup(records)

    frame_register = _load(FRAME_REGISTER_RESOURCE)
    frame_by_id = {str(frame["frame_id"]): frame for frame in cast(list[Mapping[str, Any]], frame_register["frames"])}
    mechanical = cast(Mapping[str, Any], rule["mechanical_rule"])
    threshold = float(mechanical["maximum_marginal_new_identity_yield"])

    shard_by_frame = {
        str(binding["frame_id"]): binding for binding in cast(list[Mapping[str, Any]], manifest["source_ledger_shards"])
    }

    frame_results: list[dict[str, Any]] = []
    for frame_id in cast(list[str], rule["marginal_yield_frames"]):
        frame = frame_by_id[frame_id]
        if frame["stopping_rule"] != mechanical:
            raise ProductDiscoveryError(f"R1 rule does not reproduce frozen stopping rule for {frame_id}")

        packet = _validate_historical_packet(MARGINAL_FRAME_PACKET_RESOURCES[frame_id])
        runs = cast(list[Mapping[str, Any]], packet["runs"])
        summaries = cast(list[Mapping[str, Any]], packet["round_summaries"])
        tail_ids = _tail_round_ids(
            round_summaries=summaries,
            minimum_completed_rounds=int(mechanical["minimum_completed_rounds"]),
            consecutive_low_yield_rounds=int(mechanical["consecutive_low_yield_rounds"]),
            threshold=threshold,
            minimum_raw_candidates_per_round=int(mechanical["minimum_raw_candidates_per_round"]),
        )

        round_results: list[dict[str, Any]] = []
        for summary in sorted(summaries, key=lambda item: int(str(item["round_id"])[1:])):
            round_id = str(summary["round_id"])
            counts = _round_cluster_counts(
                records=records,
                cluster_lookup=cluster_lookup,
                frame_id=frame_id,
                round_id=round_id,
            )
            result = evaluate_round_identifiability(
                C_r=int(summary["raw_candidates"]),
                Y_r=int(summary["new_resolved_include_identities"]),
                one_object_upper_bound_cluster_count=counts[ONE_OBJECT],
                cardinality_unproven_cluster_count=counts[CARDINALITY_UNPROVEN],
                unbounded_source_or_abstention_barrier_cluster_count=counts[UNBOUNDED_BARRIER],
                threshold=threshold,
            )
            result["round_id"] = round_id
            result["terminal_cluster_count"] = counts[TERMINAL]
            result["identifiability_required_for_terminal_decision"] = round_id in tail_ids
            result.pop("identifiability_path")
            round_results.append(result)

        historical_final = str(runs[-1]["stop_state"])
        if historical_final != "SATURATION_UNDER_DECLARED_PROTOCOL":
            scientific_state = "CONTINUE_MECHANICAL"
        elif tail_ids and all(
            result["identifiability_state"] == "IDENTIFIABLE_LOW_YIELD"
            for result in round_results
            if result["round_id"] in tail_ids
        ):
            scientific_state = "SATURATION_IDENTIFIED_UNDER_R1"
        else:
            scientific_state = "CONTINUE_RESOLUTION_CENSORED"

        frame_results.append(
            {
                "frame_id": frame_id,
                "historical_source_packet_sha256": packet["packet_sha256"],
                "r1_source_ledger_shard_sha256": shard_by_frame[frame_id]["ledger_shard_sha256"],
                "historical_final_stop_state": historical_final,
                "qualifying_tail_round_ids": tail_ids,
                "round_results": round_results,
                "scientific_interpretation_state": scientific_state,
            }
        )

    a3 = _validate_historical_packet(A3_RESOURCE)
    a4 = _validate_historical_packet(A4_RESOURCE)
    if a3["packet_sha256"] != A3_SHA256 or a4["packet_sha256"] != A4_SHA256:
        raise ProductDiscoveryError("Historical A3/A4 packet binding drift")

    accounting = cast(Mapping[str, Any], manifest["accounting"])
    return {
        "packet_id": CHECKPOINT_ID,
        "status": "CHECKPOINT_PENDING_KNOWLEDGE_WINDOW_CLOSE",
        "assembled_on": "2026-09-27",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "population_view_id": POPULATION_VIEW_ID,
        "rule_id": RULE_ID,
        "rule_sha256": RULE_SHA256,
        "candidate_resolution_ledger_manifest_sha256": R1_LEDGER_MANIFEST_SHA256,
        "candidate_resolution_cluster_ledger_sha256": R1_CLUSTER_LEDGER_SHA256,
        "global_resolution_context": {
            "raw_capture_row_count": accounting["raw_capture_row_count"],
            "governed_candidate_cluster_count": accounting["governed_candidate_cluster_count"],
            "unresolved_clusters_capable_of_changing_a_p1_membership": (
                accounting["unresolved_clusters_capable_of_changing_a_p1_membership"]
            ),
            "unresolved_clusters_capable_of_changing_marginal_yield_stop": (
                accounting["unresolved_clusters_capable_of_changing_marginal_yield_stop"]
            ),
            "cardinality_bounded_unresolved_cluster_count": accounting["cardinality_bounded_unresolved_cluster_count"],
            "cardinality_unproven_unresolved_cluster_count": accounting[
                "cardinality_unproven_unresolved_cluster_count"
            ],
            "unbounded_source_or_abstention_barrier_cluster_count": accounting[
                "unbounded_source_or_abstention_barrier_cluster_count"
            ],
        },
        "frame_results": frame_results,
        "a3_capability_increment_checkpoint": _derive_increment_checkpoint(
            packet=a3,
            packet_sha256=A3_SHA256,
            clusters=clusters,
            flag_field="could_change_a3_increment",
            historical_delta_field="delta_n_capability",
        ),
        "a4_multilingual_increment_checkpoint": _derive_increment_checkpoint(
            packet=a4,
            packet_sha256=A4_SHA256,
            clusters=clusters,
            flag_field="could_change_a4_increment",
            historical_delta_field="delta_n_multilingual",
        ),
        "aggregate_scientific_disposition": (
            "ALL_HISTORICAL_MARGINAL_YIELD_SATURATION_INTERPRETATIONS_RESOLUTION_CENSORED"
        ),
        "temporal_finality": "CHECKPOINT_PENDING_KNOWLEDGE_WINDOW_CLOSE",
        "rerun_requirement": (
            "Rebind and regenerate this checkpoint against the final #413 ledger successor after the frozen "
            "knowledge-time window is explicitly dispositioned."
        ),
        "authority_controls": {
            "release_a_r1_passed": False,
            "release_a_final_denominator_authorized": False,
            "release_b_c_d_denominator_consumption_authorized": False,
            "population_generalization_authority": False,
            "publication_authority": False,
        },
        "boundary": (
            "This checkpoint preserves historical mechanical stop states while recording that current resolution "
            "and source barriers prevent scientific low-yield identification. It is not a final Release-A "
            "denominator, completeness claim, unseen-population estimate, or downstream authorization."
        ),
    }


def validate_resolution_completeness_checkpoint(packet: Mapping[str, Any]) -> None:
    if packet.get("packet_id") != CHECKPOINT_ID:
        raise ProductDiscoveryError("R1 resolution-completeness checkpoint ID drift")
    if artifact_sha256(packet, digest_field="packet_sha256") != packet.get("packet_sha256"):
        raise ProductDiscoveryError("R1 resolution-completeness checkpoint digest mismatch")
    if packet.get("packet_sha256") != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("R1 resolution-completeness frozen checkpoint digest drift")

    derived = derive_resolution_completeness_checkpoint()
    materialized = {key: value for key, value in packet.items() if key != "packet_sha256"}
    if materialized != derived:
        raise ProductDiscoveryError("R1 resolution-completeness checkpoint does not reproduce from frozen inputs")


def load_resolution_completeness_checkpoint() -> dict[str, Any]:
    packet = _load(CHECKPOINT_RESOURCE)
    validate_resolution_completeness_checkpoint(packet)
    return packet
