from __future__ import annotations

import pytest

from neuroai_workbench import product_discovery_frames as pdf
from neuroai_workbench import product_registry as pr

INITIAL_IDS = {
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-EMOTIV-EPOC-X",
    "PRD-FLOW-FL-100",
    "PRD-MODIUS-SPERO",
    "PRD-SYNCHRON-STENTRODE",
}


def _universe() -> dict[str, object]:
    return pdf.load_default_analysis_universe()


def _frame(
    frame_id: str = "F1",
    frame_class: str = "FIRST_PARTY",
    *,
    capture_eligible: bool = True,
    mode: str = "MARGINAL_YIELD",
) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "frame_version": pdf.FRAME_VERSION,
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
        "boundary": pdf.DISCOVERY_BOUNDARY,
    }


def _capture(
    offering_id: str = "PRD-NEXTSENSE-SMARTBUDS",
    *,
    frame_id: str = "F1",
    round_id: str = "R1",
    population_view_id: str = "A-P1",
    outcome: str = "INCLUDE_RESOLVED",
    estimation_eligible: bool = True,
    analysis_universe_id_value: str = pdf.DEFAULT_ANALYSIS_UNIVERSE_ID,
) -> dict[str, object]:
    capture: dict[str, object] = {
        "capture_id": "",
        "frame_id": frame_id,
        "frame_version": pdf.FRAME_VERSION,
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
        "registry_projection_version": pr.REGISTRY_PROJECTION_VERSION,
        "frame_register_version": pdf.FRAME_REGISTER_VERSION,
        "analysis_universe_id": analysis_universe_id_value,
        "population_view_id": population_view_id,
        "analysis_jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "world_time_alignment": "EVIDENCE_SUPPORTS_AT_OR_BEFORE_CUTOFF",
        "world_time_support_ref": None,
        "boundary": pdf.DISCOVERY_BOUNDARY,
    }
    capture["capture_id"] = pdf.product_capture_id(capture)
    return capture


def _registry_row(
    offering_id: str = "PRD-NEXTSENSE-SMARTBUDS",
    *,
    currentness: str = "CURRENT",
    lifecycle: str = "RELEASED",
    access: str = "COMMERCIAL_DIRECT",
    deployment: str = "DOCUMENTED_CONSUMER_ACCESS",
    knowledge_time_cutoff: str = "2026-10-24T23:59:59Z",
    configuration_system_id: str | None = None,
    configuration_coverage_state: str = "NOT_APPLICABLE",
) -> dict[str, object]:
    row: dict[str, object] = {
        "registry_row_id": "",
        "registry_projection_version": pr.REGISTRY_PROJECTION_VERSION,
        "boundary_contract_id": pr.BOUNDARY_CONTRACT_ID,
        "boundary_contract_semantic_blob": pr.BOUNDARY_CONTRACT_SEMANTIC_BLOB,
        "reference_standard_id": pr.REFERENCE_STANDARD_ID,
        "reference_standard_version": pr.REFERENCE_STANDARD_VERSION,
        "reference_standard_validation_state": pr.REFERENCE_STANDARD_VALIDATION_STATE,
        "population_view_policy_id": pr.POPULATION_VIEW_POLICY_ID,
        "currentness_policy_id": pr.CURRENTNESS_POLICY_ID,
        "canonical_entity_id": offering_id,
        "canonical_entity_type": "PRODUCT",
        "identity_level": "OFFERING",
        "product_family_id": None,
        "product_offering_id": offering_id,
        "configuration_system_id": configuration_system_id,
        "configuration_coverage_state": configuration_coverage_state,
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
        "source_observation_refs": [f"OBS-{offering_id}"],
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
        "boundary": pr.REGISTRY_BOUNDARY,
    }
    row["registry_row_id"] = pr.registry_row_id(row)
    return row


def _initial_registry_rows() -> list[dict[str, object]]:
    return [_registry_row(offering_id) for offering_id in sorted(INITIAL_IDS)]


def _run(
    captures: list[dict[str, object]],
    *,
    round_id: str = "R1",
    known_ids: set[str] | None = None,
    stop_state: str = "CONTINUE",
    stop_reason: str = "Further declared rounds remain.",
    frame_id: str = "F1",
    analysis_universe_id_value: str = pdf.DEFAULT_ANALYSIS_UNIVERSE_ID,
) -> dict[str, object]:
    run: dict[str, object] = {
        "run_id": "",
        "frame_id": frame_id,
        "frame_version": pdf.FRAME_VERSION,
        "frame_register_version": pdf.FRAME_REGISTER_VERSION,
        "analysis_universe_id": analysis_universe_id_value,
        "round_id": round_id,
        "query_or_seed_ids": [f"Q-{frame_id}"],
        "languages": ["en"],
        "jurisdictions": ["GLOBAL"],
        "analysis_jurisdiction_scope": "GLOBAL_PROTOCOL_SCOPE",
        "language_scope_id": "EN_PLUS_PRIORITY_NATIVE_v1",
        "registry_projection_version": pr.REGISTRY_PROJECTION_VERSION,
        "population_view_id": "A-P1",
        "world_time_cutoff": "2026-09-24",
        "knowledge_time_cutoff": "2026-10-24T23:59:59Z",
        "known_identity_set_sha256": pdf.identity_set_digest(known_ids or set()),
        "capture_count": len(captures),
        "capture_ids": [str(capture["capture_id"]) for capture in captures],
        "stop_state": stop_state,
        "stop_reason": stop_reason,
        "boundary": pdf.DISCOVERY_BOUNDARY,
    }
    run["run_id"] = pdf.product_discovery_run_id(run)
    return run


def _summary(round_id: str, *, raw: int, marginal: float, frame_id: str = "F1") -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "round_id": round_id,
        "raw_candidates": raw,
        "marginal_new_identity_yield": marginal,
    }


def _stop_evidence(
    run: dict[str, object],
    summaries: list[dict[str, object]],
    *,
    condition: str = "MARGINAL_YIELD_SEQUENCE",
    artifact_sha256: str = "a" * 64,
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "evidence_id": "",
        "evidence_version": pdf.AUTHORITATIVE_STOP_EVIDENCE_VERSION,
        "analysis_universe_id": run["analysis_universe_id"],
        "frame_id": run["frame_id"],
        "through_round_id": run["round_id"],
        "completed_round_ids": [str(summary["round_id"]) for summary in summaries],
        "round_summaries_sha256": pdf.round_summary_sequence_sha256(summaries),
        "terminal_condition": condition,
        "supporting_artifacts": [{"ref": "PACKET:TEST", "sha256": artifact_sha256}],
    }
    evidence["evidence_id"] = pdf.authoritative_stop_evidence_id(evidence)
    return evidence


def test_capture_eligibility_is_derived_from_exact_universe_and_target_view() -> None:
    universe = _universe()
    frame = _frame()
    capture = _capture()
    row = _registry_row()

    assert pdf.derive_capture_estimation_eligibility(capture, frame, [row], universe) is True
    assert pdf.validate_authoritative_capture_estimation_eligibility(capture, frame, [row], universe) is True

    unresolved_row = _registry_row(currentness="UNRESOLVED", lifecycle="UNRESOLVED")
    outside_view = _capture(estimation_eligible=False)
    assert pdf.derive_capture_estimation_eligibility(outside_view, frame, [unresolved_row], universe) is False

    false_positive = _capture(estimation_eligible=True)
    with pytest.raises(pdf.ProductDiscoveryError, match="does not match frame and target-view"):
        pdf.validate_authoritative_capture_estimation_eligibility(false_positive, frame, [unresolved_row], universe)


def test_capture_eligibility_rejects_registry_universe_and_identity_mismatch() -> None:
    universe = _universe()
    frame = _frame()
    capture = _capture()

    wrong_cutoff = _registry_row(knowledge_time_cutoff="2026-09-24T21:00:00Z")
    with pytest.raises(pdf.ProductDiscoveryError, match="exact frozen A2 analysis universe"):
        pdf.derive_capture_estimation_eligibility(capture, frame, [wrong_cutoff], universe)

    wrong_identity = _registry_row("PRD-B")
    with pytest.raises(pdf.ProductDiscoveryError, match="lacks a compatible exact-universe"):
        pdf.derive_capture_estimation_eligibility(capture, frame, [wrong_identity], universe)


def test_exact_frozen_analysis_universe_identity_is_required() -> None:
    fake_universe = dict(_universe())
    fake_universe["boundary"] = str(fake_universe["boundary"]) + " altered"
    fake_universe["analysis_universe_id"] = pdf.analysis_universe_id(fake_universe)

    with pytest.raises(pdf.ProductDiscoveryError, match="exact frozen Release-A A2 universe"):
        pdf.derive_capture_estimation_eligibility(
            _capture(),
            _frame(),
            [_registry_row()],
            fake_universe,
        )


def test_capture_eligibility_preserves_frame_exclusion_and_a_p6_access_rule() -> None:
    universe = _universe()
    excluded_frame = _frame("F7", "EXPERT_NOMINATION", capture_eligible=False)
    excluded_capture = _capture("PRD-NEXTSENSE-SMARTBUDS", frame_id="F7", estimation_eligible=False)
    assert (
        pdf.derive_capture_estimation_eligibility(
            excluded_capture,
            excluded_frame,
            [_registry_row()],
            universe,
        )
        is False
    )

    # The frozen Release-A A2 universe targets A-P1, so an A-P6 capture is
    # universe-incompatible and must fail closed rather than being evaluated
    # under a different target view inside this authoritative path.
    a_p6_capture = _capture(population_view_id="A-P6", estimation_eligible=False)
    announced_without_access = _registry_row(
        lifecycle="ANNOUNCED",
        access="NOT_EXTERNALLY_OFFERED",
        deployment="NOT_APPLICABLE",
    )
    with pytest.raises(pdf.ProductDiscoveryError, match="population_view_id does not match"):
        pdf.derive_capture_estimation_eligibility(
            a_p6_capture,
            _frame(),
            [announced_without_access],
            universe,
        )

    # Preserve the #342 target-view regression itself at the Product Registry
    # predicate layer: pre-delivery/no-access does not qualify for A-P6.
    assert pr.population_view_identity_ids([announced_without_access], "A-P6") == set()


def test_capture_eligibility_allows_legitimate_multiple_compatible_projections() -> None:
    universe = _universe()
    capture = _capture()
    primary = _registry_row()
    configured = _registry_row(
        configuration_system_id="SYS-NEXTSENSE-CONFIG-A",
        configuration_coverage_state="RESOLVED",
    )
    assert primary["registry_row_id"] != configured["registry_row_id"]

    assert (
        pdf.validate_authoritative_capture_estimation_eligibility(
            capture,
            _frame(),
            [primary, configured],
            universe,
        )
        is True
    )


def test_round_start_known_identity_digest_is_derived_from_registry_snapshot() -> None:
    universe = _universe()
    rows = _initial_registry_rows()
    assert pdf.derive_round_start_known_identity_ids(rows, universe) == frozenset(INITIAL_IDS)

    run = _run([_capture()], known_ids=INITIAL_IDS)
    assert pdf.validate_run_known_identity_baseline(run, rows, universe) == frozenset(INITIAL_IDS)

    incomplete_rows = rows[:-1]
    with pytest.raises(pdf.ProductDiscoveryError, match="initial known-identity authority"):
        pdf.validate_run_known_identity_baseline(run, incomplete_rows, universe)


def test_round_start_known_identity_empty_set_is_deterministic_for_later_round() -> None:
    universe = _universe()
    run = _run([_capture(round_id="R2")], round_id="R2", known_ids=set())
    assert pdf.validate_run_known_identity_baseline(run, [], universe) == frozenset()


def test_authoritative_run_rejects_round_summary_from_different_known_set() -> None:
    universe = _universe()
    rows = _initial_registry_rows()
    capture = _capture()
    run = _run([capture], known_ids=INITIAL_IDS)
    wrong_summary = pdf.summarize_discovery_round([capture], known_identity_ids_before=set())
    evidence = _stop_evidence(run, [wrong_summary])

    with pytest.raises(pdf.ProductDiscoveryError, match="Declared round summary"):
        pdf.validate_authoritative_discovery_run(
            run,
            [capture],
            _frame(),
            analysis_universe=universe,
            registry_rows=rows,
            round_start_registry_rows=rows,
            declared_round_summary=wrong_summary,
            round_summaries=[wrong_summary],
            stop_evidence=evidence,
        )


def test_authoritative_run_happy_path_binds_all_four_control_layers() -> None:
    universe = _universe()
    rows = _initial_registry_rows()
    capture = _capture()
    run = _run([capture], known_ids=INITIAL_IDS)
    summary = pdf.summarize_discovery_round([capture], known_identity_ids_before=INITIAL_IDS)
    evidence = _stop_evidence(run, [summary])

    assert (
        pdf.validate_authoritative_discovery_run(
            run,
            [capture],
            _frame(),
            analysis_universe=universe,
            registry_rows=rows,
            round_start_registry_rows=rows,
            declared_round_summary=summary,
            round_summaries=[summary],
            stop_evidence=evidence,
        )
        == summary
    )


def test_stop_state_requires_complete_contiguous_digest_bound_round_evidence() -> None:
    universe = _universe()
    run = _run([_capture(round_id="R3")], round_id="R3")
    frame = _frame()
    summaries = [
        _summary("R1", raw=30, marginal=0.20),
        _summary("R2", raw=30, marginal=0.04),
        _summary("R3", raw=30, marginal=0.03),
    ]
    evidence = _stop_evidence(run, summaries)

    assert pdf.derive_authoritative_run_stop_state(run, frame, summaries, evidence, universe) == (
        "SATURATION_UNDER_DECLARED_PROTOCOL"
    )

    omitted = [summaries[0], summaries[2]]
    omitted_evidence = _stop_evidence(run, omitted)
    with pytest.raises(pdf.ProductDiscoveryError, match="complete contiguous R1..Rn"):
        pdf.derive_authoritative_run_stop_state(run, frame, omitted, omitted_evidence, universe)


def test_stop_evidence_rejects_wrong_frame_digest_and_artifact_digest() -> None:
    universe = _universe()
    run = _run([_capture()], round_id="R1")
    frame = _frame()
    summaries = [_summary("R1", raw=30, marginal=0.20)]

    wrong_frame = [_summary("R1", raw=30, marginal=0.20, frame_id="F4")]
    evidence = _stop_evidence(run, wrong_frame)
    with pytest.raises(pdf.ProductDiscoveryError, match="frame_id does not match"):
        pdf.derive_authoritative_run_stop_state(run, frame, wrong_frame, evidence, universe)

    evidence = _stop_evidence(run, summaries)
    evidence["round_summaries_sha256"] = "b" * 64
    evidence["evidence_id"] = pdf.authoritative_stop_evidence_id(evidence)
    with pytest.raises(pdf.ProductDiscoveryError, match="round-summary digest mismatch"):
        pdf.derive_authoritative_run_stop_state(run, frame, summaries, evidence, universe)

    evidence = _stop_evidence(run, summaries, artifact_sha256="NOT-A-DIGEST")
    with pytest.raises(pdf.ProductDiscoveryError, match="64 lowercase hex chars"):
        pdf.derive_authoritative_run_stop_state(run, frame, summaries, evidence, universe)


def test_bounded_source_exhaustion_requires_typed_digest_bound_evidence() -> None:
    universe = _universe()
    frame = _frame("F2", "REGULATORY", mode="BOUNDED_SOURCE_EXHAUSTION")
    capture = _capture(frame_id="F2")
    run = _run(
        [capture],
        frame_id="F2",
        known_ids=set(),
        stop_state="BOUNDED_FRAME_EXHAUSTED",
        stop_reason="Declared provider universe exhausted.",
    )
    summary = pdf.summarize_discovery_round([capture], known_identity_ids_before=set())
    evidence = _stop_evidence(run, [summary], condition="SOURCE_EXHAUSTED")

    assert (
        pdf.derive_authoritative_run_stop_state(run, frame, [summary], evidence, universe) == "BOUNDED_FRAME_EXHAUSTED"
    )

    evidence["supporting_artifacts"] = []
    evidence["evidence_id"] = pdf.authoritative_stop_evidence_id(evidence)
    with pytest.raises(pdf.ProductDiscoveryError, match="digest-bound supporting_artifacts"):
        pdf.derive_authoritative_run_stop_state(run, frame, [summary], evidence, universe)


def test_stop_evidence_rejects_terminal_condition_incompatible_with_frame_mode() -> None:
    universe = _universe()
    run = _run([_capture()])
    summaries = [_summary("R1", raw=30, marginal=0.20)]
    evidence = _stop_evidence(run, summaries, condition="SOURCE_EXHAUSTED")

    with pytest.raises(pdf.ProductDiscoveryError, match="bounded-source frame"):
        pdf.derive_authoritative_run_stop_state(run, _frame(), summaries, evidence, universe)


def test_authoritative_run_rejects_stored_stop_state_different_from_derived_state() -> None:
    universe = _universe()
    rows = _initial_registry_rows()
    captures = [_capture(round_id="R3")]
    run = _run(
        captures,
        round_id="R3",
        known_ids=INITIAL_IDS,
        stop_state="SATURATION_UNDER_DECLARED_PROTOCOL",
        stop_reason="Claimed saturation.",
    )
    current_summary = pdf.summarize_discovery_round(captures, known_identity_ids_before=INITIAL_IDS)
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
    evidence = _stop_evidence(run, all_summaries)

    with pytest.raises(pdf.ProductDiscoveryError, match="stop_state does not match"):
        pdf.validate_authoritative_discovery_run(
            run,
            captures,
            _frame(),
            analysis_universe=universe,
            registry_rows=rows,
            round_start_registry_rows=rows,
            declared_round_summary=current_summary,
            round_summaries=all_summaries,
            stop_evidence=evidence,
        )
