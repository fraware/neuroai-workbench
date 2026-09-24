from __future__ import annotations

from copy import deepcopy

import pytest

from neuroai_workbench.product_discovery_frames import (
    DISCOVERY_BOUNDARY,
    FRAME_VERSION,
    ProductDiscoveryError,
    build_capture_histories,
    evaluate_frame_stop,
    frame_overlap_matrix,
    incremental_unique_identities,
    product_capture_id,
    summarize_discovery_round,
    validate_capture_against_frame,
    validate_discovery_frame,
    validate_product_capture,
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
        "candidate_key": candidate,
        "canonical_offering_id": offering_id,
        "source_observation_ref": f"OBS-{frame_id}-{candidate}",
        "language": language,
        "jurisdiction": "GLOBAL",
        "outcome": outcome,
        "capture_estimation_eligible": estimation_eligible,
        "observed_at": "2026-09-24T12:00:00Z",
        "registry_projection_version": "PRODUCT_REGISTRY_v1.0",
        "population_view_id": "A-P1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-09-24T12:00:00Z",
        "boundary": DISCOVERY_BOUNDARY,
    }
    capture["capture_id"] = product_capture_id(capture)
    return capture


def test_frame_validation_preserves_dependence_and_excludes_expert_frame_from_primary_estimator() -> None:
    f6 = _frame("F6", "CAPABILITY_FIRST", dependencies=["F1"])
    validate_discovery_frame(f6)

    self_dependent = deepcopy(f6)
    self_dependent["dependent_or_nested_with"] = ["F6"]
    with pytest.raises(ProductDiscoveryError, match="cannot be dependent"):
        validate_discovery_frame(self_dependent)

    f7 = _frame("F7", "EXPERT_NOMINATION", capture_eligible=True)
    with pytest.raises(ProductDiscoveryError, match="cannot enter the primary capture estimator"):
        validate_discovery_frame(f7)


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
