"""Validators for Release-A F8 local-language and F10 patent/assignee freezes.

These contracts freeze language/jurisdiction strata, F8 query seeds, and the F10
patent/assignee candidate universe under the A2 checkpoint. Freezing does not
execute discovery rounds, allocate canonical identities, or establish saturation
or commercialization.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import CHECKPOINT_ID
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    FRAME_REGISTER_VERSION,
    FRAME_VERSION,
    ProductDiscoveryError,
    evaluate_frame_stop,
    load_default_frame_register,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

LANGUAGE_STRATA_RESOURCE = "RELEASE_A_LANGUAGE_JURISDICTION_STRATA.v1.0.json"
LANGUAGE_STRATA_ID = "RELEASE_A_LANGUAGE_JURISDICTION_STRATA_v1.0"
LANGUAGE_STRATA_SHA256 = "250102995796c6feff792acf6d7616e3d28b8c8bbefc10f1b15af5cbeafc24f4"
LANGUAGE_SCOPE_ID = "EN_PLUS_PRIORITY_NATIVE_v1"

F8_PROTOCOL_RESOURCE = "RELEASE_A_F8_ROUND_PROTOCOL.v1.0.json"
F8_PROTOCOL_ID = "RELEASE_A_F8_ROUND_PROTOCOL_v1.0"
F8_PROTOCOL_SHA256 = "fb4893f9512471919dcdd5a1d91456805ce0c62d23804e4ac0a1dc57dc8a787e"

F8_UNIVERSE_RESOURCE = "RELEASE_A_F8_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json"
F8_UNIVERSE_ID = "RELEASE_A_F8_OPEN_WORLD_QUERY_UNIVERSE_v1.0"
F8_UNIVERSE_SHA256 = "0e9ef6155520225ef9826ffb6fdfe89b85df3c706be47e1a5c8a4edea7486fe2"

F10_UNIVERSE_RESOURCE = "RELEASE_A_F10_PATENT_ASSIGNEE_CANDIDATE_UNIVERSE.v1.0.json"
F10_UNIVERSE_ID = "RELEASE_A_F10_PATENT_ASSIGNEE_CANDIDATE_UNIVERSE_v1.0"
F10_UNIVERSE_SHA256 = "7652eb4f2cee689821b59c8df00ab3822b309b762a478f57715c0e98d24d21fa"

CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"

F8_BOUNDARY = (
    "F8 local-language query/round contracts freeze predeclared native-language/"
    "jurisdiction strata and retrieval seeds under the A2 analysis universe and A2 "
    "bounded-frame checkpoint. They do not establish global completeness, unseen-population "
    "size, market share, effectiveness, commercialization, S2 publication authority, or "
    "v4.2 assessment effect. Language strata are bound before yield interpretation."
)

F10_BOUNDARY = (
    "F10 patent/assignee candidate universe freezes bibliographic patent publications and "
    "assignee strings as retrieval leads only under the A2 analysis universe. Patent ownership "
    "does not establish commercialization, product identity, deployment, or effectiveness. "
    "Semantic similarity does not create product links. INCLUDE_RESOLVED requires separate "
    "attributable product evidence. Exhaustion applies only to this frozen candidate set."
)


def content_digest(material: Mapping[str, Any], *, exclude: str) -> str:
    """Return deterministic SHA-256 for a freeze artifact, excluding a self-digest field."""

    payload = {key: value for key, value in material.items() if key != exclude}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def id_set_digest(ids: Iterable[str]) -> str:
    """Return SHA-256 over the sorted unique ID list."""

    encoded = json.dumps(sorted({str(item) for item in ids}), ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _load_resource(resource_name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(resource_name).read_text(encoding="utf-8")),
    )


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductDiscoveryError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProductDiscoveryError(f"{label} must be an array")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductDiscoveryError(f"{label} must be a non-empty string")
    return value


def _frame(frame_id: str) -> Mapping[str, Any]:
    register = load_default_frame_register()
    frames = cast(list[Mapping[str, Any]], register["frames"])
    return next(frame for frame in frames if frame["frame_id"] == frame_id)


def validate_language_jurisdiction_strata(strata: Mapping[str, Any]) -> None:
    """Validate the frozen EN_PLUS_PRIORITY_NATIVE_v1 language/jurisdiction design."""

    required = {
        "strata_id",
        "strata_sha256",
        "status",
        "language_scope_id",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "selection_rule",
        "stratum_count",
        "strata",
        "boundary",
    }
    missing = sorted(required - set(strata))
    if missing:
        raise ProductDiscoveryError(f"Language strata missing fields: {', '.join(missing)}")
    if strata["strata_id"] != LANGUAGE_STRATA_ID:
        raise ProductDiscoveryError(f"strata_id must be {LANGUAGE_STRATA_ID}")
    if strata["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("Language strata must be FROZEN_v1.0")
    if strata["strata_sha256"] != content_digest(strata, exclude="strata_sha256"):
        raise ProductDiscoveryError("strata_sha256 does not match deterministic content digest")
    if strata["language_scope_id"] != LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError(f"language_scope_id must be {LANGUAGE_SCOPE_ID}")
    if strata["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("Language strata must bind the frozen A2 analysis universe")
    if strata["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff does not match frozen A2 cutoff")
    if strata["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff does not match frozen A2 cutoff")
    if strata["a2_checkpoint_id"] != CHECKPOINT_ID or strata["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("Language strata must bind the frozen A2 checkpoint")
    rows = _require_list(strata["strata"], "strata")
    if int(strata["stratum_count"]) != len(rows):
        raise ProductDiscoveryError("stratum_count does not match strata length")
    if len(rows) < 1:
        raise ProductDiscoveryError("At least one language/jurisdiction stratum is required")
    seen: set[str] = set()
    for row in rows:
        item = _require_mapping(row, "stratum")
        stratum_id = _require_str(item.get("stratum_id"), "stratum_id")
        if stratum_id in seen:
            raise ProductDiscoveryError(f"Duplicate stratum_id: {stratum_id}")
        seen.add(stratum_id)
        _require_str(item.get("language_code"), "language_code")
        jurisdictions = _require_list(item.get("matched_jurisdictions"), "matched_jurisdictions")
        if not jurisdictions:
            raise ProductDiscoveryError(f"{stratum_id} matched_jurisdictions must be non-empty")
        _require_str(item.get("selection_basis"), "selection_basis")


def validate_f8_round_protocol(protocol: Mapping[str, Any]) -> None:
    """Validate the F8-only marginal-yield round protocol."""

    required = {
        "protocol_id",
        "protocol_sha256",
        "status",
        "frame_ids",
        "frame_version",
        "frame_register_version",
        "frame_register_blob_sha",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "round_start_known_identity_set_sha256",
        "language_scope_id",
        "language_jurisdiction_strata_id",
        "language_jurisdiction_strata_sha256",
        "stopping_rule",
        "round_accounting_fields",
        "independence_rule",
        "temporal_rule",
        "estimator_policy",
        "minimum_declared_rounds",
        "execution_gate",
        "boundary",
    }
    missing = sorted(required - set(protocol))
    if missing:
        raise ProductDiscoveryError(f"F8 round protocol missing fields: {', '.join(missing)}")
    if protocol["protocol_id"] != F8_PROTOCOL_ID:
        raise ProductDiscoveryError(f"protocol_id must be {F8_PROTOCOL_ID}")
    if protocol["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("F8 round protocol must be FROZEN_v1.0")
    if protocol["protocol_sha256"] != content_digest(protocol, exclude="protocol_sha256"):
        raise ProductDiscoveryError("protocol_sha256 does not match deterministic content digest")
    if list(protocol["frame_ids"]) != ["F8"]:
        raise ProductDiscoveryError("F8 protocol frame_ids must be exactly [F8]")
    if protocol["frame_version"] != FRAME_VERSION:
        raise ProductDiscoveryError(f"frame_version must be {FRAME_VERSION}")
    if protocol["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"frame_register_version must be {FRAME_REGISTER_VERSION}")
    if protocol["frame_register_blob_sha"] != FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("frame_register_blob_sha does not match the frozen register blob")
    if protocol["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("F8 protocol must bind the frozen A2 analysis universe")
    if protocol["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff does not match frozen A2 cutoff")
    if protocol["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff does not match frozen A2 cutoff")
    if protocol["a2_checkpoint_id"] != CHECKPOINT_ID or protocol["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("F8 protocol must bind the frozen A2 checkpoint")
    if protocol["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("F8 protocol must bind the A1 six-offering known-identity digest")
    if protocol["language_scope_id"] != LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError(f"language_scope_id must be {LANGUAGE_SCOPE_ID}")
    if protocol["language_jurisdiction_strata_id"] != LANGUAGE_STRATA_ID:
        raise ProductDiscoveryError("F8 protocol must bind the frozen language strata ID")
    if protocol["language_jurisdiction_strata_sha256"] != LANGUAGE_STRATA_SHA256:
        raise ProductDiscoveryError("F8 protocol must bind the frozen language strata digest")
    if protocol["boundary"] != F8_BOUNDARY:
        raise ProductDiscoveryError("F8 protocol boundary drift")

    stopping = _require_mapping(protocol["stopping_rule"], "stopping_rule")
    frame = _frame("F8")
    if stopping.get("mode") != "MARGINAL_YIELD":
        raise ProductDiscoveryError("F8 stopping_rule.mode must be MARGINAL_YIELD")
    if int(stopping["minimum_completed_rounds"]) != int(frame["stopping_rule"]["minimum_completed_rounds"]):
        raise ProductDiscoveryError("F8 minimum_completed_rounds drift")
    if int(stopping["consecutive_low_yield_rounds"]) != int(frame["stopping_rule"]["consecutive_low_yield_rounds"]):
        raise ProductDiscoveryError("F8 consecutive_low_yield_rounds drift")
    if float(stopping["maximum_marginal_new_identity_yield"]) != float(
        frame["stopping_rule"]["maximum_marginal_new_identity_yield"]
    ):
        raise ProductDiscoveryError("F8 maximum_marginal_new_identity_yield drift")
    if int(stopping["minimum_raw_candidates_per_round"]) != int(
        frame["stopping_rule"]["minimum_raw_candidates_per_round"]
    ):
        raise ProductDiscoveryError("F8 minimum_raw_candidates_per_round drift")
    if stopping.get("literal_tail_only") is not True:
        raise ProductDiscoveryError("literal_tail_only must be true")

    estimator = _require_mapping(protocol["estimator_policy"], "estimator_policy")
    if estimator.get("frame_capture_estimation_eligible") is not True:
        raise ProductDiscoveryError("F8 must remain capture_estimation_eligible at frame level")
    if estimator.get("f7_f9_f11_remain_estimator_excluded") is not True:
        raise ProductDiscoveryError("F7/F9/F11 must remain estimator-excluded")

    gate = _require_mapping(protocol["execution_gate"], "execution_gate")
    if gate.get("language_strata_bound_before_yield_interpretation") is not True:
        raise ProductDiscoveryError("F8 must bind language strata before yield interpretation")
    if gate.get("does_not_start_a3_or_later") is not True:
        raise ProductDiscoveryError("F8 protocol must keep A3+ out of scope")


def validate_f8_query_universe(universe: Mapping[str, Any]) -> None:
    """Validate the frozen F8 query universe."""

    required = {
        "universe_id",
        "universe_sha256",
        "status",
        "frame_id",
        "frame_version",
        "frame_register_version",
        "frame_register_blob_sha",
        "frame_class",
        "capture_estimation_eligible",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "f8_round_protocol_id",
        "f8_round_protocol_sha256",
        "language_scope_id",
        "language_jurisdiction_strata_id",
        "language_jurisdiction_strata_sha256",
        "round_start_known_identity_set_sha256",
        "query_families",
        "source_classes",
        "languages",
        "jurisdictions",
        "minimum_rounds",
        "round_seed_ids",
        "query_seeds",
        "query_seed_count",
        "query_seed_set_sha256",
        "per_round_seed_counts",
        "stopping_rule",
        "independence_rule",
        "temporal_rule",
        "boundary",
    }
    missing = sorted(required - set(universe))
    if missing:
        raise ProductDiscoveryError(f"F8 query universe missing fields: {', '.join(missing)}")
    if universe["universe_id"] != F8_UNIVERSE_ID:
        raise ProductDiscoveryError(f"universe_id must be {F8_UNIVERSE_ID}")
    if universe["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("F8 query universe must be FROZEN_v1.0")
    if universe["universe_sha256"] != content_digest(universe, exclude="universe_sha256"):
        raise ProductDiscoveryError("F8 universe_sha256 does not match deterministic content digest")
    if universe["frame_id"] != "F8":
        raise ProductDiscoveryError("F8 query universe frame_id mismatch")
    frame = _frame("F8")
    if universe["frame_class"] != frame["frame_class"]:
        raise ProductDiscoveryError("F8 frame_class does not match the frozen register")
    if bool(universe["capture_estimation_eligible"]) is not True:
        raise ProductDiscoveryError("F8 capture_estimation_eligible must be true")
    if set(universe["query_families"]) != set(frame["query_families"]):
        raise ProductDiscoveryError("F8 query_families do not match the frozen register")
    if set(universe["source_classes"]) != set(frame["source_classes"]):
        raise ProductDiscoveryError("F8 source_classes do not match the frozen register")
    if universe["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("F8 query universe must bind the frozen A2 analysis universe")
    if universe["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff does not match frozen A2 cutoff")
    if universe["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff does not match frozen A2 cutoff")
    if universe["a2_checkpoint_id"] != CHECKPOINT_ID or universe["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("F8 query universe must bind the frozen A2 checkpoint")
    if universe["f8_round_protocol_id"] != F8_PROTOCOL_ID:
        raise ProductDiscoveryError("F8 query universe must bind the F8 round protocol ID")
    if universe["f8_round_protocol_sha256"] != F8_PROTOCOL_SHA256:
        raise ProductDiscoveryError("F8 query universe must bind the F8 round protocol digest")
    if universe["language_jurisdiction_strata_sha256"] != LANGUAGE_STRATA_SHA256:
        raise ProductDiscoveryError("F8 query universe must bind the frozen language strata digest")
    if universe["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("F8 query universe must bind the A1 known-identity digest")
    if universe["boundary"] != F8_BOUNDARY:
        raise ProductDiscoveryError("F8 query universe boundary drift")
    if list(universe["minimum_rounds"]) != ["R1", "R2", "R3"]:
        raise ProductDiscoveryError("F8 minimum_rounds must be R1/R2/R3")

    seeds = _require_list(universe["query_seeds"], "query_seeds")
    if int(universe["query_seed_count"]) != len(seeds):
        raise ProductDiscoveryError("F8 query_seed_count does not match query_seeds length")
    seed_ids: list[str] = []
    seen: set[str] = set()
    round_seed_ids = _require_mapping(universe["round_seed_ids"], "round_seed_ids")
    rebuilt: dict[str, list[str]] = {"R1": [], "R2": [], "R3": []}
    allowed_families = set(cast(list[str], universe["query_families"]))
    allowed_sources = set(cast(list[str], universe["source_classes"]))
    for seed in seeds:
        seed_map = _require_mapping(seed, "query_seed")
        seed_id = _require_str(seed_map.get("query_or_seed_id"), "query_or_seed_id")
        if seed_id in seen:
            raise ProductDiscoveryError(f"Duplicate F8 query_or_seed_id: {seed_id}")
        seen.add(seed_id)
        seed_ids.append(seed_id)
        round_id = _require_str(seed_map.get("round_id"), "round_id")
        if round_id not in rebuilt:
            raise ProductDiscoveryError("F8 query seed round_id must be R1/R2/R3")
        rebuilt[round_id].append(seed_id)
        family = _require_str(seed_map.get("query_family"), "query_family")
        source = _require_str(seed_map.get("source_class"), "source_class")
        if family not in allowed_families:
            raise ProductDiscoveryError(f"F8 query seed family {family!r} outside declared families")
        if source not in allowed_sources:
            raise ProductDiscoveryError(f"F8 query seed source_class {source!r} outside declared classes")
        _require_str(seed_map.get("query_expression"), "query_expression")
        language = _require_str(seed_map.get("language"), "language")
        jurisdiction = _require_str(seed_map.get("jurisdiction"), "jurisdiction")
        if language == "en":
            raise ProductDiscoveryError("F8 seeds must be native-language; English-only seeds are prohibited")
        if jurisdiction == "GLOBAL":
            raise ProductDiscoveryError("F8 seeds must bind a matched jurisdiction, not GLOBAL")

    if universe["query_seed_set_sha256"] != id_set_digest(seed_ids):
        raise ProductDiscoveryError("F8 query_seed_set_sha256 does not match seed IDs")
    for round_id in ("R1", "R2", "R3"):
        declared = [str(item) for item in cast(list[Any], round_seed_ids.get(round_id, []))]
        if declared != rebuilt[round_id]:
            raise ProductDiscoveryError(f"F8 round_seed_ids[{round_id}] does not match query_seeds")
        if len(declared) < 20:
            raise ProductDiscoveryError(
                f"F8 round {round_id} must declare at least 20 query seeds to support the marginal-yield floor"
            )
    counts = _require_mapping(universe["per_round_seed_counts"], "per_round_seed_counts")
    for round_id in ("R1", "R2", "R3"):
        if int(counts.get(round_id, -1)) != len(rebuilt[round_id]):
            raise ProductDiscoveryError(f"F8 per_round_seed_counts[{round_id}] mismatch")

    independence = _require_mapping(universe["independence_rule"], "independence_rule")
    if independence.get("independently_attributable_from_other_frames") is not True:
        raise ProductDiscoveryError("F8 must remain independently attributable")
    if independence.get("does_not_credit_f9_actor_enumeration_or_f2_f3_exhaustion") is not True:
        raise ProductDiscoveryError("F8 must not credit F9/F2/F3 routes")


def validate_f10_patent_assignee_universe(universe: Mapping[str, Any]) -> None:
    """Validate the frozen F10 patent/assignee candidate universe."""

    required = {
        "universe_id",
        "universe_sha256",
        "status",
        "frame_id",
        "frame_version",
        "frame_register_version",
        "frame_register_blob_sha",
        "frame_class",
        "capture_estimation_eligible",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "a2_checkpoint_id",
        "a2_checkpoint_sha256",
        "round_start_known_identity_set_sha256",
        "providers",
        "query_families",
        "source_classes",
        "query_family_executions",
        "patent_candidate_count",
        "patent_candidates",
        "patent_publication_set_sha256",
        "assignee_candidate_count",
        "assignee_candidates",
        "assignee_candidate_set_sha256",
        "bounded_exhaustion_rule",
        "contamination_controls",
        "boundary",
    }
    missing = sorted(required - set(universe))
    if missing:
        raise ProductDiscoveryError(f"F10 patent universe missing fields: {', '.join(missing)}")
    if universe["universe_id"] != F10_UNIVERSE_ID:
        raise ProductDiscoveryError(f"universe_id must be {F10_UNIVERSE_ID}")
    if universe["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("F10 patent universe must be FROZEN_v1.0")
    if universe["universe_sha256"] != content_digest(universe, exclude="universe_sha256"):
        raise ProductDiscoveryError("F10 universe_sha256 does not match deterministic content digest")
    if universe["frame_id"] != "F10":
        raise ProductDiscoveryError("F10 patent universe frame_id mismatch")
    frame = _frame("F10")
    if universe["frame_class"] != frame["frame_class"]:
        raise ProductDiscoveryError("F10 frame_class does not match the frozen register")
    if bool(universe["capture_estimation_eligible"]) is not True:
        raise ProductDiscoveryError("F10 capture_estimation_eligible must be true at frame level")
    if set(universe["query_families"]) != set(frame["query_families"]):
        raise ProductDiscoveryError("F10 query_families do not match the frozen register")
    if set(universe["source_classes"]) != set(frame["source_classes"]):
        raise ProductDiscoveryError("F10 source_classes do not match the frozen register")
    if universe["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("F10 patent universe must bind the frozen A2 analysis universe")
    if universe["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff does not match frozen A2 cutoff")
    if universe["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff does not match frozen A2 cutoff")
    if universe["a2_checkpoint_id"] != CHECKPOINT_ID or universe["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("F10 patent universe must bind the frozen A2 checkpoint")
    if universe["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("F10 patent universe must bind the A1 known-identity digest")
    if universe["boundary"] != F10_BOUNDARY:
        raise ProductDiscoveryError("F10 patent universe boundary drift")

    patents = _require_list(universe["patent_candidates"], "patent_candidates")
    if int(universe["patent_candidate_count"]) != len(patents):
        raise ProductDiscoveryError("patent_candidate_count does not match patent_candidates length")
    if len(patents) < 1:
        raise ProductDiscoveryError("F10 freeze must include at least one patent candidate from live retrieval")
    pub_ids: list[str] = []
    seen_pub: set[str] = set()
    for patent in patents:
        item = _require_mapping(patent, "patent_candidate")
        pub = _require_str(item.get("publication_number"), "publication_number")
        if pub in seen_pub:
            raise ProductDiscoveryError(f"Duplicate F10 publication_number: {pub}")
        seen_pub.add(pub)
        pub_ids.append(pub)
        _require_str(item.get("candidate_id"), "candidate_id")
        _require_str(item.get("query_id"), "query_id")
        family = _require_str(item.get("query_family"), "query_family")
        if family not in set(frame["query_families"]):
            raise ProductDiscoveryError(f"F10 patent query_family {family!r} outside declared families")
        if item.get("source_class") != "PATENT_BIBLIOGRAPHIC":
            raise ProductDiscoveryError("F10 patent candidates must remain PATENT_BIBLIOGRAPHIC leads")
    if universe["patent_publication_set_sha256"] != id_set_digest(pub_ids):
        raise ProductDiscoveryError("patent_publication_set_sha256 does not match publication numbers")

    assignees = _require_list(universe["assignee_candidates"], "assignee_candidates")
    if int(universe["assignee_candidate_count"]) != len(assignees):
        raise ProductDiscoveryError("assignee_candidate_count does not match assignee_candidates length")
    if len(assignees) < 1:
        raise ProductDiscoveryError("F10 freeze must include at least one assignee candidate")
    assignee_ids: list[str] = []
    seen_asn: set[str] = set()
    for assignee in assignees:
        item = _require_mapping(assignee, "assignee_candidate")
        asn_id = _require_str(item.get("assignee_candidate_id"), "assignee_candidate_id")
        if asn_id in seen_asn:
            raise ProductDiscoveryError(f"Duplicate F10 assignee_candidate_id: {asn_id}")
        seen_asn.add(asn_id)
        assignee_ids.append(asn_id)
        _require_str(item.get("assignee_name"), "assignee_name")
        pubs = _require_list(item.get("patent_publication_numbers"), "patent_publication_numbers")
        if not pubs:
            raise ProductDiscoveryError(f"{asn_id} must cite at least one patent publication")
    if universe["assignee_candidate_set_sha256"] != id_set_digest(assignee_ids):
        raise ProductDiscoveryError("assignee_candidate_set_sha256 does not match assignee IDs")

    exhaustion = _require_mapping(universe["bounded_exhaustion_rule"], "bounded_exhaustion_rule")
    if exhaustion.get("mode") != "BOUNDED_SOURCE_EXHAUSTION":
        raise ProductDiscoveryError("F10 bounded_exhaustion_rule.mode must be BOUNDED_SOURCE_EXHAUSTION")
    if exhaustion.get("patent_match_is_retrieval_lead_only") is not True:
        raise ProductDiscoveryError("F10 must treat patent matches as retrieval leads only")
    if exhaustion.get("assignee_match_is_retrieval_lead_only") is not True:
        raise ProductDiscoveryError("F10 must treat assignee matches as retrieval leads only")
    if exhaustion.get("product_identity_requires_separate_attributable_product_evidence") is not True:
        raise ProductDiscoveryError("F10 must require separate attributable product evidence for product identity")
    if exhaustion.get("commercialization_not_inferred_from_patent_ownership") is not True:
        raise ProductDiscoveryError("F10 must not infer commercialization from patent ownership")
    if exhaustion.get("semantic_similarity_does_not_create_product_link") is not True:
        raise ProductDiscoveryError("F10 must not create product links from semantic similarity")

    controls = _require_mapping(universe["contamination_controls"], "contamination_controls")
    for key in (
        "patent_or_assignee_match_is_retrieval_lead_only",
        "patent_ownership_does_not_establish_commercialization",
        "semantic_similarity_does_not_create_product_identity",
        "no_canonical_offering_allocation_from_patent_freeze",
        "estimator_eligible_only_for_include_resolved_with_attributable_product_evidence",
        "f7_f9_f11_remain_estimator_excluded",
    ):
        if controls.get(key) is not True:
            raise ProductDiscoveryError(f"F10 contamination control {key} must be true")


def load_default_language_jurisdiction_strata() -> dict[str, Any]:
    """Load and validate the frozen language/jurisdiction strata."""

    strata = _load_resource(LANGUAGE_STRATA_RESOURCE)
    validate_language_jurisdiction_strata(strata)
    if strata["strata_sha256"] != LANGUAGE_STRATA_SHA256:
        raise ProductDiscoveryError("Loaded language strata digest drifted from frozen LANGUAGE_STRATA_SHA256")
    return strata


def load_default_f8_round_protocol() -> dict[str, Any]:
    """Load and validate the frozen F8 round protocol."""

    protocol = _load_resource(F8_PROTOCOL_RESOURCE)
    validate_f8_round_protocol(protocol)
    if protocol["protocol_sha256"] != F8_PROTOCOL_SHA256:
        raise ProductDiscoveryError("Loaded F8 protocol digest drifted from frozen F8_PROTOCOL_SHA256")
    return protocol


def load_default_f8_query_universe() -> dict[str, Any]:
    """Load and validate the frozen F8 query universe."""

    universe = _load_resource(F8_UNIVERSE_RESOURCE)
    validate_f8_query_universe(universe)
    if universe["universe_sha256"] != F8_UNIVERSE_SHA256:
        raise ProductDiscoveryError("Loaded F8 universe digest drifted from frozen F8_UNIVERSE_SHA256")
    return universe


def load_default_f10_patent_assignee_universe() -> dict[str, Any]:
    """Load and validate the frozen F10 patent/assignee candidate universe."""

    universe = _load_resource(F10_UNIVERSE_RESOURCE)
    validate_f10_patent_assignee_universe(universe)
    if universe["universe_sha256"] != F10_UNIVERSE_SHA256:
        raise ProductDiscoveryError("Loaded F10 universe digest drifted from frozen F10_UNIVERSE_SHA256")
    return universe


def f8_freeze_does_not_imply_saturation() -> str:
    """Freezing F8 contracts alone remains CONTINUE."""

    return "CONTINUE"


def f8_frame_stop_state(round_summaries: Sequence[Mapping[str, Any]]) -> str:
    """Evaluate F8 stop state under the frozen register marginal-yield rule."""

    return evaluate_frame_stop(_frame("F8"), round_summaries)


def f10_freeze_does_not_imply_exhaustion() -> str:
    """Freezing the F10 candidate universe alone remains CONTINUE."""

    return "CONTINUE"


def f10_frame_stop_state(*, source_exhausted: bool) -> str:
    """Evaluate F10 stop state under bounded-source exhaustion."""

    return evaluate_frame_stop(_frame("F10"), [], source_exhausted=source_exhausted)
