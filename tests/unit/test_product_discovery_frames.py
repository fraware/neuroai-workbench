from __future__ import annotations

from copy import deepcopy

import pytest

from neuroai_workbench.product_discovery_frames import (
    ANALYSIS_UNIVERSE_BOUNDARY,
    DISCOVERY_BOUNDARY,
    FRAME_REGISTER_VERSION,
    FRAME_VERSION,
    ProductDiscoveryError,
    analysis_universe_id,
    build_capture_histories,
    evaluate_frame_stop,
    frame_overlap_matrix,
    identity_set_digest,
    incremental_unique_identities,
    load_default_analysis_universe,
    load_default_frame_register,
    load_f9_actor_seed_register,
    product_capture_id,
    product_discovery_run_id,
    summarize_discovery_contributions,
    summarize_discovery_round,
    validate_analysis_universe,
    validate_capture_against_analysis_universe,
    validate_capture_against_frame,
    validate_discovery_frame,
    validate_discovery_run,
    validate_f9_actor_seed_register,
    validate_frame_register,
    validate_product_capture,
    validate_run_against_analysis_universe,
    validate_run_against_captures,
)


TEST_ANALYSIS_UNIVERSE_ID = "A2U-" + ("0" * 64)


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
        "analysis_universe_id": TEST_ANALYSIS_UNIVERSE_ID,
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


def test_estimation_histories_respect_per_capture_eligibility_within_eligible_frame() -> None:
    frame = _frame("F1", "FIRST_PARTY")
    eligible = _capture("F1", "eligible", offering_id="PRD-ELIGIBLE", estimation_eligible=True)
    outside_target_view = _capture(
        "F1",
        "outside-target-view",
        offering_id="PRD-OUTSIDE",
        estimation_eligible=False,
    )

    observed = build_capture_histories([eligible, outside_target_view], [frame])
    assert set(observed) == {"PRD-ELIGIBLE", "PRD-OUTSIDE"}

    estimator = build_capture_histories(
        [eligible, outside_target_view],
        [frame],
        estimation_eligible_only=True,
    )
    assert estimator == {"PRD-ELIGIBLE": {"F1": 1}}


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


def test_round_summary_rejects_mixed_frames_rounds_and_analysis_universes() -> None:
    first = _capture("F1", "a", offering_id="PRD-A")
    other_frame = _capture("F2", "b", offering_id="PRD-B")
    with pytest.raises(ProductDiscoveryError, match="cannot mix discovery frames"):
        summarize_discovery_round([first, other_frame])

    other_round = _capture("F1", "c", offering_id="PRD-C", round_id="R2")
    with pytest.raises(ProductDiscoveryError, match="cannot mix round_id"):
        summarize_discovery_round([first, other_round])

    other_view = deepcopy(first)
    other_view["candidate_key"] = "other-view"
    other_view["population_view_id"] = "A-P6"
    other_view["capture_id"] = product_capture_id(other_view)
    with pytest.raises(ProductDiscoveryError, match="cannot mix registry/view"):
        summarize_discovery_round([first, other_view])

    other_universe = deepcopy(first)
    other_universe["candidate_key"] = "other-universe"
    other_universe["analysis_universe_id"] = "A2U-" + ("1" * 64)
    other_universe["capture_id"] = product_capture_id(other_universe)
    with pytest.raises(ProductDiscoveryError, match="cannot mix registry/view"):
        summarize_discovery_round([first, other_universe])


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


def test_capture_cannot_postdate_its_knowledge_cutoff() -> None:
    capture = _capture("F1", "future", offering_id="PRD-X")
    capture["observed_at"] = "2026-09-24T13:00:01Z"
    capture["knowledge_time_cutoff"] = "2026-09-24T13:00:00Z"
    capture["capture_id"] = product_capture_id(capture)
    with pytest.raises(ProductDiscoveryError, match="cannot exceed"):
        validate_product_capture(capture)

    offset_equivalent = _capture("F1", "offset", offering_id="PRD-Y")
    offset_equivalent["observed_at"] = "2026-09-24T14:00:00+02:00"
    offset_equivalent["knowledge_time_cutoff"] = "2026-09-24T12:00:00Z"
    offset_equivalent["capture_id"] = product_capture_id(offset_equivalent)
    validate_product_capture(offset_equivalent)


def test_capture_rejects_invalid_or_naive_bound_timestamps() -> None:
    naive = _capture("F1", "naive-time", offering_id="PRD-X")
    naive["observed_at"] = "2026-09-24T12:00:00"
    naive["capture_id"] = product_capture_id(naive)
    with pytest.raises(ProductDiscoveryError, match="explicit timezone"):
        validate_product_capture(naive)

    invalid = _capture("F1", "invalid-time", offering_id="PRD-Y")
    invalid["knowledge_time_cutoff"] = "not-a-timestamp"
    invalid["capture_id"] = product_capture_id(invalid)
    with pytest.raises(ProductDiscoveryError, match="valid offset-aware timestamp"):
        validate_product_capture(invalid)


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

    eligible_frame = _frame("F1", "FIRST_PARTY", capture_eligible=True)
    nonqualifying_for_target_view = _capture(
        "F1",
        "known-in-scope-not-in-target-view",
        offering_id="PRD-X",
        estimation_eligible=False,
    )
    validate_capture_against_frame(nonqualifying_for_target_view, eligible_frame)


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


def test_capture_identity_binds_estimator_eligibility_and_analysis_universe() -> None:
    capture = _capture("F1", "x", offering_id="PRD-X")
    changed = deepcopy(capture)
    changed["capture_estimation_eligible"] = False
    assert product_capture_id(changed) != capture["capture_id"]

    other_universe = deepcopy(capture)
    other_universe["analysis_universe_id"] = "A2U-" + ("1" * 64)
    assert product_capture_id(other_universe) != capture["capture_id"]


def test_discovery_run_identity_binds_capture_set_and_stop_state() -> None:
    captures = [
        _capture("F1", "a", offering_id="PRD-A"),
        _capture("F1", "b", offering_id="PRD-B"),
    ]
    run: dict[str, object] = {
        "run_id": "",
        "analysis_universe_id": TEST_ANALYSIS_UNIVERSE_ID,
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

    changed_capture_set = deepcopy(run)
    changed_capture_set["capture_ids"] = [str(captures[0]["capture_id"])]
    changed_capture_set["capture_count"] = 1
    assert product_discovery_run_id(changed_capture_set) != run["run_id"]

    changed_stop = deepcopy(run)
    changed_stop["stop_state"] = "BUDGET_COVERAGE_TERMINATION"
    changed_stop["stop_reason"] = "Declared budget reached."
    assert product_discovery_run_id(changed_stop) != run["run_id"]


def test_discovery_run_binds_exact_universe_and_capture_set() -> None:
    frame = _frame("F1", "FIRST_PARTY")
    captures = [
        _capture("F1", "a", offering_id="PRD-A"),
        _capture("F1", "b", offering_id="PRD-B"),
    ]
    run: dict[str, object] = {
        "run_id": "",
        "analysis_universe_id": TEST_ANALYSIS_UNIVERSE_ID,
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

    permuted = deepcopy(run)
    permuted["query_or_seed_ids"] = list(reversed(permuted["query_or_seed_ids"]))
    permuted["languages"] = list(reversed(permuted["languages"]))
    permuted["jurisdictions"] = list(reversed(permuted["jurisdictions"]))
    permuted["capture_ids"] = list(reversed(permuted["capture_ids"]))
    assert product_discovery_run_id(permuted) == run["run_id"]

    wrong_language = deepcopy(captures[0])
    wrong_language["language"] = "ja"
    wrong_language["capture_id"] = product_capture_id(wrong_language)
    with pytest.raises(ProductDiscoveryError, match="language"):
        validate_run_against_captures(run, [wrong_language, captures[1]], frame)

    wrong_jurisdiction = deepcopy(captures[0])
    wrong_jurisdiction["jurisdiction"] = "JP"
    wrong_jurisdiction["capture_id"] = product_capture_id(wrong_jurisdiction)
    with pytest.raises(ProductDiscoveryError, match="jurisdiction"):
        validate_run_against_captures(run, [wrong_jurisdiction, captures[1]], frame)

    drift = deepcopy(run)
    drift["capture_count"] = 1
    drift["run_id"] = product_discovery_run_id(drift)
    with pytest.raises(ProductDiscoveryError, match="capture_count"):
        validate_run_against_captures(drift, captures, frame)


def _bind_capture_to_default_universe(
    capture: dict[str, object],
    universe: dict[str, object],
) -> dict[str, object]:
    language_scope = universe["language_scope"]
    assert isinstance(language_scope, dict)
    capture["analysis_universe_id"] = universe["analysis_universe_id"]
    capture["registry_projection_version"] = universe["registry_projection_version"]
    capture["frame_register_version"] = universe["frame_register_version"]
    capture["population_view_id"] = universe["population_view_id"]
    capture["analysis_jurisdiction_scope"] = universe["analysis_jurisdiction_scope"]
    capture["language_scope_id"] = language_scope["language_scope_id"]
    capture["world_time_cutoff"] = universe["world_time_cutoff"]
    capture["knowledge_time_cutoff"] = universe["knowledge_time_cutoff"]
    capture["observed_at"] = "2026-09-25T06:00:00Z"
    capture["capture_id"] = product_capture_id(capture)
    return capture


def test_default_analysis_universe_is_exactly_bound_to_a1_and_preregistered_frames() -> None:
    universe = load_default_analysis_universe()
    assert universe["analysis_universe_id"] == analysis_universe_id(universe)
    assert universe["analysis_universe_id"] == "A2U-bd43d6cf93edec79809785e8ae76e31873073d1670751818853244b953b4e439"
    assert universe["a1_seed_registry_sha256"] == "9ba43d5614fb1ebb668c097a20c2279dbaaa74511956c16ee6f278cbfc109672"
    assert universe["initial_known_offering_count"] == 6
    assert universe["initial_known_identity_set_sha256"] == identity_set_digest(universe["initial_known_offering_ids"])
    assert set(universe["primary_estimation_frame_ids"]) == {"F1", "F2", "F3", "F4", "F5", "F6", "F8", "F10"}
    assert set(universe["diagnostic_only_frame_ids"]) == {"F7", "F9", "F11"}
    assert universe["boundary"] == ANALYSIS_UNIVERSE_BOUNDARY
    language_scope = universe["language_scope"]
    assert language_scope["baseline_language"] == "en"
    assert {(item["language"], item["jurisdiction"]) for item in language_scope["native_language_strata"]} == {
        ("de", "Germany"),
        ("es", "Spain"),
        ("fr", "France"),
        ("ja", "Japan"),
        ("zh-Hans", "China"),
    }


def test_analysis_universe_identity_and_seed_binding_fail_closed_on_drift() -> None:
    universe = load_default_analysis_universe()

    changed_scope = deepcopy(universe)
    changed_scope["analysis_jurisdiction_scope"] = "OTHER"
    assert analysis_universe_id(changed_scope) != universe["analysis_universe_id"]
    with pytest.raises(ProductDiscoveryError, match="deterministic universe material"):
        validate_analysis_universe(changed_scope)

    changed_seed = deepcopy(universe)
    changed_seed["a1_seed_registry_sha256"] = "0" * 64
    changed_seed["analysis_universe_id"] = analysis_universe_id(changed_seed)
    with pytest.raises(ProductDiscoveryError, match="exact default A1 seed registry digest"):
        validate_analysis_universe(changed_seed)


def test_capture_and_run_bind_the_exact_default_analysis_universe() -> None:
    universe = load_default_analysis_universe()
    frame = _frame("F1", "FIRST_PARTY")
    capture = _bind_capture_to_default_universe(
        _capture("F1", "a", offering_id="PRD-A"),
        universe,
    )
    validate_capture_against_analysis_universe(capture, universe)

    run: dict[str, object] = {
        "run_id": "",
        "analysis_universe_id": universe["analysis_universe_id"],
        "frame_id": "F1",
        "frame_version": FRAME_VERSION,
        "frame_register_version": universe["frame_register_version"],
        "round_id": "R1",
        "query_or_seed_ids": ["Q-F1"],
        "languages": ["en"],
        "jurisdictions": ["GLOBAL"],
        "analysis_jurisdiction_scope": universe["analysis_jurisdiction_scope"],
        "language_scope_id": universe["language_scope"]["language_scope_id"],
        "registry_projection_version": universe["registry_projection_version"],
        "population_view_id": universe["population_view_id"],
        "world_time_cutoff": universe["world_time_cutoff"],
        "knowledge_time_cutoff": universe["knowledge_time_cutoff"],
        "known_identity_set_sha256": universe["initial_known_identity_set_sha256"],
        "capture_count": 1,
        "capture_ids": [capture["capture_id"]],
        "stop_state": "CONTINUE",
        "stop_reason": "Further declared rounds remain.",
        "boundary": DISCOVERY_BOUNDARY,
    }
    run["run_id"] = product_discovery_run_id(run)
    validate_run_against_analysis_universe(run, universe)
    validate_run_against_captures(run, [capture], frame)

    wrong = deepcopy(capture)
    wrong["analysis_universe_id"] = "A2U-" + ("1" * 64)
    wrong["capture_id"] = product_capture_id(wrong)
    with pytest.raises(ProductDiscoveryError, match="analysis_universe_id"):
        validate_capture_against_analysis_universe(wrong, universe)


def test_default_analysis_universe_uses_a_fixed_future_knowledge_window_without_backdating_world_state() -> None:
    universe = load_default_analysis_universe()
    assert universe["world_time_cutoff"] == "2026-09-24"
    assert universe["collection_window"] == {
        "opened_at": "2026-09-24T21:00:00Z",
        "closes_at": "2026-10-08T21:00:00Z",
    }
    assert universe["knowledge_time_cutoff"] == "2026-10-08T21:00:00Z"
    assert "do not backdate" in universe["post_world_cutoff_observation_policy"]


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


def test_f9_actor_seed_register_is_exactly_bound_and_purposive() -> None:
    register = load_f9_actor_seed_register()
    assert register["register_id"] == "RELEASE_A_F9_ACTOR_SEED_REGISTER_v1.0"
    assert register["frame_id"] == "F9"
    assert register["actor_count"] == 37
    assert len(register["actors"]) == 37
    assert len({actor["organization_id"] for actor in register["actors"]}) == 37
    assert register["source_binding"] == {
        "repository": "fraware/neuroai-observatory-data",
        "commit_sha": "35dcf13431eca40321bb64a88e1743d9313f9247",
        "path": "releases/data-v0.1.0-public-governing/records/canonical_observatory_release_v1.4.json",
        "blob_sha": "c13289b4093f2c59a01d6860365e7ad2c2d25ac7",
        "release_version": "v1.4",
        "evidence_cutoff": "2026-07-29",
    }
    assert register["estimator_role"] == "EXCLUDED_FROM_PRIMARY_UNSEEN_POPULATION_ESTIMATOR"


def test_f9_actor_seed_register_fails_closed_on_identity_or_count_drift() -> None:
    register = load_f9_actor_seed_register()

    wrong_count = deepcopy(register)
    wrong_count["actor_count"] = 36
    with pytest.raises(ProductDiscoveryError, match="actor_count"):
        validate_f9_actor_seed_register(wrong_count)

    duplicate = deepcopy(register)
    duplicate["actors"][1]["organization_id"] = duplicate["actors"][0]["organization_id"]
    with pytest.raises(ProductDiscoveryError, match="Duplicate F9 actor organization_id"):
        validate_f9_actor_seed_register(duplicate)

    wrong_frame = deepcopy(register)
    wrong_frame["frame_id"] = "F1"
    with pytest.raises(ProductDiscoveryError, match="frame_id F9"):
        validate_f9_actor_seed_register(wrong_frame)

    unbound = deepcopy(register)
    unbound["source_binding"]["blob_sha"] = ""
    with pytest.raises(ProductDiscoveryError, match="source_binding requires blob_sha"):
        validate_f9_actor_seed_register(unbound)


def test_f9_actor_seed_register_rejects_missing_core_fields() -> None:
    register = load_f9_actor_seed_register()

    wrong_id = deepcopy(register)
    wrong_id["register_id"] = "OTHER"
    with pytest.raises(ProductDiscoveryError, match="register_id"):
        validate_f9_actor_seed_register(wrong_id)

    wrong_version = deepcopy(register)
    wrong_version["frame_register_version"] = "OTHER"
    with pytest.raises(ProductDiscoveryError, match="must bind PRODUCT_DISCOVERY_FRAME_REGISTER"):
        validate_f9_actor_seed_register(wrong_version)

    wrong_role = deepcopy(register)
    wrong_role["estimator_role"] = "ELIGIBLE"
    with pytest.raises(ProductDiscoveryError, match="excluded"):
        validate_f9_actor_seed_register(wrong_role)

    no_actors = deepcopy(register)
    no_actors["actors"] = []
    no_actors["actor_count"] = 0
    with pytest.raises(ProductDiscoveryError, match="non-empty"):
        validate_f9_actor_seed_register(no_actors)

    malformed_actor = deepcopy(register)
    malformed_actor["actors"][0] = "ORG-0001"
    with pytest.raises(ProductDiscoveryError, match="entries must be objects"):
        validate_f9_actor_seed_register(malformed_actor)

    missing_name = deepcopy(register)
    missing_name["actors"][0]["canonical_name"] = ""
    with pytest.raises(ProductDiscoveryError, match="require organization_id and canonical_name"):
        validate_f9_actor_seed_register(missing_name)

    missing_binding = deepcopy(register)
    missing_binding["source_binding"] = None
    with pytest.raises(ProductDiscoveryError, match="exact source_binding"):
        validate_f9_actor_seed_register(missing_binding)


def test_f9_actor_seed_register_rejects_each_missing_source_binding_field() -> None:
    register = load_f9_actor_seed_register()
    for field in ("repository", "commit_sha", "path", "blob_sha"):
        changed = deepcopy(register)
        changed["source_binding"][field] = ""
        with pytest.raises(ProductDiscoveryError, match=f"source_binding requires {field}"):
            validate_f9_actor_seed_register(changed)


def test_discovery_records_reject_boundary_drift() -> None:
    capture = _capture("F1", "x", offering_id="PRD-X")
    capture["boundary"] = "weaker boundary"
    with pytest.raises(ProductDiscoveryError, match="capture boundary"):
        validate_product_capture(capture)

    valid_capture = _capture("F1", "x", offering_id="PRD-X")
    run: dict[str, object] = {
        "run_id": "",
        "analysis_universe_id": TEST_ANALYSIS_UNIVERSE_ID,
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
        "capture_count": 1,
        "capture_ids": [str(valid_capture["capture_id"])],
        "stop_state": "CONTINUE",
        "stop_reason": "Further declared rounds remain.",
        "boundary": "weaker boundary",
    }
    run["run_id"] = product_discovery_run_id(run)
    with pytest.raises(ProductDiscoveryError, match="run boundary"):
        validate_discovery_run(run)
