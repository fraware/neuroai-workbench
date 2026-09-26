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
    checkpoint_content_digest,
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
