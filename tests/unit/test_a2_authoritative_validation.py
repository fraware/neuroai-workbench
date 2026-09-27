from __future__ import annotations

import pytest

from neuroai_workbench.product_discovery_frames import (
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    DISCOVERY_BOUNDARY,
    FRAME_REGISTER_VERSION,
    FRAME_VERSION,
    ProductDiscoveryError,
    derive_authoritative_run_stop_state,
    derive_capture_estimation_eligibility,
    identity_set_digest,
    product_capture_id,
    product_discovery_run_id,
    summarize_discovery_round,
    validate_authoritative_capture_estimation_eligibility,
    validate_authoritative_discovery_run,
    validate_run_known_identity_baseline,
)
from neuroai_workbench.product_registry import (
    BOUNDARY_CONTRACT_ID,
    BOUNDARY_CONTRACT_SEMANTIC_BLOB,
    CURRENTNESS_POLICY_ID,
    POPULATION_VIEW_POLICY_ID,
    REFERENCE_STANDARD_ID,
    REFERENCE_STANDARD_VALIDATION_STATE,
    REFERENCE_STANDARD_VERSION,
    REGISTRY_BOUNDARY,
    REGISTRY_PROJECTION_VERSION,
    registry_row_id,
)


def _frame(
    frame_id: str = "F1",
    frame_class: str = "FIRST_PARTY",
    *,
    capture_eligible: bool = True,
    mode: str = "MARGINAL_YIELD",
) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "frame_version": FRAME_VERSION,
        "label": f"Synthetic {frame_id}",
        "frame_class": frame_class,
        "purpose": "Synthetic authoritative-A2 validation frame.",
        "capture_estimation_eligible": capture_eligible,
        "dependence_notes": "Synthetic dependence statement.",
        "dependent_or_nested_with": [],
        "languages": ["en"],
        "jurisdictions": ["GLOBAL"],
        "query_families": ["Q1"],
        "source_classes": ["PUBLIC"],
        "stopping_rule": {
            "mode": mode,
            "minimum_completed_rounds": 3 if mode == "MARGINAL_YIELD" else None,
            "consecutive_low_yield_rounds": 2 if mode == "MARGINAL_YIELD" else None,
            "maximum_marginal_new_identity_yield": 0.05 if mode == "MARGINAL_YIELD" else None,
            "minimum_raw_candidates_per_round": 20 if mode == "MARGINAL_YIELD" else None,
        },
        "status": "ACTIVE",
        "boundary": DISCOVERY_BOUNDARY,
    }


def _capture(
    offering_id: str = "PRD-A",
    *,
    frame_id: str = "F1",
    round_id: str = "R1",
    population_view_id: str = "A-P1",
    outcome: str = "INCLUDE_RESOLVED",
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
        "candidate_key": f"{offering_id}-candidate",
        "canonical_offering_id": offering_id if outcome == "INCLUDE_RESOLVED" else None,
        "source_observation_ref": f"OBS-{offering_id}",
        "language": "en",
        "jurisdiction": "GLOBAL",
        "outcome": outcome,
        "capture_estimation_eligible": estimation_eligible,
        "observed_at": "2026-09-24T12:00:00Z",
        "registry_projection_version": REGISTRY_PROJECTION_VERSION,
        "frame_register_version": FRAME_REGISTER_VERSION,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "population_view_id": population_view_id,
        "analysis_jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "world_time_alignment": "EVIDENCE_SUPPORTS_AT_OR_BEFORE_CUTOFF",
        "world_time_support_ref": None,
        "boundary": DISCOVERY_BOUNDARY,
    }
    capture["capture_id"] = product_capture_id(capture)
    return capture


def _registry_row(
    offering_id: str = "PRD-A",
    *,
    currentness: str = "CURRENT",
    lifecycle: str = "RELEASED",
    access: str = "COMMERCIAL_DIRECT",
    deployment: str = "DOCUMENTED_CONSUMER_ACCESS",
    knowledge_time_cutoff: str = "2026-10-24T23:59:59Z",
) -> dict[str, object]:
    row: dict[str, object] = {
        "registry_row_id": "",
        "registry_projection_version": REGISTRY_PROJECTION_VERSION,
        "boundary_contract_id": BOUNDARY_CONTRACT_ID,
        "boundary_contract_semantic_blob": BOUNDARY_CONTRACT_SEMANTIC_BLOB,
        "reference_standard_id": REFERENCE_STANDARD_ID,
        "reference_standard_version": REFERENCE_STANDARD_VERSION,
        "reference_standard_validation_state": REFERENCE_STANDARD_VALIDATION_STATE,
        "population_view_policy_id": POPULATION_VIEW_POLICY_ID,
        "currentness_policy_id": CURRENTNESS_POLICY_ID,
        "canonical_entity_id": offering_id,
        "canonical_entity_type": "PRODUCT",
        "identity_level": "OFFERING",
        "product_family_id": None,
        "product_offering_id": offering_id,
        "configuration_system_id": None,
        "configuration_coverage_state": "NOT_APPLICABLE",
        "system_or_offering_role": "OFFERING",
        "offering_kind": "BUNDLE",
        "primary_enumeration_role": "INTEGRATED_SYSTEM",
        "jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": knowledge_time_cutoff,
        "identity_state": "RESOLVED",
        "boundary_disposition": "INCLUDE",
        "boundary_disposition_ref": "D4_PRODUCT_REFERENCE_STANDARD_v1.0:D4-REF-001",
        "lifecycle_state": lifecycle,
        "access_commercial_state": access,
        "regulatory_state": "NO_CONTROLLING_RECORD",
        "deployment_state": deployment,
        "currentness_state": currentness,
        "evidence_state": ["COMPANY_REPRESENTATION"],
        "organization_relationship_refs": ["REL-DEV-1"],
        "projected_assertion_refs": ["AST-1"],
        "source_observation_refs": ["OBS-1"],
        "first_observed_at": "2026-09-20T00:00:00Z",
        "last_observed_at": "2026-09-24T00:00:00Z",
        "signal_or_sensing_modality": ["SENSE_SCALP_EEG"],
        "inference_capability": ["STATE_ATTENTION_VIGILANCE"],
        "intervention_output_capability": ["OUTPUT_NEUROFEEDBACK"],
        "form_factor": ["FORM_HEADBAND"],
        "deployment_context": ["CONTEXT_CONSUMER_WELLNESS"],
        "target_population": ["GENERAL_ADULT"],
        "technical_equivalence_cluster_id": None,
        "technical_equivalence_evidence_refs": [],
        "boundary": REGISTRY_BOUNDARY,
    }
    row["registry_row_id"] = registry_row_id(row)
    return row


def _run(
    captures: list[dict[str, object]],
    *,
    round_id: str = "R1",
    known_ids: set[str] | None = None,
    stop_state: str = "CONTINUE",
    stop_reason: str = "Further declared rounds remain.",
    frame_id: str = "F1",
) -> dict[str, object]:
    run: dict[str, object] = {
        "run_id": "",
        "frame_id": frame_id,
        "frame_version": FRAME_VERSION,
        "frame_register_version": FRAME_REGISTER_VERSION,
        "analysis_universe_id": DEFAULT_ANALYSIS_UNIVERSE_ID,
        "round_id": round_id,
        "query_or_seed_ids": [f"Q-{frame_id}"],
        "languages": ["en"],
        "jurisdictions": ["GLOBAL"],
        "analysis_jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "registry_projection_version": REGISTRY_PROJECTION_VERSION,
        "population_view_id": "A-P1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "known_identity_set_sha256": identity_set_digest(known_ids or set()),
        "capture_count": len(captures),
        "capture_ids": [str(capture["capture_id"]) for capture in captures],
        "stop_state": stop_state,
        "stop_reason": stop_reason,
        "boundary": DISCOVERY_BOUNDARY,
    }
    run["run_id"] = product_discovery_run_id(run)
    return run


def _summary(round_id: str, *, raw: int, marginal: float) -> dict[str, object]:
    return {
        "frame_id": "F1",
        "round_id": round_id,
        "raw_candidates": raw,
        "marginal_new_identity_yield": marginal,
    }


def test_capture_eligibility_is_derived_from_target_view_registry_qualification() -> None:
    frame = _frame()
    capture = _capture()
    row = _registry_row()

    assert derive_capture_estimation_eligibility(capture, frame, [row]) is True
    assert validate_authoritative_capture_estimation_eligibility(capture, frame, [row]) is True

    unresolved_row = _registry_row(currentness="UNRESOLVED", lifecycle="UNRESOLVED")
    outside_view = _capture(estimation_eligible=False)
    assert derive_capture_estimation_eligibility(outside_view, frame, [unresolved_row]) is False

    false_positive = _capture(estimation_eligible=True)
    with pytest.raises(ProductDiscoveryError, match="does not match frame and target-view"):
        validate_authoritative_capture_estimation_eligibility(false_positive, frame, [unresolved_row])


def test_capture_eligibility_rejects_universe_and_identity_mismatch() -> None:
    frame = _frame()
    capture = _capture()

    wrong_cutoff = _registry_row(knowledge_time_cutoff="2026-09-24T21:00:00Z")
    with pytest.raises(ProductDiscoveryError, match="lacks a compatible exact-universe"):
        derive_capture_estimation_eligibility(capture, frame, [wrong_cutoff])

    wrong_identity = _registry_row("PRD-B")
    with pytest.raises(ProductDiscoveryError, match="lacks a compatible exact-universe"):
        derive_capture_estimation_eligibility(capture, frame, [wrong_identity])


def test_capture_eligibility_preserves_frame_exclusion_and_a_p6_access_rule() -> None:
    excluded_frame = _frame("F7", "EXPERT_NOMINATION", capture_eligible=False)
    excluded_capture = _capture("PRD-A", frame_id="F7", estimation_eligible=False)
    assert (
        derive_capture_estimation_eligibility(
            excluded_capture,
            excluded_frame,
            [_registry_row()],
        )
        is False
    )

    a_p6_capture = _capture(population_view_id="A-P6", estimation_eligible=False)
    announced_without_access = _registry_row(
        lifecycle="ANNOUNCED",
        access="NOT_EXTERNALLY_OFFERED",
        deployment="NOT_APPLICABLE",
    )
    assert derive_capture_estimation_eligibility(a_p6_capture, _frame(), [announced_without_access]) is False


def test_capture_eligibility_allows_multiple_compatible_projections_for_same_offering() -> None:
    capture = _capture()
    primary = _registry_row()
    secondary = _registry_row(access="RESEARCH_USE_SOLD_OR_LICENSED")
    assert primary["registry_row_id"] != secondary["registry_row_id"]

    assert (
        validate_authoritative_capture_estimation_eligibility(
            capture,
            _frame(),
            [primary, secondary],
        )
        is True
    )


def test_run_known_identity_digest_is_recomputed_including_empty_set() -> None:
    capture = _capture()
    correct = _run([capture], known_ids={"PRD-KNOWN"})
    assert validate_run_known_identity_baseline(correct, {"PRD-KNOWN"}) == frozenset({"PRD-KNOWN"})

    with pytest.raises(ProductDiscoveryError, match="does not match the exact round-start"):
        validate_run_known_identity_baseline(correct, {"PRD-DIFFERENT"})

    empty = _run([capture], known_ids=set())
    assert validate_run_known_identity_baseline(empty, set()) == frozenset()


def test_authoritative_run_rejects_round_summary_from_different_known_set() -> None:
    capture = _capture()
    run = _run([capture], known_ids={"PRD-A"})
    wrong_summary = summarize_discovery_round([capture], known_identity_ids_before=set())

    with pytest.raises(ProductDiscoveryError, match="Declared round summary"):
        validate_authoritative_discovery_run(
            run,
            [capture],
            _frame(),
            registry_rows=[_registry_row()],
            known_identity_ids_before={"PRD-A"},
            declared_round_summary=wrong_summary,
            round_summaries=[wrong_summary],
            expected_completed_round_ids=["R1"],
        )


def test_stop_state_requires_complete_ordered_round_evidence() -> None:
    capture = _capture(round_id="R3")
    run = _run([capture], round_id="R3")
    frame = _frame()
    summaries = [
        _summary("R1", raw=30, marginal=0.20),
        _summary("R2", raw=30, marginal=0.04),
        _summary("R3", raw=30, marginal=0.03),
    ]

    assert (
        derive_authoritative_run_stop_state(
            run,
            frame,
            summaries,
            expected_completed_round_ids=["R1", "R2", "R3"],
            stop_evidence_ref="PACKET:ROUND-SUMMARIES",
        )
        == "SATURATION_UNDER_DECLARED_PROTOCOL"
    )

    with pytest.raises(ProductDiscoveryError, match="complete expected round-id sequence"):
        derive_authoritative_run_stop_state(
            run,
            frame,
            [summaries[0], summaries[2]],
            expected_completed_round_ids=["R1", "R2", "R3"],
            stop_evidence_ref="PACKET:ROUND-SUMMARIES",
        )


def test_stop_state_rejects_premature_and_unbound_bounded_exhaustion() -> None:
    capture = _capture(round_id="R2")
    run = _run([capture], round_id="R2")
    frame = _frame()
    summaries = [
        _summary("R1", raw=30, marginal=0.04),
        _summary("R2", raw=30, marginal=0.03),
    ]
    assert (
        derive_authoritative_run_stop_state(
            run,
            frame,
            summaries,
            expected_completed_round_ids=["R1", "R2"],
        )
        == "CONTINUE"
    )

    bounded_frame = _frame("F2", "REGULATORY", mode="BOUNDED_SOURCE_EXHAUSTION")
    bounded_capture = _capture("PRD-A", frame_id="F2")
    bounded_run = _run([bounded_capture], frame_id="F2")
    with pytest.raises(ProductDiscoveryError, match="source exhaustion requires an explicit evidence binding"):
        derive_authoritative_run_stop_state(
            bounded_run,
            bounded_frame,
            [],
            source_exhausted=True,
        )


def test_authoritative_run_rejects_stored_stop_state_different_from_derived_state() -> None:
    captures = [_capture(round_id="R3")]
    run = _run(
        captures,
        round_id="R3",
        stop_state="SATURATION_UNDER_DECLARED_PROTOCOL",
        stop_reason="Claimed saturation.",
    )
    current_summary = summarize_discovery_round(captures, known_identity_ids_before=set())
    prior = [
        {
            **current_summary,
            "round_id": "R1",
            "raw_candidates": 30,
            "marginal_new_identity_yield": 0.20,
        },
        {
            **current_summary,
            "round_id": "R2",
            "raw_candidates": 5,
            "marginal_new_identity_yield": 0.01,
        },
    ]
    all_summaries = prior + [current_summary]

    with pytest.raises(ProductDiscoveryError, match="stop_state does not match"):
        validate_authoritative_discovery_run(
            run,
            captures,
            _frame(),
            registry_rows=[_registry_row()],
            known_identity_ids_before=set(),
            declared_round_summary=current_summary,
            round_summaries=all_summaries,
            expected_completed_round_ids=["R1", "R2", "R3"],
        )
