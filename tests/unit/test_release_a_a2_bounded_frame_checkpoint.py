from __future__ import annotations

import copy
import hashlib
import json
from importlib.resources import files
from typing import Any, cast

import pytest

from neuroai_workbench.a2_bounded_frame_checkpoint import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    CHECKPOINT_ID,
    CHECKPOINT_RESOURCE,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    F2_FINAL_PACKET_SHA256,
    F2_FINAL_RUN_ID,
    F2_UNIVERSE_SHA256,
    F3_FINAL_PACKET_SHA256,
    F3_FINAL_RUN_ID,
    F3_UNIVERSE_SHA256,
    F9_ACTOR_ENUMERATION_PROCEDURE_SHA256,
    F9_FINAL_LEDGER_SHA256,
    _require_mapping,
    _validate_f2_binding,
    _validate_f3_binding,
    _validate_f9_binding,
    _validate_schema,
    _validate_unresolved,
    assemble_a2_bounded_frame_checkpoint,
    build_expected_unresolved_candidates,
    canonical_offering_ids_from_registry,
    checkpoint_content_digest,
    collect_f2_f3_unresolved_candidates,
    collect_f9_unresolved_candidates,
    load_default_a1_identity_registry,
    load_default_a2_bounded_frame_checkpoint,
    unresolved_candidate_set_digest,
    validate_a2_bounded_frame_checkpoint,
)
from neuroai_workbench.product_discovery_frames import (
    ProductDiscoveryError,
    identity_set_digest,
    load_default_analysis_universe,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
ANALYSIS_UNIVERSE_RESOURCE = "RELEASE_A_A2_ANALYSIS_UNIVERSE.v1.0.json"
ANALYSIS_UNIVERSE_FILE_SHA256 = "5fab2aca7b03e9bc71b0a89f1fcf9798de4054cfd8a7bf095587cdb6abd2e74a"
CHECKPOINT_SHA256 = "452c8c504990c05edd6ac7c29b542a49ffa4fd81ccdece2bd7ca8e9e0921ca32"
UNRESOLVED_SET_SHA256 = "d832e69611ec0500ecf940372fe10977a2337e609edef3d345575a03d3503ec8"


def _load_checkpoint() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(RESOURCE_PACKAGE).joinpath(CHECKPOINT_RESOURCE).read_text(encoding="utf-8")),
    )


def test_checkpoint_binds_frozen_universe_terminals_and_identity_sets() -> None:
    checkpoint = load_default_a2_bounded_frame_checkpoint()
    universe = load_default_analysis_universe()

    assert checkpoint["checkpoint_id"] == CHECKPOINT_ID
    assert checkpoint["checkpoint_sha256"] == CHECKPOINT_SHA256
    assert checkpoint_content_digest(checkpoint) == CHECKPOINT_SHA256
    assert checkpoint["analysis_universe_id"] == DEFAULT_ANALYSIS_UNIVERSE_ID == universe["analysis_universe_id"]
    assert checkpoint["world_time_cutoff"] == universe["world_time_cutoff"]
    assert checkpoint["knowledge_time_cutoff"] == universe["knowledge_time_cutoff"]
    assert checkpoint["claim_scope"] == "BOUNDED_FRAME_EXHAUSTION_UNDER_FROZEN_PROTOCOLS"

    known = cast(list[str], checkpoint["round_start_known_identity_ids"])
    final = cast(list[str], checkpoint["final_known_identity_ids"])
    offerings = cast(list[str], checkpoint["canonical_offering_ids"])
    assert known == final == offerings
    assert identity_set_digest(known) == checkpoint["round_start_known_identity_set_sha256"]
    assert checkpoint["round_start_known_identity_set_sha256"] == A1_INITIAL_KNOWN_IDENTITY_SHA256
    assert checkpoint["final_known_identity_set_sha256"] == A1_INITIAL_KNOWN_IDENTITY_SHA256
    assert checkpoint["canonical_offering_set_sha256"] == A1_INITIAL_KNOWN_IDENTITY_SHA256
    assert checkpoint["canonical_offering_binding"]["new_canonical_allocations_during_bounded_frames"] == 0

    f2 = checkpoint["frame_terminal_bindings"]["F2"]
    f3 = checkpoint["frame_terminal_bindings"]["F3"]
    f9 = checkpoint["frame_terminal_bindings"]["F9"]
    assert f2["final_run_id"] == F2_FINAL_RUN_ID
    assert f2["final_packet_sha256"] == F2_FINAL_PACKET_SHA256
    assert f2["provider_query_universe_sha256"] == F2_UNIVERSE_SHA256
    assert f2["stop_state"] == "BOUNDED_FRAME_EXHAUSTED"
    assert f2["barrier_state"] is None
    assert f2["source_exhaustion_state"] == "PROVIDER_QUERY_UNIVERSE_EXHAUSTED"
    assert f3["final_run_id"] == F3_FINAL_RUN_ID
    assert f3["final_packet_sha256"] == F3_FINAL_PACKET_SHA256
    assert f3["provider_query_universe_sha256"] == F3_UNIVERSE_SHA256
    assert f3["stop_state"] == "BOUNDED_FRAME_EXHAUSTED"
    assert f3["barrier_state"] is None
    assert f9["final_completion_ledger_sha256"] == F9_FINAL_LEDGER_SHA256
    assert f9["procedure_sha256"] == F9_ACTOR_ENUMERATION_PROCEDURE_SHA256
    assert f9["stop_state"] == "BOUNDED_FRAME_EXHAUSTED"
    assert f9["barrier_state"] is None
    assert f9["source_exhaustion_state"] == "ACTOR_SEED_SET_EXHAUSTED"

    assert checkpoint["unresolved_candidate_count"] == 416
    assert checkpoint["unresolved_candidate_set_sha256"] == UNRESOLVED_SET_SHA256
    assert unresolved_candidate_set_digest(checkpoint["unresolved_candidates"]) == UNRESOLVED_SET_SHA256
    assert checkpoint["open_world_frames_not_started"] == ["F1", "F4", "F5", "F6", "F11"]
    assert checkpoint["estimator_exclusion"]["bounded_checkpoint_feeds_primary_estimator"] is False


def test_analysis_universe_resource_remains_immutable() -> None:
    raw = files(RESOURCE_PACKAGE).joinpath(ANALYSIS_UNIVERSE_RESOURCE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ANALYSIS_UNIVERSE_FILE_SHA256
    universe = load_default_analysis_universe()
    assert universe["analysis_universe_id"] == DEFAULT_ANALYSIS_UNIVERSE_ID
    assert universe["status"] == "FROZEN_v1.0"


def test_checkpoint_fails_closed_on_universe_drift() -> None:
    checkpoint = _load_checkpoint()
    drifted = copy.deepcopy(checkpoint)
    drifted["analysis_universe_id"] = "RAU-" + ("0" * 64)
    drifted["checkpoint_sha256"] = checkpoint_content_digest(drifted)
    with pytest.raises(ProductDiscoveryError, match="analysis_universe_id drift"):
        validate_a2_bounded_frame_checkpoint(drifted)


def test_checkpoint_fails_closed_on_missing_terminal_digests() -> None:
    checkpoint = _load_checkpoint()

    missing_f2 = copy.deepcopy(checkpoint)
    missing_f2["frame_terminal_bindings"]["F2"]["final_packet_sha256"] = "0" * 64
    missing_f2["checkpoint_sha256"] = checkpoint_content_digest(missing_f2)
    with pytest.raises(ProductDiscoveryError, match="F2 final_packet_sha256 drift"):
        validate_a2_bounded_frame_checkpoint(missing_f2)

    missing_f3 = copy.deepcopy(checkpoint)
    missing_f3["frame_terminal_bindings"]["F3"]["final_run_id"] = "PDR-" + ("0" * 64)
    missing_f3["checkpoint_sha256"] = checkpoint_content_digest(missing_f3)
    with pytest.raises(ProductDiscoveryError, match="F3 final_run_id"):
        validate_a2_bounded_frame_checkpoint(missing_f3)

    missing_f9 = copy.deepcopy(checkpoint)
    missing_f9["frame_terminal_bindings"]["F9"]["final_completion_ledger_sha256"] = "0" * 64
    missing_f9["checkpoint_sha256"] = checkpoint_content_digest(missing_f9)
    with pytest.raises(ProductDiscoveryError, match="F9 final_completion_ledger_sha256 drift"):
        validate_a2_bounded_frame_checkpoint(missing_f9)


def test_checkpoint_fails_closed_on_estimator_contamination() -> None:
    checkpoint = _load_checkpoint()

    feeds = copy.deepcopy(checkpoint)
    feeds["estimator_exclusion"]["bounded_checkpoint_feeds_primary_estimator"] = True
    feeds["checkpoint_sha256"] = checkpoint_content_digest(feeds)
    with pytest.raises(ProductDiscoveryError, match="bounded_checkpoint_feeds_primary_estimator"):
        validate_a2_bounded_frame_checkpoint(feeds)

    # Schema-valid list that still omits F9 (duplicate F7) must fail closed on set equality.
    wrong_excluded = copy.deepcopy(checkpoint)
    wrong_excluded["estimator_exclusion"]["primary_estimation_excluded_frame_ids"] = ["F7", "F11", "F7"]
    wrong_excluded["checkpoint_sha256"] = checkpoint_content_digest(wrong_excluded)
    with pytest.raises(ProductDiscoveryError, match="estimator exclusion must be exactly F7/F9/F11"):
        validate_a2_bounded_frame_checkpoint(wrong_excluded)

    contaminated = copy.deepcopy(checkpoint)
    contaminated["unseen_population_estimate"] = {"n_hat": 1}
    contaminated["checkpoint_sha256"] = checkpoint_content_digest(contaminated)
    with pytest.raises(ProductDiscoveryError, match="estimator contamination field present"):
        validate_a2_bounded_frame_checkpoint(contaminated)

    f9_eligible = copy.deepcopy(checkpoint)
    f9_eligible["frame_terminal_bindings"]["F9"]["capture_estimation_eligible"] = True
    f9_eligible["checkpoint_sha256"] = checkpoint_content_digest(f9_eligible)
    with pytest.raises(ProductDiscoveryError, match="F9 marked capture_estimation_eligible"):
        validate_a2_bounded_frame_checkpoint(f9_eligible)


def test_checkpoint_fails_closed_on_content_digest_tamper() -> None:
    checkpoint = _load_checkpoint()
    tampered = copy.deepcopy(checkpoint)
    tampered["checkpoint_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="checkpoint_sha256 does not match"):
        validate_a2_bounded_frame_checkpoint(tampered)


def test_assemble_reproduces_frozen_checkpoint() -> None:
    assembled = assemble_a2_bounded_frame_checkpoint(assembled_on="2026-09-26")
    frozen = _load_checkpoint()
    assert assembled == frozen
    assert assembled["checkpoint_sha256"] == CHECKPOINT_SHA256
    assert build_expected_unresolved_candidates() == assembled["unresolved_candidates"]
    assert collect_f2_f3_unresolved_candidates()
    assert any(
        item["frame_id"] == "F9"
        for item in collect_f9_unresolved_candidates(
            json.loads(
                files(RESOURCE_PACKAGE)
                .joinpath("RELEASE_A_F9_ACTOR_COMPLETION_LEDGER_008.v1.0.json")
                .read_text(encoding="utf-8")
            )
        )
    )


def test_checkpoint_fails_closed_on_identity_and_cutoff_drift() -> None:
    checkpoint = _load_checkpoint()

    unsorted = copy.deepcopy(checkpoint)
    unsorted["round_start_known_identity_ids"] = list(reversed(unsorted["round_start_known_identity_ids"]))
    unsorted["checkpoint_sha256"] = checkpoint_content_digest(unsorted)
    with pytest.raises(ProductDiscoveryError, match="round_start_known_identity_ids must be sorted unique"):
        validate_a2_bounded_frame_checkpoint(unsorted)

    digest_mismatch = copy.deepcopy(checkpoint)
    digest_mismatch["round_start_known_identity_set_sha256"] = "0" * 64
    digest_mismatch["checkpoint_sha256"] = checkpoint_content_digest(digest_mismatch)
    with pytest.raises(ProductDiscoveryError, match="round_start_known_identity_set_sha256 digest mismatch"):
        validate_a2_bounded_frame_checkpoint(digest_mismatch)

    final_drift = copy.deepcopy(checkpoint)
    final_drift["final_known_identity_ids"] = ["PRD-ONLY-ONE"]
    final_drift["final_known_identity_set_sha256"] = identity_set_digest(["PRD-ONLY-ONE"])
    final_drift["checkpoint_sha256"] = checkpoint_content_digest(final_drift)
    with pytest.raises(ProductDiscoveryError, match="final known-identity set must equal round-start"):
        validate_a2_bounded_frame_checkpoint(final_drift)

    offering_drift = copy.deepcopy(checkpoint)
    offering_drift["canonical_offering_ids"] = ["PRD-EXTRA"] + list(offering_drift["canonical_offering_ids"])
    offering_drift["canonical_offering_ids"] = sorted(offering_drift["canonical_offering_ids"])
    offering_drift["canonical_offering_set_sha256"] = identity_set_digest(offering_drift["canonical_offering_ids"])
    offering_drift["checkpoint_sha256"] = checkpoint_content_digest(offering_drift)
    with pytest.raises(ProductDiscoveryError, match="canonical offering set must equal the final known-identity set"):
        validate_a2_bounded_frame_checkpoint(offering_drift)

    final_unsorted = copy.deepcopy(checkpoint)
    final_unsorted["final_known_identity_ids"] = list(reversed(final_unsorted["final_known_identity_ids"]))
    final_unsorted["checkpoint_sha256"] = checkpoint_content_digest(final_unsorted)
    with pytest.raises(ProductDiscoveryError, match="final_known_identity_ids must be sorted unique"):
        validate_a2_bounded_frame_checkpoint(final_unsorted)

    final_digest = copy.deepcopy(checkpoint)
    final_digest["final_known_identity_set_sha256"] = "0" * 64
    final_digest["checkpoint_sha256"] = checkpoint_content_digest(final_digest)
    with pytest.raises(ProductDiscoveryError, match="final_known_identity_set_sha256 digest mismatch"):
        validate_a2_bounded_frame_checkpoint(final_digest)

    canon_digest = copy.deepcopy(checkpoint)
    canon_digest["canonical_offering_set_sha256"] = "0" * 64
    canon_digest["checkpoint_sha256"] = checkpoint_content_digest(canon_digest)
    with pytest.raises(ProductDiscoveryError, match="canonical_offering_set_sha256 digest mismatch"):
        validate_a2_bounded_frame_checkpoint(canon_digest)

    canon_unsorted = copy.deepcopy(checkpoint)
    canon_unsorted["canonical_offering_ids"] = list(reversed(canon_unsorted["canonical_offering_ids"]))
    canon_unsorted["checkpoint_sha256"] = checkpoint_content_digest(canon_unsorted)
    with pytest.raises(ProductDiscoveryError, match="canonical_offering_ids must be sorted unique"):
        validate_a2_bounded_frame_checkpoint(canon_unsorted)

    registry_id = copy.deepcopy(checkpoint)
    registry_id["canonical_offering_binding"]["a1_identity_registry_id"] = "WRONG"
    registry_id["checkpoint_sha256"] = checkpoint_content_digest(registry_id)
    with pytest.raises(ProductDiscoveryError, match="canonical offering binding registry id drift"):
        validate_a2_bounded_frame_checkpoint(registry_id)

    # Schema rejects non-zero allocations; keep the semantic path covered via binding helper mutation.
    alloc = copy.deepcopy(checkpoint)
    alloc["canonical_offering_binding"]["new_canonical_allocations_during_bounded_frames"] = 1
    alloc["checkpoint_sha256"] = checkpoint_content_digest(alloc)
    with pytest.raises(ProductDiscoveryError, match="schema validation failed|zero new canonical"):
        validate_a2_bounded_frame_checkpoint(alloc)

    binding_drift = copy.deepcopy(checkpoint)
    binding_drift["canonical_offering_binding"]["a1_identity_registry_sha256"] = "0" * 64
    binding_drift["checkpoint_sha256"] = checkpoint_content_digest(binding_drift)
    with pytest.raises(ProductDiscoveryError, match="canonical offering binding registry digest drift"):
        validate_a2_bounded_frame_checkpoint(binding_drift)

    cutoff = copy.deepcopy(checkpoint)
    cutoff["world_time_cutoff"] = "2020-01-01"
    cutoff["checkpoint_sha256"] = checkpoint_content_digest(cutoff)
    with pytest.raises(ProductDiscoveryError, match="world_time_cutoff drift"):
        validate_a2_bounded_frame_checkpoint(cutoff)

    knowledge = copy.deepcopy(checkpoint)
    knowledge["knowledge_time_cutoff"] = "2020-01-01T00:00:00Z"
    knowledge["checkpoint_sha256"] = checkpoint_content_digest(knowledge)
    with pytest.raises(ProductDiscoveryError, match="knowledge_time_cutoff drift"):
        validate_a2_bounded_frame_checkpoint(knowledge)


def test_checkpoint_fails_closed_on_barrier_unresolved_and_open_world_drift() -> None:
    checkpoint = _load_checkpoint()

    barrier = copy.deepcopy(checkpoint)
    barrier["frame_terminal_bindings"]["F2"]["barrier_state"] = "UNRESOLVED_SOURCE_BARRIER"
    barrier["checkpoint_sha256"] = checkpoint_content_digest(barrier)
    with pytest.raises(ProductDiscoveryError, match="F2 terminal barrier_state must be null"):
        validate_a2_bounded_frame_checkpoint(barrier)

    f3_barrier = copy.deepcopy(checkpoint)
    f3_barrier["frame_terminal_bindings"]["F3"]["barrier_state"] = "UNRESOLVED_SOURCE_BARRIER"
    f3_barrier["checkpoint_sha256"] = checkpoint_content_digest(f3_barrier)
    with pytest.raises(ProductDiscoveryError, match="F3 terminal barrier_state must be null"):
        validate_a2_bounded_frame_checkpoint(f3_barrier)

    f9_barrier = copy.deepcopy(checkpoint)
    f9_barrier["frame_terminal_bindings"]["F9"]["barrier_state"] = "UNRESOLVED_SOURCE_BARRIER"
    f9_barrier["checkpoint_sha256"] = checkpoint_content_digest(f9_barrier)
    with pytest.raises(ProductDiscoveryError, match="F9 terminal barrier_state must be null"):
        validate_a2_bounded_frame_checkpoint(f9_barrier)

    unresolved = copy.deepcopy(checkpoint)
    unresolved["unresolved_candidates"] = unresolved["unresolved_candidates"][1:]
    unresolved["unresolved_candidate_count"] = len(unresolved["unresolved_candidates"])
    unresolved["unresolved_candidate_set_sha256"] = unresolved_candidate_set_digest(unresolved["unresolved_candidates"])
    unresolved["checkpoint_sha256"] = checkpoint_content_digest(unresolved)
    with pytest.raises(ProductDiscoveryError, match="unresolved_candidates drifted"):
        validate_a2_bounded_frame_checkpoint(unresolved)

    count_mismatch = copy.deepcopy(checkpoint)
    count_mismatch["unresolved_candidate_count"] = 0
    count_mismatch["checkpoint_sha256"] = checkpoint_content_digest(count_mismatch)
    with pytest.raises(ProductDiscoveryError, match="unresolved_candidate_count does not match"):
        validate_a2_bounded_frame_checkpoint(count_mismatch)

    open_world = copy.deepcopy(checkpoint)
    open_world["open_world_frames_not_started"] = ["F1", "F4", "F5", "F6", "F8"]
    open_world["checkpoint_sha256"] = checkpoint_content_digest(open_world)
    with pytest.raises(ProductDiscoveryError, match="open_world_frames_not_started must be exactly"):
        validate_a2_bounded_frame_checkpoint(open_world)

    boundary = copy.deepcopy(checkpoint)
    boundary["boundary"] = "overclaim"
    boundary["checkpoint_sha256"] = checkpoint_content_digest(boundary)
    with pytest.raises(ProductDiscoveryError, match="checkpoint boundary drift"):
        validate_a2_bounded_frame_checkpoint(boundary)

    next_state = copy.deepcopy(checkpoint)
    next_state["next_required_state"] = "start A3 now"
    next_state["checkpoint_sha256"] = checkpoint_content_digest(next_state)
    with pytest.raises(ProductDiscoveryError, match="next_required_state drift"):
        validate_a2_bounded_frame_checkpoint(next_state)

    f9_feeds = copy.deepcopy(checkpoint)
    f9_feeds["frame_terminal_bindings"]["F9"]["feeds_primary_estimator"] = True
    f9_feeds["checkpoint_sha256"] = checkpoint_content_digest(f9_feeds)
    with pytest.raises(ProductDiscoveryError, match="F9 marked feeds_primary_estimator"):
        validate_a2_bounded_frame_checkpoint(f9_feeds)


def test_direct_terminal_binding_validators_fail_closed() -> None:
    checkpoint = _load_checkpoint()
    f2 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F2"])
    f2["frame_id"] = "F3"
    with pytest.raises(ProductDiscoveryError, match="F2 terminal binding frame_id drift"):
        _validate_f2_binding(f2)
    f2 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F2"])
    f2["stop_state"] = "CONTINUE"
    with pytest.raises(ProductDiscoveryError, match="F2 terminal stop_state"):
        _validate_f2_binding(f2)
    f2 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F2"])
    f2["provider_query_universe_id"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F2 provider_query_universe_id drift"):
        _validate_f2_binding(f2)
    f2 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F2"])
    f2["final_packet_id"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F2 final_packet_id drift"):
        _validate_f2_binding(f2)
    f2 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F2"])
    f2["final_run_id"] = "PDR-" + ("1" * 64)
    with pytest.raises(ProductDiscoveryError, match="F2 final_run_id"):
        _validate_f2_binding(f2)
    f2 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F2"])
    f2["source_exhaustion_state"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F2 source_exhaustion_state drift"):
        _validate_f2_binding(f2)

    f3 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F3"])
    f3["frame_id"] = "F2"
    with pytest.raises(ProductDiscoveryError, match="F3 terminal binding frame_id drift"):
        _validate_f3_binding(f3)
    f3 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F3"])
    f3["stop_state"] = "CONTINUE"
    with pytest.raises(ProductDiscoveryError, match="F3 terminal stop_state"):
        _validate_f3_binding(f3)
    f3 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F3"])
    f3["provider_query_universe_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="F3 provider_query_universe_sha256 drift"):
        _validate_f3_binding(f3)
    f3 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F3"])
    f3["final_packet_id"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F3 final_packet_id drift"):
        _validate_f3_binding(f3)
    f3 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F3"])
    f3["source_exhaustion_state"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F3 source_exhaustion_state drift"):
        _validate_f3_binding(f3)

    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["frame_id"] = "F2"
    with pytest.raises(ProductDiscoveryError, match="F9 terminal binding frame_id drift"):
        _validate_f9_binding(f9)
    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["stop_state"] = "CONTINUE"
    with pytest.raises(ProductDiscoveryError, match="F9 terminal stop_state"):
        _validate_f9_binding(f9)
    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["procedure_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="F9 procedure_sha256 drift"):
        _validate_f9_binding(f9)
    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["final_completion_ledger_id"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F9 final_completion_ledger_id drift"):
        _validate_f9_binding(f9)
    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["final_source_packet_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="F9 final_source_packet_sha256 drift"):
        _validate_f9_binding(f9)
    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["source_exhaustion_state"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F9 source_exhaustion_state drift"):
        _validate_f9_binding(f9)
    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["procedure_id"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F9 procedure_id drift"):
        _validate_f9_binding(f9)
    f9 = copy.deepcopy(checkpoint["frame_terminal_bindings"]["F9"])
    f9["final_source_packet_id"] = "WRONG"
    with pytest.raises(ProductDiscoveryError, match="F9 final_source_packet_id drift"):
        _validate_f9_binding(f9)


def test_helper_guards_and_registry_projection() -> None:
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        _require_mapping("x", "label")
    registry = load_default_a1_identity_registry()
    offerings = canonical_offering_ids_from_registry(registry)
    assert offerings == _load_checkpoint()["canonical_offering_ids"]
    with pytest.raises(ProductDiscoveryError, match="identity registry record missing entity_id"):
        canonical_offering_ids_from_registry({"records": [{"entity": {}}]})

    checkpoint = _load_checkpoint()
    with pytest.raises(ProductDiscoveryError, match="schema validation failed"):
        _validate_schema({"checkpoint_id": "WRONG"})

    unsorted_unresolved = copy.deepcopy(checkpoint)
    unsorted_unresolved["unresolved_candidates"] = list(reversed(unsorted_unresolved["unresolved_candidates"]))
    unsorted_unresolved["unresolved_candidate_set_sha256"] = unresolved_candidate_set_digest(
        unsorted_unresolved["unresolved_candidates"]
    )
    with pytest.raises(ProductDiscoveryError, match="unresolved_candidates must be sorted"):
        _validate_unresolved(unsorted_unresolved)

    digest_bad = copy.deepcopy(checkpoint)
    digest_bad["unresolved_candidate_set_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="unresolved_candidate_set_sha256 digest mismatch"):
        _validate_unresolved(digest_bad)

    duplicate = copy.deepcopy(checkpoint)
    mid = duplicate["unresolved_candidates"][len(duplicate["unresolved_candidates"]) // 2]
    insert_at = next(
        index
        for index, item in enumerate(duplicate["unresolved_candidates"])
        if item["frame_id"] == mid["frame_id"] and item["candidate_key"] == mid["candidate_key"]
    )
    duplicate["unresolved_candidates"] = (
        list(duplicate["unresolved_candidates"][: insert_at + 1])
        + [copy.deepcopy(mid)]
        + list(duplicate["unresolved_candidates"][insert_at + 1 :])
    )
    duplicate["unresolved_candidate_count"] = len(duplicate["unresolved_candidates"])
    duplicate["unresolved_candidate_set_sha256"] = unresolved_candidate_set_digest(duplicate["unresolved_candidates"])
    with pytest.raises(ProductDiscoveryError, match="duplicate frame/candidate keys"):
        _validate_unresolved(duplicate)

    empty = copy.deepcopy(checkpoint)
    empty["unresolved_candidates"] = []
    empty["unresolved_candidate_count"] = 0
    empty["unresolved_candidate_set_sha256"] = unresolved_candidate_set_digest([])
    with pytest.raises(ProductDiscoveryError, match="unresolved_candidates drifted|empty unexpectedly"):
        _validate_unresolved(empty)

    claim = copy.deepcopy(checkpoint)
    claim["claim_scope"] = "GLOBAL_COMPLETENESS"
    claim["checkpoint_sha256"] = checkpoint_content_digest(claim)
    with pytest.raises(ProductDiscoveryError, match="schema validation failed|claim_scope"):
        validate_a2_bounded_frame_checkpoint(claim)

    status = copy.deepcopy(checkpoint)
    status["status"] = "DRAFT"
    status["checkpoint_sha256"] = checkpoint_content_digest(status)
    with pytest.raises(ProductDiscoveryError, match="schema validation failed|status"):
        validate_a2_bounded_frame_checkpoint(status)

    market = copy.deepcopy(checkpoint)
    market["market_share_claim"] = True
    with pytest.raises(ProductDiscoveryError, match="estimator contamination field present"):
        validate_a2_bounded_frame_checkpoint(market)

    f2_universe = copy.deepcopy(checkpoint)
    f2_universe["frame_terminal_bindings"]["F2"]["provider_query_universe_sha256"] = "0" * 64
    f2_universe["checkpoint_sha256"] = checkpoint_content_digest(f2_universe)
    with pytest.raises(ProductDiscoveryError, match="F2 provider_query_universe_sha256 drift"):
        validate_a2_bounded_frame_checkpoint(f2_universe)

    f3_run = copy.deepcopy(checkpoint)
    f3_run["frame_terminal_bindings"]["F3"]["final_packet_sha256"] = "0" * 64
    f3_run["checkpoint_sha256"] = checkpoint_content_digest(f3_run)
    with pytest.raises(ProductDiscoveryError, match="F3 final_packet_sha256 drift"):
        validate_a2_bounded_frame_checkpoint(f3_run)


def test_monkeypatched_packet_and_terminal_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    import neuroai_workbench.a2_bounded_frame_checkpoint as mod

    checkpoint = _load_checkpoint()
    real_load = mod._load_json_resource

    def fake_load(package: str, name: str) -> dict[str, Any]:
        payload = real_load(package, name)
        if name == mod.F2_FINAL_PACKET_RESOURCE:
            mutated = copy.deepcopy(payload)
            mutated["packet_sha256"] = "0" * 64
            return mutated
        return payload

    monkeypatch.setattr(mod, "_load_json_resource", fake_load)
    with pytest.raises(ProductDiscoveryError, match="F2 final packet content digest drift"):
        _validate_f2_binding(checkpoint["frame_terminal_bindings"]["F2"])

    def fake_load_f3(package: str, name: str) -> dict[str, Any]:
        payload = real_load(package, name)
        if name == mod.F3_FINAL_PACKET_RESOURCE:
            mutated = copy.deepcopy(payload)
            mutated["f3_exhaustion_state"] = "CONTINUE"
            return mutated
        return payload

    monkeypatch.setattr(mod, "_load_json_resource", fake_load_f3)
    monkeypatch.setattr(mod, "_packet_content_sha256", lambda _packet: mod.F3_FINAL_PACKET_SHA256)
    with pytest.raises(ProductDiscoveryError, match="F3 final packet exhaustion state missing"):
        _validate_f3_binding(checkpoint["frame_terminal_bindings"]["F3"])

    def fake_load_f3_f2(package: str, name: str) -> dict[str, Any]:
        payload = real_load(package, name)
        if name == mod.F3_FINAL_PACKET_RESOURCE:
            mutated = copy.deepcopy(payload)
            mutated["f2_exhaustion_state"] = "CONTINUE"
            return mutated
        return payload

    monkeypatch.setattr(mod, "_load_json_resource", fake_load_f3_f2)
    monkeypatch.setattr(mod, "_packet_content_sha256", lambda _packet: mod.F3_FINAL_PACKET_SHA256)
    with pytest.raises(ProductDiscoveryError, match="F3 final packet must preserve F2"):
        _validate_f3_binding(checkpoint["frame_terminal_bindings"]["F3"])

    def fake_load_f9(package: str, name: str) -> dict[str, Any]:
        payload = real_load(package, name)
        if name == mod.F9_FINAL_LEDGER_RESOURCE:
            mutated = copy.deepcopy(payload)
            mutated["f9_exhaustion_state"] = "CONTINUE"
            return mutated
        return payload

    monkeypatch.setattr(mod, "_load_json_resource", fake_load_f9)
    monkeypatch.setattr(mod, "f9_actor_completion_ledger_digest", lambda _ledger: mod.F9_FINAL_LEDGER_SHA256)
    with pytest.raises(ProductDiscoveryError, match="F9 ledger exhaustion state missing"):
        _validate_f9_binding(checkpoint["frame_terminal_bindings"]["F9"])

    def fake_load_f9_universe(package: str, name: str) -> dict[str, Any]:
        payload = real_load(package, name)
        if name == mod.F9_FINAL_LEDGER_RESOURCE:
            mutated = copy.deepcopy(payload)
            mutated["analysis_universe_id"] = "RAU-" + ("0" * 64)
            return mutated
        return payload

    monkeypatch.setattr(mod, "_load_json_resource", fake_load_f9_universe)
    monkeypatch.setattr(mod, "f9_actor_completion_ledger_digest", lambda _ledger: mod.F9_FINAL_LEDGER_SHA256)
    with pytest.raises(ProductDiscoveryError, match="F9 ledger analysis universe drift"):
        _validate_f9_binding(checkpoint["frame_terminal_bindings"]["F9"])

    # Restore default loader for remaining checks.
    monkeypatch.setattr(mod, "_load_json_resource", real_load)
    missing_terminal = copy.deepcopy(checkpoint)
    del missing_terminal["frame_terminal_bindings"]["F2"]
    missing_terminal["checkpoint_sha256"] = checkpoint_content_digest(missing_terminal)
    with pytest.raises(ProductDiscoveryError, match="schema validation failed|missing terminal binding"):
        validate_a2_bounded_frame_checkpoint(missing_terminal)

    _reject = mod._reject_estimator_contamination_markers
    _reject({"frame_terminal_bindings": "not-a-mapping"})
    with pytest.raises(ProductDiscoveryError, match="F11 marked feeds_primary_estimator"):
        _reject({"frame_terminal_bindings": {"F11": {"feeds_primary_estimator": True}}})
