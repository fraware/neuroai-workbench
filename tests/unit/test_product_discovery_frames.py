from __future__ import annotations

from copy import deepcopy

import pytest

from neuroai_workbench.product_discovery_frames import (
    DISCOVERY_BOUNDARY,
    FRAME_REGISTER_VERSION,
    FRAME_VERSION,
    ProductDiscoveryError,
    build_capture_histories,
    evaluate_frame_stop,
    frame_overlap_matrix,
    identity_set_digest,
    incremental_unique_identities,
    load_default_frame_register,
    product_capture_id,
    product_discovery_run_id,
    summarize_discovery_contributions,
    summarize_discovery_round,
    validate_capture_against_frame,
    validate_discovery_frame,
    validate_discovery_run,
    validate_frame_register,
    validate_product_capture,
    validate_run_against_captures,
)


def _frame(
    frame_id: str,
    frame_class: str,
    *,
    capture_eligible: bool = True,
    dependencies: list[str] | None = None,
    mode: str = "MARGINAL_YIELD",
) -> dict[str, object]:
    rule: dict[str, object] = {
        "mode": mode,
        "minimum_completed_rounds": 3 if mode == "MARGINAL_YIELD" else None,
        "consecutive_low_yield_rounds": 2 if mode == "MARGINAL_YIELD" else None,
        "maximum_marginal_new_identity_yield": 0.05 if mode == "MARGINAL_YIELD" else None,
        "minimum_raw_candidates_per_round": 20 if mode == "MARGINAL_YIELD" else None,
    }
    return {
        "frame_id": frame_id,
        "frame_version": FRAME_VERSION,
        "label": f"Synthetic {frame_id}",
        "frame_class": frame_class,
        "purpose": "Synthetic test frame",
        "capture_estimation_eligible": capture_eligible,
        "dependence_notes": "Synthetic dependence statement.",
        "dependent_or_nested_with": dependencies or [],
        "languages": ["en"],
        "jurisdictions": ["GLOBAL"],
        "query_families": ["Q1"],
        "source_classes": ["PUBLIC"],
        "stopping_rule": rule,
        "status": "ACTIVE",
        "boundary": DISCOVERY_BOUNDARY,
    }


def _capture(
    frame_id: str,
    candidate: str,
    *,
    offering_id: str | None,
    outcome: str = "INCLUDE_RESOLVED",
    round_id: str = "R1",
    language: str = "en",
    estimation_eligible: bool = True,
) -> dict[str, object]:
    capture: dict[str, object] = {
        "capture_id": "",
        "frame_id": frame_id,
        "frame_version": FRAME_VERSION,
        "round_id": round_id,
        "query_or_seed_id": f"Q-{frame_id}",
        "query_family": "Q1",
        "source_class": "PUBLIC",
        "candidate_key": candidate,
        "canonical_offering_id": offering_id,
        "source_observation_ref": f"OBS-{frame_id}-{candidate}",
        "language": language,
        "jurisdiction": "GLOBAL",
        "outcome": outcome,
        "capture_estimation_eligible": estimation_eligible,
        "observed_at": "2026-09-24T12:00:00Z",
        "registry_projection_version": "PRODUCT_REGISTRY_v1.0",
        "frame_register_version": FRAME_REGISTER_VERSION,
        "population_view_id": "A-P1",
        "analysis_jurisdiction_scope": "GLOBAL",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "boundary": DISCOVERY_BOUNDARY,
    }
    capture["capture_id"] = product_capture_id(capture)
    return capture


def test_frame_validation_preserves_dependence_and_excludes_purposive_frames_from_primary_estimator() -> None:
    f6 = _frame("F6", "CAPABILITY_FIRST", dependencies=["F1"])
    validate_discovery_frame(f6)

    self_dependent = deepcopy(f6)
    self_dependent["dependent_or_nested_with"] = ["F6"]
    with pytest.raises(ProductDiscoveryError, match="cannot be dependent"):
        validate_discovery_frame(self_dependent)

    for frame_id, frame_class in (
        ("F7", "EXPERT_NOMINATION"),
        ("F9", "CURATED_ACTOR_SEED"),
        ("F11", "SNOWBALL_EXPANSION"),
    ):
        frame = _frame(frame_id, frame_class, capture_eligible=True)
        with pytest.raises(ProductDiscoveryError, match="cannot enter the primary capture estimator"):
            validate_discovery_frame(frame)


def test_capture_id_is_deterministic_and_resolved_include_requires_identity() -> None:
    capture = _capture("F1", "muse-athena", offering_id="PRD-MUSE-ATHENA")
    validate_product_capture(capture)
    assert capture["capture_id"] == product_capture_id(capture)

    invalid = deepcopy(capture)
    invalid["canonical_offering_id"] = None
    invalid["capture_id"] = product_capture_id(invalid)
    with pytest.raises(ProductDiscoveryError, match="requires canonical_offering_id"):
        validate_product_capture(invalid)


def test_capture_history_is_binary_after_within_frame_deduplication_and_overlap_is_exact() -> None:
    frames = [
        _frame("F1", "FIRST_PARTY"),
        _frame("F2", "REGULATORY", dependencies=["F1"]),
        _frame("F6", "CAPABILITY_FIRST", dependencies=["F1"]),
        _frame("F8", "LOCAL_LANGUAGE"),
    ]
    captures = [
        _capture("F1", "muse-a", offering_id="PRD-MUSE"),
        _capture("F1", "muse-b", offering_id="PRD-MUSE"),
        _capture("F2", "muse-fda", offering_id="PRD-MUSE"),
        _capture("F6", "guardian", offering_id="PRD-GUARDIAN"),
        _capture("F8", "neu-jp", offering_id="PRD-HOT2000", language="ja"),
        _capture("F1", "hot-en", offering_id="PRD-HOT2000"),
    ]
    histories = build_capture_histories(captures, frames)
    assert histories["PRD-MUSE"] == {"F1": 1, "F2": 1, "F6": 0, "F8": 0}
    assert histories["PRD-GUARDIAN"] == {"F1": 0, "F2": 0, "F6": 1, "F8": 0}
    assert histories["PRD-HOT2000"] == {"F1": 1, "F2": 0, "F6": 0, "F8": 1}

    overlap = frame_overlap_matrix(captures, frames)
    assert overlap["F1"]["F1"] == 2
    assert overlap["F1"]["F2"] == 1
    assert overlap["F1"]["F8"] == 1
    assert overlap["F6"]["F8"] == 0


def test_estimation_histories_exclude_noneligible_expert_frame() -> None:
    frames = [
        _frame("F1", "FIRST_PARTY"),
        _frame("F7", "EXPERT_NOMINATION", capture_eligible=False),
    ]
    captures = [
        _capture("F1", "known", offering_id="PRD-A"),
        _capture(
            "F7",
            "expert-only",
            offering_id="PRD-B",
            estimation_eligible=False,
        ),
    ]
    histories = build_capture_histories(captures, frames, estimation_eligible_only=True)
    assert histories == {"PRD-A": {"F1": 1}}


def test_round_summary_separates_new_products_from_duplicate_captures_and_failures() -> None:
    captures = [
        _capture("F1", "known", offering_id="PRD-KNOWN"),
        _capture("F1", "new-a", offering_id="PRD-NEW"),
        _capture("F1", "new-a-repeat", offering_id="PRD-NEW"),
        _capture(
            "F1",
            "excluded",
            offering_id=None,
            outcome="EXCLUDE",
            estimation_eligible=False,
        ),
        _capture(
            "F1",
            "failed",
            offering_id=None,
            outcome="FAILED_INACCESSIBLE",
            estimation_eligible=False,
        ),
    ]
    summary = summarize_discovery_round(
        captures,
        known_identity_ids_before={"PRD-KNOWN"},
    )
    assert summary["raw_candidates"] == 5
    assert summary["unique_resolved_include_identities"] == 2
    assert summary["new_resolved_include_identities"] == 1
    assert summary["known_identity_duplicate_count"] == 1
    assert summary["within_round_duplicate_count"] == 1
    assert summary["duplicate_capture_count"] == 2
    assert summary["outcome_counts"]["EXCLUDE"] == 1
    assert summary["outcome_counts"]["FAILED_INACCESSIBLE"] == 1
    assert summary["marginal_new_identity_yield"] == pytest.approx(0.2)
    assert summary["duplicate_yield"] == pytest.approx(0.4)


def test_capability_and_multilingual_incremental_yield_is_computed_after_identity_deduplication() -> None:
    captures = [
        _capture("F1", "base-a", offering_id="PRD-A"),
        _capture("F6", "cap-a-duplicate", offering_id="PRD-A"),
        _capture("F6", "cap-b", offering_id="PRD-B"),
        _capture("F8", "local-c", offering_id="PRD-C", language="ja"),
    ]
    capability_gain = incremental_unique_identities(
        captures,
        baseline_frame_ids={"F1"},
        expanded_frame_ids={"F1", "F6"},
    )
    assert capability_gain == {"PRD-B"}

    multilingual_gain = incremental_unique_identities(
        captures,
        baseline_frame_ids={"F1", "F6"},
        expanded_frame_ids={"F1", "F6", "F8"},
    )
    assert multilingual_gain == {"PRD-C"}


def test_capture_source_and_query_provenance_must_match_declared_frame() -> None:
    frame = _frame("F1", "FIRST_PARTY")
    capture = _capture("F1", "x", offering_id="PRD-X")
    validate_capture_against_frame(capture, frame)

    wrong_query = deepcopy(capture)
    wrong_query["query_family"] = "OTHER_QUERY"
    wrong_query["capture_id"] = product_capture_id(wrong_query)
    with pytest.raises(ProductDiscoveryError, match="query_family"):
        validate_capture_against_frame(wrong_query, frame)

    wrong_source = deepcopy(capture)
    wrong_source["source_class"] = "OTHER_SOURCE"
    wrong_source["capture_id"] = product_capture_id(wrong_source)
    with pytest.raises(ProductDiscoveryError, match="source_class"):
        validate_capture_against_frame(wrong_source, frame)


def test_capture_and_frame_eligibility_must_agree() -> None:
    frame = _frame("F7", "EXPERT_NOMINATION", capture_eligible=False)
    capture = _capture("F7", "expert", offering_id="PRD-X", estimation_eligible=True)
    with pytest.raises(ProductDiscoveryError, match="estimation-eligible"):
        validate_capture_against_frame(capture, frame)


def test_predeclared_stop_rule_uses_consecutive_low_yield_rounds_only() -> None:
    frame = _frame("F6", "CAPABILITY_FIRST")
    summaries = [
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.20},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.04},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.03},
    ]
    assert evaluate_frame_stop(frame, summaries) == "SATURATION_UNDER_DECLARED_PROTOCOL"

    high_tail = summaries[:-1] + [{"raw_candidates": 30, "marginal_new_identity_yield": 0.10}]
    assert evaluate_frame_stop(frame, high_tail) == "CONTINUE"
    assert evaluate_frame_stop(frame, summaries, budget_limit_reached=True) == "BUDGET_COVERAGE_TERMINATION"
    assert evaluate_frame_stop(frame, summaries, unresolved_source_barrier=True) == "UNRESOLVED_SOURCE_BARRIER"

    bounded = _frame("F2", "REGULATORY", mode="BOUNDED_SOURCE_EXHAUSTION")
    assert evaluate_frame_stop(bounded, [], source_exhausted=True) == "BOUNDED_FRAME_EXHAUSTED"


def test_validation_rejects_frame_mismatch_duplicate_frames_and_undeclared_capture_frame() -> None:
    f1 = _frame("F1", "FIRST_PARTY")
    f2 = _frame("F2", "REGULATORY")
    capture = _capture("F1", "x", offering_id="PRD-X")

    with pytest.raises(ProductDiscoveryError, match="frame_id does not match"):
        validate_capture_against_frame(capture, f2)

    with pytest.raises(ProductDiscoveryError, match="Duplicate discovery frame definition"):
        build_capture_histories([capture], [f1, deepcopy(f1)])

    f6_capture = _capture("F6", "y", offering_id="PRD-Y")
    with pytest.raises(ProductDiscoveryError, match="undeclared frame"):
        build_capture_histories([f6_capture], [f1])


def test_incremental_comparison_rejects_unknown_or_non_nested_frame_sets() -> None:
    capture = _capture("F1", "x", offering_id="PRD-X")
    with pytest.raises(ProductDiscoveryError, match="Unknown discovery frame"):
        incremental_unique_identities(
            [capture],
            baseline_frame_ids={"F1"},
            expanded_frame_ids={"F1", "F12"},
        )
    with pytest.raises(ProductDiscoveryError, match="must be a subset"):
        incremental_unique_identities(
            [capture],
            baseline_frame_ids={"F1", "F2"},
            expanded_frame_ids={"F1"},
        )


def test_stop_rule_continues_with_too_few_or_too_small_rounds() -> None:
    frame = _frame("F6", "CAPABILITY_FIRST")
    too_few = [{"raw_candidates": 30, "marginal_new_identity_yield": 0.01}]
    assert evaluate_frame_stop(frame, too_few) == "CONTINUE"

    too_small = [
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.10},
        {"raw_candidates": 5, "marginal_new_identity_yield": 0.01},
        {"raw_candidates": 5, "marginal_new_identity_yield": 0.01},
    ]
    assert evaluate_frame_stop(frame, too_small) == "CONTINUE"


def test_frame_id_has_frozen_semantic_class() -> None:
    wrong = _frame("F9", "FIRST_PARTY")
    with pytest.raises(ProductDiscoveryError, match="frame_class must be"):
        validate_discovery_frame(wrong)
    validate_discovery_frame(_frame("F9", "CURATED_ACTOR_SEED", capture_eligible=False))
    validate_discovery_frame(_frame("F10", "PATENT_COMMERCIALIZATION"))
    validate_discovery_frame(_frame("F11", "SNOWBALL_EXPANSION", capture_eligible=False))


def test_capture_histories_fail_closed_across_analysis_universes() -> None:
    frame = _frame("F1", "FIRST_PARTY")
    a = _capture("F1", "a", offering_id="PRD-A")
    b = _capture("F1", "b", offering_id="PRD-B")
    b["population_view_id"] = "A-P6"
    b["capture_id"] = product_capture_id(b)
    with pytest.raises(ProductDiscoveryError, match="cannot mix"):
        build_capture_histories([a, b], [frame])


def test_language_and_jurisdiction_contributions_are_deduplicated() -> None:
    captures = [
        _capture("F1", "a-en", offering_id="PRD-A", language="en"),
        _capture("F8", "a-ja", offering_id="PRD-A", language="ja"),
        _capture("F8", "b-ja", offering_id="PRD-B", language="ja"),
    ]
    captures[1]["jurisdiction"] = "JP"
    captures[1]["capture_id"] = product_capture_id(captures[1])
    captures[2]["jurisdiction"] = "JP"
    captures[2]["capture_id"] = product_capture_id(captures[2])
    result = summarize_discovery_contributions(
        captures,
        known_identity_ids_before={"PRD-A"},
    )
    assert result["by_language"]["ja"]["unique_resolved_include_identities"] == 2
    assert result["by_language"]["ja"]["new_resolved_include_identities"] == 1
    assert result["by_jurisdiction"]["JP"]["new_resolved_include_identities"] == 1


def test_underpowered_intervening_round_breaks_low_yield_consecutive_tail() -> None:
    frame = _frame("F6", "CAPABILITY_FIRST")
    summaries = [
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.20},
        {"raw_candidates": 30, "marginal_new_identity_yield": 0.04},
        {"raw_candidates": 5, "marginal_new_identity_yield": 0.01},
    ]
    assert evaluate_frame_stop(frame, summaries) == "CONTINUE"


def test_discovery_run_binds_exact_universe_and_capture_set() -> None:
    frame = _frame("F1", "FIRST_PARTY")
    captures = [
        _capture("F1", "a", offering_id="PRD-A"),
        _capture("F1", "b", offering_id="PRD-B"),
    ]
    run: dict[str, object] = {
        "run_id": "",
        "frame_id": "F1",
        "frame_version": FRAME_VERSION,
        "frame_register_version": FRAME_REGISTER_VERSION,
        "round_id": "R1",
        "query_or_seed_ids": ["Q-F1"],
        "languages": ["en"],
        "jurisdictions": ["GLOBAL"],
        "analysis_jurisdiction_scope": "GLOBAL",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "registry_projection_version": "PRODUCT_REGISTRY_v1.0",
        "population_view_id": "A-P1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "known_identity_set_sha256": identity_set_digest({"PRD-KNOWN"}),
        "capture_count": 2,
        "capture_ids": [str(capture["capture_id"]) for capture in captures],
        "stop_state": "CONTINUE",
        "stop_reason": "Further declared rounds remain.",
        "boundary": DISCOVERY_BOUNDARY,
    }
    run["run_id"] = product_discovery_run_id(run)
    validate_discovery_run(run)
    validate_run_against_captures(run, captures, frame)

    drift = deepcopy(run)
    drift["capture_count"] = 1
    drift["run_id"] = product_discovery_run_id(drift)
    with pytest.raises(ProductDiscoveryError, match="capture_count"):
        validate_run_against_captures(drift, captures, frame)


def test_default_frame_register_is_complete_and_freezes_estimation_eligibility() -> None:
    register = load_default_frame_register()
    frames = {frame["frame_id"]: frame for frame in register["frames"]}
    assert set(frames) == {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11"}
    assert {frame_id for frame_id, frame in frames.items() if not frame["capture_estimation_eligible"]} == {
        "F7",
        "F9",
        "F11",
    }
    assert frames["F2"]["stopping_rule"]["mode"] == "BOUNDED_SOURCE_EXHAUSTION"
    assert frames["F6"]["stopping_rule"]["maximum_marginal_new_identity_yield"] == 0.05


def test_frame_register_rejects_missing_frame_and_eligibility_policy_drift() -> None:
    register = load_default_frame_register()
    missing = deepcopy(register)
    missing["frames"] = [frame for frame in missing["frames"] if frame["frame_id"] != "F11"]
    with pytest.raises(ProductDiscoveryError, match="exactly F1-F11"):
        validate_frame_register(missing)

    drift = deepcopy(register)
    drift["estimation_policy"]["purposive_frames_excluded"] = ["F7"]
    with pytest.raises(ProductDiscoveryError, match="exclusions"):
        validate_frame_register(drift)


def test_frame_register_rejects_identity_status_and_shape_drift() -> None:
    register = load_default_frame_register()

    wrong_id = deepcopy(register)
    wrong_id["register_id"] = "OTHER"
    with pytest.raises(ProductDiscoveryError, match="register_id"):
        validate_frame_register(wrong_id)

    wrong_status = deepcopy(register)
    wrong_status["status"] = "DRAFT"
    with pytest.raises(ProductDiscoveryError, match="FROZEN_v1.0"):
        validate_frame_register(wrong_status)

    wrong_shape = deepcopy(register)
    wrong_shape["frames"] = {}
    with pytest.raises(ProductDiscoveryError, match="must be a list"):
        validate_frame_register(wrong_shape)
