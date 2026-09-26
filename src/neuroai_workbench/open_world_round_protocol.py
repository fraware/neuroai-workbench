"""Validators for Release-A open-world round protocol and query universes.

These contracts freeze declared query seeds and the literal marginal-yield stop
rule for F1/F4/F5/F6/F11 under the A2 checkpoint. Freezing does not execute
retrieval, allocate canonical identities, or establish saturation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a2_bounded_frame_checkpoint import (
    CHECKPOINT_ID,
    OPEN_WORLD_FRAMES_NOT_STARTED,
)
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
PROTOCOL_RESOURCE = "RELEASE_A_OPEN_WORLD_ROUND_PROTOCOL.v1.0.json"
PROTOCOL_ID = "RELEASE_A_OPEN_WORLD_ROUND_PROTOCOL_v1.0"
PROTOCOL_SHA256 = "43b610d8a6446011b47a0761c8a18f13bb00d6f8a5001742f30968851395a377"
CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
FRAME_REGISTER_BLOB_SHA = "bb3d95226dc0ed528e5eed8e6de707430399b9ae"

OPEN_WORLD_FRAME_IDS = OPEN_WORLD_FRAMES_NOT_STARTED
PRIMARY_OPEN_WORLD_FRAME_IDS = ("F1", "F4", "F5", "F6")
DIAGNOSTIC_OPEN_WORLD_FRAME_IDS = ("F11",)

UNIVERSE_RESOURCES = {
    "F1": "RELEASE_A_F1_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
    "F4": "RELEASE_A_F4_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
    "F5": "RELEASE_A_F5_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
    "F6": "RELEASE_A_F6_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
    "F11": "RELEASE_A_F11_OPEN_WORLD_QUERY_UNIVERSE.v1.0.json",
}
UNIVERSE_IDS = {frame_id: f"RELEASE_A_{frame_id}_OPEN_WORLD_QUERY_UNIVERSE_v1.0" for frame_id in OPEN_WORLD_FRAME_IDS}
UNIVERSE_SHA256 = {
    "F1": "848231b5fc88afc6efd790dc371c1644d8fdd222c782c003edafa89ae37d1662",
    "F4": "32259556bb138afc3927d1ba65f0213af132ebad7782b3ab67419c4e88f3c770",
    "F5": "fcebb63bcbe4b1c23d1ba1c9e0e62b79c9585426b8c9518d4db61842c8dcc233",
    "F6": "65ff66464b7cba60e0347c061069a59b59f6102041b7a3b24a723a7d09cbdfbc",
    "F11": "d965a9395740bdf7bb75ed8b4c380b12760c28e31461c98af01b8b8f19a28488",
}

OPEN_WORLD_BOUNDARY = (
    "Open-world query/round contracts fix declared retrieval seeds, round accounting, "
    "independence, and the literal marginal-yield stop rule under the frozen A2 analysis "
    "universe and A2 bounded-frame checkpoint. They do not establish global completeness, "
    "unseen-population size, market share, effectiveness, commercialization, S2 publication "
    "authority, or v4.2 assessment effect. F11 remains diagnostic-only for the primary "
    "unseen-population estimator."
)


def open_world_content_digest(material: Mapping[str, Any], *, exclude: str) -> str:
    """Return deterministic SHA-256 for an open-world contract, excluding a self-digest field."""

    payload = {key: value for key, value in material.items() if key != exclude}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def query_seed_set_digest(seed_ids: Iterable[str]) -> str:
    """Return SHA-256 over the sorted unique query-or-seed ID list."""

    encoded = json.dumps(
        sorted({str(seed_id) for seed_id in seed_ids}), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
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


def validate_open_world_round_protocol(protocol: Mapping[str, Any]) -> None:
    """Validate the shared open-world round protocol binding."""

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
        raise ProductDiscoveryError(f"Open-world round protocol missing fields: {', '.join(missing)}")
    if protocol["protocol_id"] != PROTOCOL_ID:
        raise ProductDiscoveryError(f"protocol_id must be {PROTOCOL_ID}")
    if protocol["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("Open-world round protocol must be FROZEN_v1.0")
    if protocol["protocol_sha256"] != open_world_content_digest(protocol, exclude="protocol_sha256"):
        raise ProductDiscoveryError("protocol_sha256 does not match deterministic content digest")
    if tuple(protocol["frame_ids"]) != OPEN_WORLD_FRAME_IDS:
        raise ProductDiscoveryError("Open-world protocol frame_ids must be exactly F1/F4/F5/F6/F11")
    if protocol["frame_version"] != FRAME_VERSION:
        raise ProductDiscoveryError(f"frame_version must be {FRAME_VERSION}")
    if protocol["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"frame_register_version must be {FRAME_REGISTER_VERSION}")
    if protocol["frame_register_blob_sha"] != FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("frame_register_blob_sha does not match the frozen register blob")
    if protocol["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("Open-world protocol must bind the frozen A2 analysis universe")
    if protocol["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff does not match frozen A2 cutoff")
    if protocol["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff does not match frozen A2 cutoff")
    if protocol["a2_checkpoint_id"] != CHECKPOINT_ID:
        raise ProductDiscoveryError("Open-world protocol must bind the A2 bounded-frame checkpoint ID")
    if protocol["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError("Open-world protocol must bind the frozen A2 checkpoint digest")
    if protocol["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("Open-world protocol must bind the A1 six-offering known-identity digest")
    if protocol["boundary"] != OPEN_WORLD_BOUNDARY:
        raise ProductDiscoveryError("Open-world protocol boundary drift")

    stopping = _require_mapping(protocol["stopping_rule"], "stopping_rule")
    if stopping.get("mode") != "MARGINAL_YIELD":
        raise ProductDiscoveryError("Open-world stopping_rule.mode must be MARGINAL_YIELD")
    if int(stopping["minimum_completed_rounds"]) != 3:
        raise ProductDiscoveryError("minimum_completed_rounds must be 3")
    if int(stopping["consecutive_low_yield_rounds"]) != 2:
        raise ProductDiscoveryError("consecutive_low_yield_rounds must be 2")
    if float(stopping["maximum_marginal_new_identity_yield"]) != 0.05:
        raise ProductDiscoveryError("maximum_marginal_new_identity_yield must be 0.05")
    if int(stopping["minimum_raw_candidates_per_round"]) != 20:
        raise ProductDiscoveryError("minimum_raw_candidates_per_round must be 20")
    if stopping.get("literal_tail_only") is not True:
        raise ProductDiscoveryError("literal_tail_only must be true")

    estimator = _require_mapping(protocol["estimator_policy"], "estimator_policy")
    if tuple(estimator.get("primary_estimation_eligible_frames", ())) != PRIMARY_OPEN_WORLD_FRAME_IDS:
        raise ProductDiscoveryError("primary_estimation_eligible_frames must be F1/F4/F5/F6")
    if tuple(estimator.get("diagnostic_only_frames", ())) != DIAGNOSTIC_OPEN_WORLD_FRAME_IDS:
        raise ProductDiscoveryError("diagnostic_only_frames must be exactly F11")
    if estimator.get("f11_capture_estimation_eligible_must_be_false") is not True:
        raise ProductDiscoveryError("F11 must remain estimator-ineligible")

    independence = _require_mapping(protocol["independence_rule"], "independence_rule")
    if independence.get("frames_independently_attributable") is not True:
        raise ProductDiscoveryError("Open-world frames must remain independently attributable")
    if independence.get("prohibit_pooling_source_routes_merely_because_same_product_found") is not True:
        raise ProductDiscoveryError("Pooling source routes merely because the same product is found is prohibited")

    temporal = _require_mapping(protocol["temporal_rule"], "temporal_rule")
    if temporal.get("resolved_post_cutoff_capture_requires_world_time_support_ref") is not True:
        raise ProductDiscoveryError("Post-cutoff INCLUDE_RESOLVED must require world_time_support_ref")
    if temporal.get("no_canonical_identity_allocation_by_implication") is not True:
        raise ProductDiscoveryError("Canonical identity allocation by implication is prohibited")

    if list(protocol["minimum_declared_rounds"]) != ["R1", "R2", "R3"]:
        raise ProductDiscoveryError("minimum_declared_rounds must be R1/R2/R3")

    gate = _require_mapping(protocol["execution_gate"], "execution_gate")
    if gate.get("does_not_start_f8_f10_a3_or_a7") is not True:
        raise ProductDiscoveryError("Open-world protocol must keep F8/F10/A3/A7 out of scope")


def load_default_open_world_round_protocol() -> dict[str, Any]:
    """Load and validate the frozen open-world round protocol."""

    protocol = _load_resource(PROTOCOL_RESOURCE)
    validate_open_world_round_protocol(protocol)
    if protocol["protocol_sha256"] != PROTOCOL_SHA256:
        raise ProductDiscoveryError("Loaded open-world protocol digest drifted from frozen PROTOCOL_SHA256")
    return protocol


def validate_open_world_query_universe(universe: Mapping[str, Any], *, frame_id: str) -> None:
    """Validate one frozen open-world query universe for a declared frame."""

    if frame_id not in OPEN_WORLD_FRAME_IDS:
        raise ProductDiscoveryError(f"Unknown open-world frame_id {frame_id!r}")
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
        "open_world_round_protocol_id",
        "open_world_round_protocol_sha256",
        "round_start_known_identity_set_sha256",
        "query_families",
        "source_classes",
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
        raise ProductDiscoveryError(f"{frame_id} query universe missing fields: {', '.join(missing)}")
    if universe["universe_id"] != UNIVERSE_IDS[frame_id]:
        raise ProductDiscoveryError(f"{frame_id} universe_id must be {UNIVERSE_IDS[frame_id]}")
    if universe["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError(f"{frame_id} query universe must be FROZEN_v1.0")
    if universe["universe_sha256"] != open_world_content_digest(universe, exclude="universe_sha256"):
        raise ProductDiscoveryError(f"{frame_id} universe_sha256 does not match deterministic content digest")
    if universe["frame_id"] != frame_id:
        raise ProductDiscoveryError(f"{frame_id} query universe frame_id mismatch")
    if universe["frame_version"] != FRAME_VERSION:
        raise ProductDiscoveryError(f"frame_version must be {FRAME_VERSION}")
    if universe["frame_register_version"] != FRAME_REGISTER_VERSION:
        raise ProductDiscoveryError(f"frame_register_version must be {FRAME_REGISTER_VERSION}")
    if universe["frame_register_blob_sha"] != FRAME_REGISTER_BLOB_SHA:
        raise ProductDiscoveryError("frame_register_blob_sha does not match the frozen register blob")
    if universe["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError(f"{frame_id} query universe must bind the frozen A2 analysis universe")
    if universe["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff does not match frozen A2 cutoff")
    if universe["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff does not match frozen A2 cutoff")
    if universe["a2_checkpoint_id"] != CHECKPOINT_ID or universe["a2_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ProductDiscoveryError(f"{frame_id} query universe must bind the frozen A2 checkpoint")
    if universe["open_world_round_protocol_id"] != PROTOCOL_ID:
        raise ProductDiscoveryError(f"{frame_id} query universe must bind {PROTOCOL_ID}")
    if universe["open_world_round_protocol_sha256"] != PROTOCOL_SHA256:
        raise ProductDiscoveryError(f"{frame_id} query universe must bind the frozen open-world protocol digest")
    if universe["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError(f"{frame_id} query universe must bind the A1 known-identity digest")
    if universe["boundary"] != OPEN_WORLD_BOUNDARY:
        raise ProductDiscoveryError(f"{frame_id} query universe boundary drift")

    frame = _frame(frame_id)
    if universe["frame_class"] != frame["frame_class"]:
        raise ProductDiscoveryError(f"{frame_id} frame_class does not match the frozen register")
    if bool(universe["capture_estimation_eligible"]) != bool(frame["capture_estimation_eligible"]):
        raise ProductDiscoveryError(f"{frame_id} capture_estimation_eligible does not match the frozen register")
    if set(universe["query_families"]) != set(frame["query_families"]):
        raise ProductDiscoveryError(f"{frame_id} query_families do not match the frozen register")
    if set(universe["source_classes"]) != set(frame["source_classes"]):
        raise ProductDiscoveryError(f"{frame_id} source_classes do not match the frozen register")
    if list(universe["minimum_rounds"]) != ["R1", "R2", "R3"]:
        raise ProductDiscoveryError(f"{frame_id} minimum_rounds must be R1/R2/R3")

    stopping = _require_mapping(universe["stopping_rule"], "stopping_rule")
    if stopping.get("mode") != "MARGINAL_YIELD":
        raise ProductDiscoveryError(f"{frame_id} stopping_rule.mode must be MARGINAL_YIELD")
    if int(stopping["minimum_completed_rounds"]) != int(frame["stopping_rule"]["minimum_completed_rounds"]):
        raise ProductDiscoveryError(f"{frame_id} minimum_completed_rounds drift")
    if int(stopping["consecutive_low_yield_rounds"]) != int(frame["stopping_rule"]["consecutive_low_yield_rounds"]):
        raise ProductDiscoveryError(f"{frame_id} consecutive_low_yield_rounds drift")
    if float(stopping["maximum_marginal_new_identity_yield"]) != float(
        frame["stopping_rule"]["maximum_marginal_new_identity_yield"]
    ):
        raise ProductDiscoveryError(f"{frame_id} maximum_marginal_new_identity_yield drift")
    if int(stopping["minimum_raw_candidates_per_round"]) != int(
        frame["stopping_rule"]["minimum_raw_candidates_per_round"]
    ):
        raise ProductDiscoveryError(f"{frame_id} minimum_raw_candidates_per_round drift")

    seeds = _require_list(universe["query_seeds"], "query_seeds")
    if int(universe["query_seed_count"]) != len(seeds):
        raise ProductDiscoveryError(f"{frame_id} query_seed_count does not match query_seeds length")
    seed_ids: list[str] = []
    seen: set[str] = set()
    round_seed_ids = _require_mapping(universe["round_seed_ids"], "round_seed_ids")
    rebuilt_rounds: dict[str, list[str]] = {"R1": [], "R2": [], "R3": []}
    allowed_families = set(cast(list[str], universe["query_families"]))
    allowed_sources = set(cast(list[str], universe["source_classes"]))
    for seed in seeds:
        seed_map = _require_mapping(seed, "query_seed")
        seed_id = _require_str(seed_map.get("query_or_seed_id"), "query_or_seed_id")
        if seed_id in seen:
            raise ProductDiscoveryError(f"Duplicate open-world query_or_seed_id: {seed_id}")
        seen.add(seed_id)
        seed_ids.append(seed_id)
        round_id = _require_str(seed_map.get("round_id"), "round_id")
        if round_id not in rebuilt_rounds:
            raise ProductDiscoveryError(f"{frame_id} query seed round_id must be R1/R2/R3")
        rebuilt_rounds[round_id].append(seed_id)
        family = _require_str(seed_map.get("query_family"), "query_family")
        source = _require_str(seed_map.get("source_class"), "source_class")
        if family not in allowed_families:
            raise ProductDiscoveryError(f"{frame_id} query seed family {family!r} outside declared families")
        if source not in allowed_sources:
            raise ProductDiscoveryError(f"{frame_id} query seed source_class {source!r} outside declared classes")
        _require_str(seed_map.get("query_expression"), "query_expression")
        _require_str(seed_map.get("language"), "language")
        _require_str(seed_map.get("jurisdiction"), "jurisdiction")

    if universe["query_seed_set_sha256"] != query_seed_set_digest(seed_ids):
        raise ProductDiscoveryError(f"{frame_id} query_seed_set_sha256 does not match seed IDs")
    for round_id in ("R1", "R2", "R3"):
        declared = [str(item) for item in cast(list[Any], round_seed_ids.get(round_id, []))]
        if declared != rebuilt_rounds[round_id]:
            raise ProductDiscoveryError(f"{frame_id} round_seed_ids[{round_id}] does not match query_seeds")
        if len(declared) < 20:
            raise ProductDiscoveryError(
                f"{frame_id} round {round_id} must declare at least 20 query seeds to support the marginal-yield floor"
            )
    counts = _require_mapping(universe["per_round_seed_counts"], "per_round_seed_counts")
    for round_id in ("R1", "R2", "R3"):
        if int(counts.get(round_id, -1)) != len(rebuilt_rounds[round_id]):
            raise ProductDiscoveryError(f"{frame_id} per_round_seed_counts[{round_id}] mismatch")

    independence = _require_mapping(universe["independence_rule"], "independence_rule")
    if independence.get("independently_attributable_from_other_frames") is not True:
        raise ProductDiscoveryError(f"{frame_id} must remain independently attributable")
    if independence.get("does_not_credit_f9_actor_enumeration_or_f2_f3_exhaustion") is not True:
        raise ProductDiscoveryError(f"{frame_id} must not credit F9/F2/F3 routes")

    temporal = _require_mapping(universe["temporal_rule"], "temporal_rule")
    if temporal.get("resolved_post_cutoff_capture_requires_world_time_support_ref") is not True:
        raise ProductDiscoveryError(f"{frame_id} must require world_time_support_ref for post-cutoff INCLUDE_RESOLVED")
    if temporal.get("no_canonical_identity_allocation_by_implication") is not True:
        raise ProductDiscoveryError(f"{frame_id} must forbid canonical identity allocation by implication")


def load_default_open_world_query_universe(frame_id: str) -> dict[str, Any]:
    """Load and validate one frozen open-world query universe."""

    if frame_id not in UNIVERSE_RESOURCES:
        raise ProductDiscoveryError(f"Unknown open-world frame_id {frame_id!r}")
    universe = _load_resource(UNIVERSE_RESOURCES[frame_id])
    validate_open_world_query_universe(universe, frame_id=frame_id)
    if universe["universe_sha256"] != UNIVERSE_SHA256[frame_id]:
        raise ProductDiscoveryError(f"Loaded {frame_id} universe digest drifted from frozen UNIVERSE_SHA256")
    return universe


def load_all_default_open_world_query_universes() -> dict[str, dict[str, Any]]:
    """Load and validate all frozen open-world query universes."""

    return {frame_id: load_default_open_world_query_universe(frame_id) for frame_id in OPEN_WORLD_FRAME_IDS}


def open_world_frame_stop_state(
    frame_id: str,
    round_summaries: Sequence[Mapping[str, Any]],
) -> str:
    """Evaluate the literal marginal-yield stop state for one open-world frame."""

    if frame_id not in OPEN_WORLD_FRAME_IDS:
        raise ProductDiscoveryError(f"Unknown open-world frame_id {frame_id!r}")
    frame = _frame(frame_id)
    return evaluate_frame_stop(frame, round_summaries)


def freeze_does_not_imply_saturation(frame_id: str) -> str:
    """Return CONTINUE until executed round summaries satisfy the literal stop rule."""

    return open_world_frame_stop_state(frame_id, [])
