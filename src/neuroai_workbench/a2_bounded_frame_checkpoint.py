"""Release-A A2 bounded-frame checkpoint digest and fail-closed validation.

The checkpoint freezes protocol-bounded exhaustion for F2, F3, and F9 under the
immutable A2 analysis universe. It does not authorize open-world frames, A3+,
global completeness, market share, effectiveness, or unseen-population size.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.f2_f3_bounded_universe import (
    F2_UNIVERSE_ID,
    F2_UNIVERSE_SHA256,
    F3_UNIVERSE_ID,
    F3_UNIVERSE_SHA256,
)
from neuroai_workbench.f9_actor_enumeration import (
    F9_ACTOR_ENUMERATION_PROCEDURE_ID,
    F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
    f9_actor_completion_ledger_digest,
    f9_bounded_exhaustion_state,
)
from neuroai_workbench.product_discovery_frames import (
    A1_IDENTITY_REGISTRY_ID,
    A1_IDENTITY_REGISTRY_SHA256,
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS,
    ProductDiscoveryError,
    identity_set_digest,
    load_default_analysis_universe,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
CHECKPOINT_SCHEMA = "RELEASE_A_A2_BOUNDED_FRAME_CHECKPOINT.schema.json"
CHECKPOINT_RESOURCE = "RELEASE_A_A2_BOUNDED_FRAME_CHECKPOINT.v1.0.json"
CHECKPOINT_ID = "RELEASE_A_A2_BOUNDED_FRAME_CHECKPOINT_v1.0"

F2_FINAL_PACKET_ID = "RELEASE_A_A2_F2_EXHAUSTION_F3_FORMAL_RETRY_TRANCHE_2_v1.0"
F2_FINAL_PACKET_RESOURCE = "RELEASE_A_A2_F2_EXHAUSTION_F3_FORMAL_RETRY_TRANCHE_2.v1.0.json"
F2_FINAL_PACKET_SHA256 = "d66590970362ac82b880e5fe4b9d7c66a913b6dc91618d31fbf67fa39a31c39b"
F2_FINAL_RUN_ID = "PDR-5585af25b1594c7ad52d2c0a9521570f919f243219eb075b9c3abecfd306bd3d"

F3_FINAL_PACKET_ID = "RELEASE_A_A2_F3_INTERVENTION_DEVICE_EXHAUSTION_TRANCHE_3_v1.0"
F3_FINAL_PACKET_RESOURCE = "RELEASE_A_A2_F3_INTERVENTION_DEVICE_EXHAUSTION_TRANCHE_3.v1.0.json"
F3_FINAL_PACKET_SHA256 = "584ab1dae1fcf0885a51ec527bea953a2ee4ad5452c10b7bb6985ca652edb82b"
F3_FINAL_RUN_ID = "PDR-e4d613d91fce2cfc70cd4792d7b28c4ac4c316a0850dcbc04d9474828677af05"

F9_FINAL_LEDGER_ID = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_008_v1.0"
F9_FINAL_LEDGER_RESOURCE = "RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_008.v1.0.json"
F9_FINAL_LEDGER_SHA256 = "8ed73ad8e53c341f28a749527e5cc6e7277b5a37ba205231ed8219d24c27fc9e"
F9_FINAL_SOURCE_PACKET_ID = "RELEASE_A_A2_F9_REMAINING_ACTORS_PROTOCOL_TRANCHE_12_v1.0"
F9_FINAL_SOURCE_PACKET_SHA256 = "ec36291d58685e30e19903a04ec83b9ba03a8cf3931f311881438eea4b3c8407"

F2_F3_LINEAGE_RESOURCES = (
    "RELEASE_A_A2_BOUNDED_TRANCHE_1.v1.0.json",
    F2_FINAL_PACKET_RESOURCE,
    F3_FINAL_PACKET_RESOURCE,
)

PRODUCT_REGISTRY_PACKAGE = "neuroai_workbench.resources.product_registry"
PRODUCT_REGISTRY_RESOURCE = "RELEASE_A_PRODUCT_IDENTITY_REGISTRY.v1.0.json"

CHECKPOINT_BOUNDARY = (
    "This checkpoint freezes bounded-frame exhaustion for F2, F3, and F9 under the "
    "immutable Release-A A2 analysis universe and frozen protocols. It does not establish "
    "global completeness, market share, effectiveness, unseen-population size, open-world "
    "frame saturation, S2 publication authority, or v4.2 assessment effect."
)

CHECKPOINT_NEXT_REQUIRED = (
    "Open-world frames F1, F4, F5, and F6 (plus diagnostic F11) may begin under the frozen "
    "marginal-yield stopping rule; F8/F10 and A3+ remain separately gated. Do not start A3+ "
    "from this checkpoint alone."
)

CANONICAL_OFFERING_NOTE = (
    "Canonical offering IDs remain exactly the A1 identity-registry allocations. Bounded-frame "
    "execution produced zero new PRODUCT/OFFERING allocations."
)

ESTIMATOR_EXCLUSION_NOTE = (
    "F7, F9, and F11 remain excluded from the primary unseen-population estimator. This "
    "bounded-frame checkpoint must not feed that estimator."
)

OPEN_WORLD_FRAMES_NOT_STARTED = ("F1", "F4", "F5", "F6", "F11")


def _load_json_resource(package: str, name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(files(package).joinpath(name).read_text(encoding="utf-8")))


def checkpoint_content_digest(checkpoint: Mapping[str, Any]) -> str:
    """Return SHA-256 of checkpoint content excluding the self-digest field."""

    material = {key: value for key, value in checkpoint.items() if key != "checkpoint_sha256"}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def unresolved_candidate_set_digest(candidates: Iterable[Mapping[str, Any]]) -> str:
    """Return SHA-256 over sorted unique frame_id/candidate_key pairs."""

    material = sorted(
        (
            {
                "frame_id": str(item["frame_id"]),
                "candidate_key": str(item["candidate_key"]),
            }
            for item in candidates
        ),
        key=lambda item: (item["frame_id"], item["candidate_key"]),
    )
    encoded = json.dumps(material, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _packet_content_sha256(packet: Mapping[str, Any]) -> str:
    exclude = {"packet_sha256"}
    if "disposition_credits" in packet:
        exclude.add("disposition_credits")
    material = {key: value for key, value in packet.items() if key not in exclude}
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sorted_unique_ids(values: Sequence[str]) -> list[str]:
    return sorted(set(values))


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductDiscoveryError(f"{label} must be an object")
    return value


def load_default_a1_identity_registry() -> dict[str, Any]:
    """Load the frozen A1 product identity registry resource."""

    return _load_json_resource(PRODUCT_REGISTRY_PACKAGE, PRODUCT_REGISTRY_RESOURCE)


def canonical_offering_ids_from_registry(registry: Mapping[str, Any]) -> list[str]:
    """Return sorted canonical PRODUCT entity IDs from the A1 registry."""

    records = cast(list[Mapping[str, Any]], registry.get("records", []))
    offering_ids: list[str] = []
    for record in records:
        entity = _require_mapping(record.get("entity"), "identity registry entity")
        entity_id = entity.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.strip():
            raise ProductDiscoveryError("identity registry record missing entity_id")
        offering_ids.append(entity_id)
    return _sorted_unique_ids(offering_ids)


def collect_f2_f3_unresolved_candidates() -> list[dict[str, str]]:
    """Collect unique F2/F3 UNRESOLVED_IDENTITY candidates across the immutable lineage."""

    unresolved: dict[tuple[str, str], dict[str, str]] = {}
    for resource_name in F2_F3_LINEAGE_RESOURCES:
        packet = _load_json_resource(RESOURCE_PACKAGE, resource_name)
        packet_id = str(packet["packet_id"])
        packet_sha = str(packet["packet_sha256"])
        for capture in cast(list[Mapping[str, Any]], packet.get("captures", [])):
            frame_id = str(capture["frame_id"])
            candidate_key = str(capture["candidate_key"])
            key = (frame_id, candidate_key)
            outcome = str(capture["outcome"])
            if outcome == "UNRESOLVED_IDENTITY":
                unresolved[key] = {
                    "frame_id": frame_id,
                    "candidate_key": candidate_key,
                    "capture_id": str(capture["capture_id"]),
                    "source_packet_id": packet_id,
                    "source_packet_sha256": packet_sha,
                }
            elif outcome in {"INCLUDE_RESOLVED", "EXCLUDE", "ABSTAIN"}:
                unresolved.pop(key, None)
    return sorted(unresolved.values(), key=lambda item: (item["frame_id"], item["candidate_key"]))


def collect_f9_unresolved_candidates(ledger: Mapping[str, Any]) -> list[dict[str, str]]:
    """Collect F9 UNRESOLVED_IDENTITY candidates from the terminal completion ledger."""

    capture_to_packet: dict[str, tuple[str, str]] = {}
    for resource in files(RESOURCE_PACKAGE).iterdir():
        name = resource.name
        if not name.startswith("RELEASE_A_A2_F9_") or not name.endswith(".json"):
            continue
        packet = _load_json_resource(RESOURCE_PACKAGE, name)
        packet_id = str(packet["packet_id"])
        packet_sha = str(packet["packet_sha256"])
        for capture in cast(list[Mapping[str, Any]], packet.get("captures", [])):
            capture_to_packet[str(capture["capture_id"])] = (packet_id, packet_sha)

    unresolved: list[dict[str, str]] = []
    for record in cast(list[Mapping[str, Any]], ledger.get("completion_records", [])):
        for candidate in cast(list[Mapping[str, Any]], record.get("candidate_manifest", [])):
            if candidate.get("capture_outcome") != "UNRESOLVED_IDENTITY":
                continue
            capture_id = str(candidate["capture_id"])
            packet_id, packet_sha = capture_to_packet.get(
                capture_id,
                (str(ledger["source_packet_id"]), str(ledger["source_packet_sha256"])),
            )
            unresolved.append(
                {
                    "frame_id": "F9",
                    "candidate_key": str(candidate["candidate_key"]),
                    "capture_id": capture_id,
                    "source_packet_id": packet_id,
                    "source_packet_sha256": packet_sha,
                }
            )
    return sorted(unresolved, key=lambda item: (item["frame_id"], item["candidate_key"]))


def build_expected_unresolved_candidates() -> list[dict[str, str]]:
    """Return the authoritative unresolved candidate set for the A2 checkpoint."""

    ledger = _load_json_resource(RESOURCE_PACKAGE, F9_FINAL_LEDGER_RESOURCE)
    combined = collect_f2_f3_unresolved_candidates() + collect_f9_unresolved_candidates(ledger)
    return sorted(combined, key=lambda item: (item["frame_id"], item["candidate_key"]))


def _validate_schema(checkpoint: Mapping[str, Any]) -> None:
    schema = _load_json_resource(RESOURCE_PACKAGE, CHECKPOINT_SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(checkpoint),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        messages = [
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in errors
        ]
        raise ProductDiscoveryError("A2 checkpoint schema validation failed: " + "; ".join(messages))


def _validate_identity_sets(checkpoint: Mapping[str, Any], universe: Mapping[str, Any]) -> None:
    round_start = cast(list[str], checkpoint["round_start_known_identity_ids"])
    final_known = cast(list[str], checkpoint["final_known_identity_ids"])
    canonical = cast(list[str], checkpoint["canonical_offering_ids"])

    if round_start != _sorted_unique_ids(round_start):
        raise ProductDiscoveryError("round_start_known_identity_ids must be sorted unique")
    if final_known != _sorted_unique_ids(final_known):
        raise ProductDiscoveryError("final_known_identity_ids must be sorted unique")
    if canonical != _sorted_unique_ids(canonical):
        raise ProductDiscoveryError("canonical_offering_ids must be sorted unique")

    if identity_set_digest(round_start) != checkpoint["round_start_known_identity_set_sha256"]:
        raise ProductDiscoveryError("round_start_known_identity_set_sha256 digest mismatch")
    if identity_set_digest(final_known) != checkpoint["final_known_identity_set_sha256"]:
        raise ProductDiscoveryError("final_known_identity_set_sha256 digest mismatch")
    if identity_set_digest(canonical) != checkpoint["canonical_offering_set_sha256"]:
        raise ProductDiscoveryError("canonical_offering_set_sha256 digest mismatch")

    if checkpoint["round_start_known_identity_set_sha256"] != universe["initial_known_identity_set_sha256"]:
        raise ProductDiscoveryError("round-start known-identity digest drifted from analysis universe")
    if checkpoint["round_start_known_identity_set_sha256"] != A1_INITIAL_KNOWN_IDENTITY_SHA256:
        raise ProductDiscoveryError("round-start known-identity digest drifted from frozen A1 digest")
    if (
        final_known != round_start
        or checkpoint["final_known_identity_set_sha256"] != checkpoint["round_start_known_identity_set_sha256"]
    ):
        raise ProductDiscoveryError(
            "final known-identity set must equal round-start set when bounded frames allocate no new identity"
        )
    if (
        canonical != final_known
        or checkpoint["canonical_offering_set_sha256"] != checkpoint["final_known_identity_set_sha256"]
    ):
        raise ProductDiscoveryError("canonical offering set must equal the final known-identity set")

    registry = load_default_a1_identity_registry()
    expected_offerings = canonical_offering_ids_from_registry(registry)
    if canonical != expected_offerings:
        raise ProductDiscoveryError("canonical offering set does not match A1 identity registry")

    binding = _require_mapping(checkpoint["canonical_offering_binding"], "canonical_offering_binding")
    if binding.get("a1_identity_registry_id") != A1_IDENTITY_REGISTRY_ID:
        raise ProductDiscoveryError("canonical offering binding registry id drift")
    if binding.get("a1_identity_registry_sha256") != A1_IDENTITY_REGISTRY_SHA256:
        raise ProductDiscoveryError("canonical offering binding registry digest drift")
    if binding.get("new_canonical_allocations_during_bounded_frames") != 0:
        raise ProductDiscoveryError("bounded-frame checkpoint must record zero new canonical allocations")


def _validate_f2_binding(binding: Mapping[str, Any]) -> None:
    if binding.get("frame_id") != "F2":
        raise ProductDiscoveryError("F2 terminal binding frame_id drift")
    if binding.get("stop_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F2 terminal stop_state must be BOUNDED_FRAME_EXHAUSTED")
    if binding.get("barrier_state") is not None:
        raise ProductDiscoveryError("F2 terminal barrier_state must be null under exhaustion")
    if binding.get("source_exhaustion_state") != "PROVIDER_QUERY_UNIVERSE_EXHAUSTED":
        raise ProductDiscoveryError("F2 source_exhaustion_state drift")
    if binding.get("final_run_id") != F2_FINAL_RUN_ID:
        raise ProductDiscoveryError("F2 final_run_id does not match terminal exhaustion run")
    if binding.get("final_packet_id") != F2_FINAL_PACKET_ID:
        raise ProductDiscoveryError("F2 final_packet_id drift")
    if binding.get("final_packet_sha256") != F2_FINAL_PACKET_SHA256:
        raise ProductDiscoveryError("F2 final_packet_sha256 drift")
    if binding.get("provider_query_universe_id") != F2_UNIVERSE_ID:
        raise ProductDiscoveryError("F2 provider_query_universe_id drift")
    if binding.get("provider_query_universe_sha256") != F2_UNIVERSE_SHA256:
        raise ProductDiscoveryError("F2 provider_query_universe_sha256 drift")

    packet = _load_json_resource(RESOURCE_PACKAGE, F2_FINAL_PACKET_RESOURCE)
    if (
        packet.get("packet_sha256") != F2_FINAL_PACKET_SHA256
        or _packet_content_sha256(packet) != F2_FINAL_PACKET_SHA256
    ):
        raise ProductDiscoveryError("F2 final packet content digest drift")
    if packet.get("f2_exhaustion_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F2 final packet exhaustion state missing")
    run = next(
        (
            item
            for item in cast(list[Mapping[str, Any]], packet.get("runs", []))
            if item.get("run_id") == F2_FINAL_RUN_ID
        ),
        None,
    )
    if run is None or run.get("stop_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F2 final run missing or not exhausted")


def _validate_f3_binding(binding: Mapping[str, Any]) -> None:
    if binding.get("frame_id") != "F3":
        raise ProductDiscoveryError("F3 terminal binding frame_id drift")
    if binding.get("stop_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F3 terminal stop_state must be BOUNDED_FRAME_EXHAUSTED")
    if binding.get("barrier_state") is not None:
        raise ProductDiscoveryError("F3 terminal barrier_state must be null under exhaustion")
    if binding.get("source_exhaustion_state") != "PROVIDER_QUERY_UNIVERSE_EXHAUSTED":
        raise ProductDiscoveryError("F3 source_exhaustion_state drift")
    if binding.get("final_run_id") != F3_FINAL_RUN_ID:
        raise ProductDiscoveryError("F3 final_run_id does not match terminal exhaustion run")
    if binding.get("final_packet_id") != F3_FINAL_PACKET_ID:
        raise ProductDiscoveryError("F3 final_packet_id drift")
    if binding.get("final_packet_sha256") != F3_FINAL_PACKET_SHA256:
        raise ProductDiscoveryError("F3 final_packet_sha256 drift")
    if binding.get("provider_query_universe_id") != F3_UNIVERSE_ID:
        raise ProductDiscoveryError("F3 provider_query_universe_id drift")
    if binding.get("provider_query_universe_sha256") != F3_UNIVERSE_SHA256:
        raise ProductDiscoveryError("F3 provider_query_universe_sha256 drift")

    packet = _load_json_resource(RESOURCE_PACKAGE, F3_FINAL_PACKET_RESOURCE)
    if (
        packet.get("packet_sha256") != F3_FINAL_PACKET_SHA256
        or _packet_content_sha256(packet) != F3_FINAL_PACKET_SHA256
    ):
        raise ProductDiscoveryError("F3 final packet content digest drift")
    if packet.get("f3_exhaustion_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F3 final packet exhaustion state missing")
    if packet.get("f2_exhaustion_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F3 final packet must preserve F2 terminal exhaustion")
    run = next(
        (
            item
            for item in cast(list[Mapping[str, Any]], packet.get("runs", []))
            if item.get("run_id") == F3_FINAL_RUN_ID
        ),
        None,
    )
    if run is None or run.get("stop_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F3 final run missing or not exhausted")


def _validate_f9_binding(binding: Mapping[str, Any]) -> None:
    if binding.get("frame_id") != "F9":
        raise ProductDiscoveryError("F9 terminal binding frame_id drift")
    if binding.get("stop_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F9 terminal stop_state must be BOUNDED_FRAME_EXHAUSTED")
    if binding.get("barrier_state") is not None:
        raise ProductDiscoveryError("F9 terminal barrier_state must be null under exhaustion")
    if binding.get("source_exhaustion_state") != "ACTOR_SEED_SET_EXHAUSTED":
        raise ProductDiscoveryError("F9 source_exhaustion_state drift")
    if binding.get("final_completion_ledger_id") != F9_FINAL_LEDGER_ID:
        raise ProductDiscoveryError("F9 final_completion_ledger_id drift")
    if binding.get("final_completion_ledger_sha256") != F9_FINAL_LEDGER_SHA256:
        raise ProductDiscoveryError("F9 final_completion_ledger_sha256 drift")
    if binding.get("procedure_id") != F9_ACTOR_ENUMERATION_PROCEDURE_ID:
        raise ProductDiscoveryError("F9 procedure_id drift")
    if binding.get("procedure_sha256") != F9_ACTOR_ENUMERATION_PROCEDURE_SHA256:
        raise ProductDiscoveryError("F9 procedure_sha256 drift")
    if binding.get("final_source_packet_id") != F9_FINAL_SOURCE_PACKET_ID:
        raise ProductDiscoveryError("F9 final_source_packet_id drift")
    if binding.get("final_source_packet_sha256") != F9_FINAL_SOURCE_PACKET_SHA256:
        raise ProductDiscoveryError("F9 final_source_packet_sha256 drift")

    ledger = _load_json_resource(RESOURCE_PACKAGE, F9_FINAL_LEDGER_RESOURCE)
    if ledger.get("ledger_sha256") != F9_FINAL_LEDGER_SHA256:
        raise ProductDiscoveryError("F9 ledger embedded digest drift")
    if f9_actor_completion_ledger_digest(ledger) != F9_FINAL_LEDGER_SHA256:
        raise ProductDiscoveryError("F9 ledger content digest drift")
    if ledger.get("f9_exhaustion_state") != "BOUNDED_FRAME_EXHAUSTED":
        raise ProductDiscoveryError("F9 ledger exhaustion state missing")
    if f9_bounded_exhaustion_state(cast(list[Mapping[str, Any]], ledger["completion_records"])) != (
        "BOUNDED_FRAME_EXHAUSTED"
    ):
        raise ProductDiscoveryError("F9 ledger is not bounded-frame exhausted under procedure")
    if ledger.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("F9 ledger analysis universe drift")


def _validate_unresolved(checkpoint: Mapping[str, Any]) -> None:
    candidates = cast(list[Mapping[str, Any]], checkpoint["unresolved_candidates"])
    if int(checkpoint["unresolved_candidate_count"]) != len(candidates):
        raise ProductDiscoveryError("unresolved_candidate_count does not match unresolved_candidates length")
    if unresolved_candidate_set_digest(candidates) != checkpoint["unresolved_candidate_set_sha256"]:
        raise ProductDiscoveryError("unresolved_candidate_set_sha256 digest mismatch")

    sorted_candidates = sorted(candidates, key=lambda item: (str(item["frame_id"]), str(item["candidate_key"])))
    if list(candidates) != sorted_candidates:
        raise ProductDiscoveryError("unresolved_candidates must be sorted by frame_id then candidate_key")

    keys = [(str(item["frame_id"]), str(item["candidate_key"])) for item in candidates]
    if len(keys) != len(set(keys)):
        raise ProductDiscoveryError("unresolved_candidates contain duplicate frame/candidate keys")

    expected = build_expected_unresolved_candidates()
    if candidates != expected:
        raise ProductDiscoveryError("unresolved_candidates drifted from authoritative F2/F3/F9 terminal sources")
    if not candidates:
        raise ProductDiscoveryError("terminal digests present but unresolved candidate set is empty unexpectedly")


def _reject_estimator_contamination_markers(checkpoint: Mapping[str, Any]) -> None:
    for contaminated_key in (
        "primary_estimator_input_frame_ids",
        "capture_estimation_eligible_frame_ids",
        "unseen_population_estimate",
        "market_share_claim",
        "effectiveness_claim",
        "global_completeness_claim",
    ):
        if contaminated_key in checkpoint:
            raise ProductDiscoveryError(f"estimator contamination field present: {contaminated_key}")

    terminals = checkpoint.get("frame_terminal_bindings")
    if isinstance(terminals, Mapping):
        for frame_id in ("F7", "F9", "F11"):
            frame_binding = terminals.get(frame_id)
            if not isinstance(frame_binding, Mapping):
                continue
            if frame_binding.get("capture_estimation_eligible") is True:
                raise ProductDiscoveryError(f"{frame_id} marked capture_estimation_eligible in checkpoint")
            if frame_binding.get("feeds_primary_estimator") is True:
                raise ProductDiscoveryError(f"{frame_id} marked feeds_primary_estimator in checkpoint")


def _validate_estimator_exclusion(checkpoint: Mapping[str, Any]) -> None:
    exclusion = _require_mapping(checkpoint["estimator_exclusion"], "estimator_exclusion")
    excluded = set(cast(list[str], exclusion.get("primary_estimation_excluded_frame_ids", [])))
    if excluded != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ProductDiscoveryError("estimator exclusion must be exactly F7/F9/F11")
    if exclusion.get("bounded_checkpoint_feeds_primary_estimator") is not False:
        raise ProductDiscoveryError("bounded checkpoint must not feed the primary estimator")


def validate_a2_bounded_frame_checkpoint(checkpoint: Mapping[str, Any]) -> None:
    """Fail closed unless the checkpoint binds the frozen A2 bounded-frame terminals."""

    _reject_estimator_contamination_markers(checkpoint)
    _validate_schema(checkpoint)
    if checkpoint.get("checkpoint_id") != CHECKPOINT_ID:
        raise ProductDiscoveryError(f"checkpoint_id must be {CHECKPOINT_ID}")
    if checkpoint.get("status") != "FROZEN_v1.0":
        raise ProductDiscoveryError("checkpoint status must be FROZEN_v1.0")
    if checkpoint.get("claim_scope") != "BOUNDED_FRAME_EXHAUSTION_UNDER_FROZEN_PROTOCOLS":
        raise ProductDiscoveryError("claim_scope must remain protocol-bounded exhaustion")
    if checkpoint.get("checkpoint_sha256") != checkpoint_content_digest(checkpoint):
        raise ProductDiscoveryError("checkpoint_sha256 does not match deterministic content digest")

    universe = load_default_analysis_universe()
    if checkpoint.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id drift from frozen RAU")
    if checkpoint.get("analysis_universe_id") != universe["analysis_universe_id"]:
        raise ProductDiscoveryError("analysis_universe_id does not match loaded analysis universe")
    if (
        checkpoint.get("world_time_cutoff") != A2_WORLD_TIME_CUTOFF
        or checkpoint.get("world_time_cutoff") != universe["world_time_cutoff"]
    ):
        raise ProductDiscoveryError("world_time_cutoff drift")
    if (
        checkpoint.get("knowledge_time_cutoff") != A2_KNOWLEDGE_TIME_CUTOFF
        or checkpoint.get("knowledge_time_cutoff") != universe["knowledge_time_cutoff"]
    ):
        raise ProductDiscoveryError("knowledge_time_cutoff drift")

    _validate_identity_sets(checkpoint, universe)

    terminals = _require_mapping(checkpoint["frame_terminal_bindings"], "frame_terminal_bindings")
    for required in ("F2", "F3", "F9"):
        if required not in terminals:
            raise ProductDiscoveryError(f"missing terminal binding for {required}")
    _validate_f2_binding(_require_mapping(terminals["F2"], "F2 terminal binding"))
    _validate_f3_binding(_require_mapping(terminals["F3"], "F3 terminal binding"))
    _validate_f9_binding(_require_mapping(terminals["F9"], "F9 terminal binding"))

    _validate_unresolved(checkpoint)
    _validate_estimator_exclusion(checkpoint)

    open_world = tuple(cast(list[str], checkpoint.get("open_world_frames_not_started", [])))
    if open_world != OPEN_WORLD_FRAMES_NOT_STARTED:
        raise ProductDiscoveryError("open_world_frames_not_started must be exactly F1/F4/F5/F6/F11")
    if checkpoint.get("next_required_state") != CHECKPOINT_NEXT_REQUIRED:
        raise ProductDiscoveryError("next_required_state drift")
    if checkpoint.get("boundary") != CHECKPOINT_BOUNDARY:
        raise ProductDiscoveryError("checkpoint boundary drift")


def load_default_a2_bounded_frame_checkpoint() -> dict[str, Any]:
    """Load and validate the frozen A2 bounded-frame checkpoint."""

    checkpoint = _load_json_resource(RESOURCE_PACKAGE, CHECKPOINT_RESOURCE)
    validate_a2_bounded_frame_checkpoint(checkpoint)
    return checkpoint


def assemble_a2_bounded_frame_checkpoint(*, assembled_on: str) -> dict[str, Any]:
    """Assemble the authoritative checkpoint payload (digest filled)."""

    universe = load_default_analysis_universe()
    registry = load_default_a1_identity_registry()
    offerings = canonical_offering_ids_from_registry(registry)
    offering_digest = identity_set_digest(offerings)
    unresolved = build_expected_unresolved_candidates()

    checkpoint: dict[str, Any] = {
        "checkpoint_id": CHECKPOINT_ID,
        "checkpoint_sha256": "",
        "status": "FROZEN_v1.0",
        "assembled_on": assembled_on,
        "analysis_universe_id": universe["analysis_universe_id"],
        "world_time_cutoff": universe["world_time_cutoff"],
        "knowledge_time_cutoff": universe["knowledge_time_cutoff"],
        "claim_scope": "BOUNDED_FRAME_EXHAUSTION_UNDER_FROZEN_PROTOCOLS",
        "round_start_known_identity_ids": list(offerings),
        "round_start_known_identity_set_sha256": offering_digest,
        "final_known_identity_ids": list(offerings),
        "final_known_identity_set_sha256": offering_digest,
        "canonical_offering_ids": list(offerings),
        "canonical_offering_set_sha256": offering_digest,
        "canonical_offering_binding": {
            "a1_identity_registry_id": A1_IDENTITY_REGISTRY_ID,
            "a1_identity_registry_sha256": A1_IDENTITY_REGISTRY_SHA256,
            "new_canonical_allocations_during_bounded_frames": 0,
            "note": CANONICAL_OFFERING_NOTE,
        },
        "frame_terminal_bindings": {
            "F2": {
                "frame_id": "F2",
                "stop_state": "BOUNDED_FRAME_EXHAUSTED",
                "barrier_state": None,
                "source_exhaustion_state": "PROVIDER_QUERY_UNIVERSE_EXHAUSTED",
                "final_run_id": F2_FINAL_RUN_ID,
                "final_packet_id": F2_FINAL_PACKET_ID,
                "final_packet_sha256": F2_FINAL_PACKET_SHA256,
                "provider_query_universe_id": F2_UNIVERSE_ID,
                "provider_query_universe_sha256": F2_UNIVERSE_SHA256,
            },
            "F3": {
                "frame_id": "F3",
                "stop_state": "BOUNDED_FRAME_EXHAUSTED",
                "barrier_state": None,
                "source_exhaustion_state": "PROVIDER_QUERY_UNIVERSE_EXHAUSTED",
                "final_run_id": F3_FINAL_RUN_ID,
                "final_packet_id": F3_FINAL_PACKET_ID,
                "final_packet_sha256": F3_FINAL_PACKET_SHA256,
                "provider_query_universe_id": F3_UNIVERSE_ID,
                "provider_query_universe_sha256": F3_UNIVERSE_SHA256,
            },
            "F9": {
                "frame_id": "F9",
                "stop_state": "BOUNDED_FRAME_EXHAUSTED",
                "barrier_state": None,
                "source_exhaustion_state": "ACTOR_SEED_SET_EXHAUSTED",
                "final_completion_ledger_id": F9_FINAL_LEDGER_ID,
                "final_completion_ledger_sha256": F9_FINAL_LEDGER_SHA256,
                "procedure_id": F9_ACTOR_ENUMERATION_PROCEDURE_ID,
                "procedure_sha256": F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
                "final_source_packet_id": F9_FINAL_SOURCE_PACKET_ID,
                "final_source_packet_sha256": F9_FINAL_SOURCE_PACKET_SHA256,
            },
        },
        "unresolved_candidates": unresolved,
        "unresolved_candidate_count": len(unresolved),
        "unresolved_candidate_set_sha256": unresolved_candidate_set_digest(unresolved),
        "estimator_exclusion": {
            "primary_estimation_excluded_frame_ids": sorted(PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS),
            "bounded_checkpoint_feeds_primary_estimator": False,
            "note": ESTIMATOR_EXCLUSION_NOTE,
        },
        "open_world_frames_not_started": list(OPEN_WORLD_FRAMES_NOT_STARTED),
        "next_required_state": CHECKPOINT_NEXT_REQUIRED,
        "boundary": CHECKPOINT_BOUNDARY,
    }
    digest = checkpoint_content_digest(checkpoint)
    mutable = cast(MutableMapping[str, Any], checkpoint)
    mutable["checkpoint_sha256"] = digest
    validate_a2_bounded_frame_checkpoint(checkpoint)
    return checkpoint
