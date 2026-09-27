"""Release-A R1 candidate-unit construct-validity audit.

The historical A2 marginal-yield protocol defines its denominator as capture rows.
This successor audit preserves those historical bytes and asks a separate question:
which capture rows are governed product/offering candidate objects, source/query
probes, literature/record probes, or unresolved empirical units?
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import _packet_content_sha256
from neuroai_workbench.product_discovery_frames import DEFAULT_ANALYSIS_UNIVERSE_ID, ProductDiscoveryError
from neuroai_workbench.release_a_r1_decision_resolution import (
    WORKLIST_SHA256 as R1_4_WORKLIST_SHA256,
)
from neuroai_workbench.release_a_r1_decision_resolution import load_decision_resolution_worklist
from neuroai_workbench.release_a_r1_resolution import (
    DISCOVERY_RESOURCE_PACKAGE,
    R1_CLUSTER_LEDGER_SHA256,
    R1_LEDGER_MANIFEST_SHA256,
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)

RULE_RESOURCE = "RELEASE_A_R1_CANDIDATE_UNIT_AUDIT_RULE.v1.0.json"
AUDIT_RESOURCE = "RELEASE_A_R1_CANDIDATE_UNIT_AUDIT_CHECKPOINT.v1.0.json"

RULE_ID = "RELEASE_A_R1_CANDIDATE_UNIT_AUDIT_RULE_v1.0"
AUDIT_ID = "RELEASE_A_R1_CANDIDATE_UNIT_AUDIT_CHECKPOINT_v1.0"
RULE_SHA256 = "9249c958ca66a07b326cb3f237da280a28965372f12f3623405a049adc8ad0d6"
AUDIT_SHA256 = "c229667ae50ef71396837c1e34b5edf016c3ed224c771ae15cab20377bda384a"
SOURCE_WORKBENCH_MAIN_COMMIT = "73689e59960677460b5130022a7321b37d2c51cc"
WORLD_TIME_CUTOFF = "2026-09-24"
KNOWLEDGE_TIME_CUTOFF = "2026-10-24T23:59:59Z"
POPULATION_VIEW_ID = "A-P1"

R1_3_RULE_SHA256 = "8ef1b0700e67a5d3737ae56f22e530cd239cb8ed9bdaacf3c1b2dc4ba5255cb1"
R1_3_CHECKPOINT_SHA256 = "500bcd90ad59b4320a1f2a9eec857f81ce83b45e501f1d38853e8ae8ea37485d"
R1_4_RULE_SHA256 = "0e4ea20af846b18e59cabfb338e59ab2cff4b9566e7ea1a3b18f8cc7f825f771"

AUDITED_FRAMES = ("F1", "F4", "F5", "F6", "F8", "F11")
AUDITED_ROUNDS = ("R2", "R3")
UNIT_CLASSES = (
    "OFFERING_CANDIDATE_OBJECT",
    "SOURCE_OR_QUERY_PROBE",
    "LITERATURE_OR_RECORD_PROBE",
    "UNRESOLVED_EMPIRICAL_UNIT",
)

PACKET_RESOURCES = {
    "F1": "RELEASE_A_A2_F1_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F4": "RELEASE_A_A2_F4_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F5": "RELEASE_A_A2_F5_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F6": "RELEASE_A_A2_F6_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F8": "RELEASE_A_A2_F8_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
    "F11": "RELEASE_A_A2_F11_OPEN_WORLD_ROUNDS_1_3_TRANCHE_1.v1.0.json",
}
PACKET_SHA256 = {
    "F1": "4d4f8fdf655882315a6f53499f4932e91d1596c29c1a873c86dde243cd9c4c85",
    "F4": "abaff10977ad1f7f84b3311b6619d403184da4d94d805714913851c7d87ebfc3",
    "F5": "0ce4e51a4f968ef452a1031d651e30119498fd4969563f91cadbccdeb2eaf3f5",
    "F6": "95e13cc7dc896a0bad3f2d3862fda7475ff5e35291341f6bdbe5b9a0372e2e4c",
    "F8": "07e79f2ba1501379315850d3756cb4758f632b5f337e47a140fe50c861e2043f",
    "F11": "e6da0402653a89bb1c55e61b630864271f80daa7d0a1f11cc38d451917d3e88a",
}

AGGREGATE_DISPOSITION = "NO_HISTORICAL_MARGINAL_YIELD_FRAME_CURRENTLY_SUPPORTS_CANDIDATE_UNIT_SATURATION"


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


def validate_candidate_unit_audit_rule(rule: Mapping[str, Any]) -> None:
    if rule.get("rule_id") != RULE_ID:
        raise ProductDiscoveryError("R1.5 candidate-unit audit rule ID drift")
    if artifact_sha256(rule, digest_field="rule_sha256") != rule.get("rule_sha256"):
        raise ProductDiscoveryError("R1.5 candidate-unit audit rule digest mismatch")
    if rule.get("rule_sha256") != RULE_SHA256:
        raise ProductDiscoveryError("R1.5 frozen rule digest drift")
    expected = {
        "status": "FROZEN",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "population_view_id": POPULATION_VIEW_ID,
        "r1_2_candidate_resolution_manifest_sha256": R1_LEDGER_MANIFEST_SHA256,
        "r1_2_candidate_cluster_ledger_sha256": R1_CLUSTER_LEDGER_SHA256,
        "r1_3_resolution_completeness_rule_sha256": R1_3_RULE_SHA256,
        "r1_3_resolution_completeness_checkpoint_sha256": R1_3_CHECKPOINT_SHA256,
        "r1_4_worklist_rule_sha256": R1_4_RULE_SHA256,
        "r1_4_worklist_sha256": R1_4_WORKLIST_SHA256,
        "audited_frames": list(AUDITED_FRAMES),
        "audited_rounds": list(AUDITED_ROUNDS),
    }
    for field, value in expected.items():
        if rule.get(field) != value:
            raise ProductDiscoveryError(f"R1.5 candidate-unit audit {field} drift")

    mechanical = cast(Mapping[str, Any], rule["historical_mechanical_contract"])
    if mechanical != {
        "C_capture_definition": "len(captures) in summarize_discovery_round",
        "marginal_yield_definition": "new_resolved_include_identities / C_capture",
        "minimum_completed_rounds": 3,
        "consecutive_low_yield_rounds": 2,
        "maximum_marginal_new_identity_yield": 0.05,
        "minimum_raw_candidates_per_round": 20,
        "historical_packets_and_stop_states_immutable": True,
    }:
        raise ProductDiscoveryError("R1.5 historical mechanical contract drift")

    classification = cast(Mapping[str, Any], rule["classification_contract"])
    if classification.get("all_other_nonterminal_rows_default_to") != "UNRESOLVED_EMPIRICAL_UNIT":
        raise ProductDiscoveryError("R1.5 unresolved empirical-unit default drift")
    if classification.get("inference_from_product_looking_name_alone_prohibited") is not True:
        raise ProductDiscoveryError("R1.5 must prohibit product-looking-name inference")

    accounting = cast(Mapping[str, Any], rule["candidate_unit_accounting"])
    if accounting.get("candidate_denominator_identified_only_if_unresolved_empirical_unit_count_is_zero") is not True:
        raise ProductDiscoveryError("R1.5 candidate-denominator identifiability rule drift")
    if accounting.get("historical_numeric_floor_sensitivity") != 20:
        raise ProductDiscoveryError("R1.5 candidate-unit numeric-floor sensitivity drift")

    finality = cast(Mapping[str, Any], rule["finality"])
    if not (
        finality.get("pre_r1_4_adjudication_checkpoint") is True
        and finality.get("final_rebind_after_r1_4_adjudication_required") is True
        and finality.get("final_rebind_after_knowledge_window_disposition_required") is True
    ):
        raise ProductDiscoveryError("R1.5 final rebind contract drift")


def load_candidate_unit_audit_rule() -> dict[str, Any]:
    rule = _load(RULE_RESOURCE)
    validate_candidate_unit_audit_rule(rule)
    return rule


def classify_capture_unit(record: Mapping[str, Any], rule: Mapping[str, Any]) -> dict[str, Any]:
    """Classify one frozen source-ledger row without inferring objecthood from its name."""

    label = str(record.get("normalized_candidate_label") or "").lower()
    if record.get("outcome") == "INCLUDE_RESOLVED" and record.get("canonical_offering_id"):
        unit_class = "OFFERING_CANDIDATE_OBJECT"
        basis = "HISTORICAL_INCLUDE_RESOLVED_CANONICAL"
        dedup_key: str | None = str(record["canonical_offering_id"])
    else:
        contract = cast(Mapping[str, Any], rule["classification_contract"])
        literature_patterns = cast(Sequence[str], contract["literature_probe_normalized_label_patterns"])
        exact_source_labels = set(cast(Sequence[str], contract["source_probe_exact_normalized_labels"]))
        source_suffixes = cast(Sequence[str], contract["source_probe_normalized_label_suffixes"])
        if any(re.search(pattern, label) for pattern in literature_patterns):
            unit_class = "LITERATURE_OR_RECORD_PROBE"
            basis = "EXPLICIT_LITERATURE_RECORD_SENTINEL"
        elif label in exact_source_labels or any(label.endswith(suffix) for suffix in source_suffixes):
            unit_class = "SOURCE_OR_QUERY_PROBE"
            basis = "EXPLICIT_SOURCE_OR_QUERY_PROBE_SENTINEL"
        else:
            unit_class = "UNRESOLVED_EMPIRICAL_UNIT"
            basis = "EMPIRICAL_UNIT_NOT_GOVERNED_PRE_ADJUDICATION"
        dedup_key = None

    return {
        "capture_id": record["capture_id"],
        "source_record_id": record["source_record_id"],
        "candidate_cluster_id": record["candidate_cluster_id"],
        "frame_id": record["frame_id"],
        "round_id": record["round_id"],
        "query_or_seed_id": record["query_or_seed_id"],
        "query_family": record["query_family"],
        "source_class": record["source_class"],
        "source_observation_ref": record.get("source_observation_ref"),
        "normalized_candidate_key": record["normalized_candidate_key"],
        "normalized_candidate_label": record["normalized_candidate_label"],
        "predecessor_outcome": record["outcome"],
        "predecessor_uncertainty_cardinality_class": record["uncertainty_cardinality_class"],
        "unit_class": unit_class,
        "classification_basis": basis,
        "candidate_object_dedup_key": dedup_key,
    }


def _validated_packet(frame_id: str) -> dict[str, Any]:
    packet = _load(PACKET_RESOURCES[frame_id])
    declared = packet.get("packet_sha256")
    if declared != PACKET_SHA256[frame_id] or _packet_content_sha256(packet) != declared:
        raise ProductDiscoveryError(f"R1.5 historical packet digest drift: {frame_id}")
    if packet.get("frame_id") != frame_id:
        raise ProductDiscoveryError(f"R1.5 historical packet frame drift: {frame_id}")
    return packet


def _historical_stop_state(packet: Mapping[str, Any]) -> str:
    state = packet.get("final_stop_state", packet.get("frame_stop_state"))
    if state is None:
        runs = cast(Sequence[Mapping[str, Any]], packet["runs"])
        state = runs[-1]["stop_state"]
    return str(state)


def _round_result(
    *,
    frame_id: str,
    round_id: str,
    classifications: Sequence[Mapping[str, Any]],
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    rows = [item for item in classifications if item["frame_id"] == frame_id and item["round_id"] == round_id]
    summaries = cast(Sequence[Mapping[str, Any]], packet["round_summaries"])
    historical = next(summary for summary in summaries if summary["round_id"] == round_id)
    if len(rows) != int(historical["raw_candidates"]):
        raise ProductDiscoveryError(f"R1.5 {frame_id}/{round_id} source rows do not reproduce C_capture")

    counts = {unit_class: 0 for unit_class in UNIT_CLASSES}
    candidate_keys: set[str] = set()
    for item in rows:
        unit_class = str(item["unit_class"])
        counts[unit_class] += 1
        if unit_class == "OFFERING_CANDIDATE_OBJECT":
            key = item.get("candidate_object_dedup_key")
            if not isinstance(key, str) or not key:
                raise ProductDiscoveryError("R1.5 governed candidate object lacks a deterministic dedup key")
            candidate_keys.add(key)

    c_candidate = len(candidate_keys)
    unresolved = counts["UNRESOLVED_EMPIRICAL_UNIT"]
    denominator_identified = unresolved == 0
    y = int(historical["new_resolved_include_identities"])
    m_candidate = y / c_candidate if denominator_identified and c_candidate > 0 else None
    numeric_floor = denominator_identified and c_candidate >= 20

    if unresolved > 0:
        state = "CANDIDATE_UNIT_RESOLUTION_CENSORED"
    elif not numeric_floor:
        state = "CANDIDATE_UNIT_DENOMINATOR_INSUFFICIENT"
    elif m_candidate is not None and m_candidate <= 0.05:
        state = "CANDIDATE_UNIT_SATURATION_IDENTIFIED"
    else:
        state = "MECHANICAL_CAPTURE_ROW_SATURATION_ONLY"

    return {
        "frame_id": frame_id,
        "round_id": round_id,
        "historical_source_packet_sha256": packet["packet_sha256"],
        "C_capture": int(historical["raw_candidates"]),
        "C_candidate": c_candidate,
        "source_or_query_probe_count": counts["SOURCE_OR_QUERY_PROBE"],
        "literature_or_record_probe_count": counts["LITERATURE_OR_RECORD_PROBE"],
        "unresolved_empirical_unit_count": unresolved,
        "offering_candidate_object_row_count": counts["OFFERING_CANDIDATE_OBJECT"],
        "new_resolved_include_identities": y,
        "m_capture": historical["marginal_new_identity_yield"],
        "m_candidate": m_candidate,
        "candidate_denominator_identified": denominator_identified,
        "candidate_object_count_meets_historical_numeric_floor": numeric_floor,
        "candidate_unit_state": state,
    }


def derive_candidate_unit_audit() -> dict[str, Any]:
    rule = load_candidate_unit_audit_rule()
    manifest = load_r1_candidate_resolution_manifest()
    worklist = load_decision_resolution_worklist()
    if worklist["worklist_sha256"] != R1_4_WORKLIST_SHA256:
        raise ProductDiscoveryError("R1.5 does not bind the exact R1.4 worklist")

    records = [
        record
        for record in compile_r1_source_records(manifest)
        if record["frame_id"] in AUDITED_FRAMES and record["round_id"] in AUDITED_ROUNDS
    ]
    classifications = [classify_capture_unit(record, rule) for record in records]
    classifications.sort(key=lambda item: (str(item["frame_id"]), str(item["round_id"]), str(item["capture_id"])))
    capture_ids = [str(item["capture_id"]) for item in classifications]
    if len(capture_ids) != len(set(capture_ids)):
        raise ProductDiscoveryError("R1.5 audited capture rows must be unique")

    packets = {frame_id: _validated_packet(frame_id) for frame_id in AUDITED_FRAMES}
    round_results = [
        _round_result(
            frame_id=frame_id,
            round_id=round_id,
            classifications=classifications,
            packet=packets[frame_id],
        )
        for frame_id in AUDITED_FRAMES
        for round_id in AUDITED_ROUNDS
    ]

    frame_results: list[dict[str, Any]] = []
    for frame_id in AUDITED_FRAMES:
        tail = [item for item in round_results if item["frame_id"] == frame_id]
        historical_stop = _historical_stop_state(packets[frame_id])
        if historical_stop != "SATURATION_UNDER_DECLARED_PROTOCOL":
            raise ProductDiscoveryError(f"R1.5 historical tail does not bind mechanical saturation: {frame_id}")

        if any(
            item["candidate_denominator_identified"] is True
            and item["candidate_object_count_meets_historical_numeric_floor"] is not True
            for item in tail
        ):
            state = "CANDIDATE_UNIT_DENOMINATOR_INSUFFICIENT"
        elif any(int(item["unresolved_empirical_unit_count"]) > 0 for item in tail):
            state = "CANDIDATE_UNIT_RESOLUTION_CENSORED"
        elif all(item["m_candidate"] is not None and float(item["m_candidate"]) <= 0.05 for item in tail):
            state = "CANDIDATE_UNIT_SATURATION_IDENTIFIED"
        else:
            state = "MECHANICAL_CAPTURE_ROW_SATURATION_ONLY"

        frame_results.append(
            {
                "frame_id": frame_id,
                "historical_final_stop_state": historical_stop,
                "historical_tail_round_ids": list(AUDITED_ROUNDS),
                "candidate_unit_scientific_state": state,
            }
        )

    counts = {unit_class: 0 for unit_class in UNIT_CLASSES}
    for item in classifications:
        counts[str(item["unit_class"])] += 1

    return {
        "audit_id": AUDIT_ID,
        "status": "CHECKPOINT_PRE_R1_4_ADJUDICATION_AND_KNOWLEDGE_WINDOW_CLOSE",
        "assembled_on": "2026-09-27",
        "source_workbench_main_commit": SOURCE_WORKBENCH_MAIN_COMMIT,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "world_time_cutoff": WORLD_TIME_CUTOFF,
        "knowledge_time_cutoff": KNOWLEDGE_TIME_CUTOFF,
        "population_view_id": POPULATION_VIEW_ID,
        "rule_id": RULE_ID,
        "rule_sha256": RULE_SHA256,
        "r1_2_candidate_resolution_manifest_sha256": R1_LEDGER_MANIFEST_SHA256,
        "r1_4_worklist_sha256": R1_4_WORKLIST_SHA256,
        "audited_capture_row_count": len(classifications),
        "unit_class_counts": counts,
        "row_classifications": classifications,
        "round_results": round_results,
        "frame_results": frame_results,
        "aggregate_scientific_disposition": AGGREGATE_DISPOSITION,
        "final_rebind_requirement": (
            "Re-run this audit after R1.4 adjudications and again after final knowledge-window disposition before "
            "#414 or Release-A R1 receives final scientific disposition."
        ),
        "authority_controls": {
            "historical_a2_mutated": False,
            "release_a_r1_passed": False,
            "release_a_final_denominator_authorized": False,
            "release_b_c_d_denominator_consumption_authorized": False,
            "population_generalization_authority": False,
            "publication_authority": False,
        },
        "boundary": (
            "This checkpoint preserves historical C_capture, yields and mechanical stop states while auditing "
            "whether those rows represent candidate product/offering units. It is pre-adjudication checkpoint "
            "evidence, not a final Release-A denominator or completeness claim."
        ),
    }


def validate_candidate_unit_audit(audit: Mapping[str, Any]) -> None:
    if audit.get("audit_id") != AUDIT_ID:
        raise ProductDiscoveryError("R1.5 candidate-unit audit ID drift")
    if artifact_sha256(audit, digest_field="audit_sha256") != audit.get("audit_sha256"):
        raise ProductDiscoveryError("R1.5 candidate-unit audit digest mismatch")
    if audit.get("audit_sha256") != AUDIT_SHA256:
        raise ProductDiscoveryError("R1.5 frozen audit digest drift")
    materialized = {key: value for key, value in audit.items() if key != "audit_sha256"}
    if materialized != derive_candidate_unit_audit():
        raise ProductDiscoveryError("R1.5 candidate-unit audit does not reproduce from frozen inputs")


def load_candidate_unit_audit() -> dict[str, Any]:
    audit = _load(AUDIT_RESOURCE)
    validate_candidate_unit_audit(audit)
    return audit
