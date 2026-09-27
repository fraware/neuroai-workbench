from __future__ import annotations

import copy

import pytest

import neuroai_workbench.release_a_r1_decision_resolution as dr


def _reseal(value: dict[str, object], field: str) -> None:
    value[field] = dr.artifact_sha256(value, digest_field=field)


def _historical_evidence(
    *,
    evidence_ref: str = "EV-1",
    propositions: list[str] | None = None,
    role: str = "DIRECT_PRE_CUTOFF_STATE",
    world_ref: str | None = "2026-09-24",
    knowledge_observed_at: str = "2026-09-27T09:00:00Z",
    supports_historical: bool = True,
) -> dict[str, object]:
    return {
        "evidence_ref": evidence_ref,
        "source_locator": "https://example.test/evidence",
        "knowledge_observed_at": knowledge_observed_at,
        "evidence_role": role,
        "supported_propositions": propositions or ["SCOPE"],
        "supports_state_at_or_before_world_cutoff": supports_historical,
        "supported_world_time_ref": world_ref,
        "sha256": "1" * 64,
    }


def _base_record(
    work_item_id: str,
    *,
    disposition: str = "UNRESOLVED_CARDINALITY_UNPROVEN",
    adjudicator_state: str = "MACHINE_PROVISIONAL",
    adjudicator_id: str | None = None,
    evidence: list[dict[str, object]] | None = None,
    existing_canonical_offering_id: str | None = None,
    one_object_upper_bound: bool = False,
    max_incremental_offering_contribution: int | None = None,
    proposed_currentness_state: str | None = None,
    proposed_lifecycle_state: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "adjudication_id": "",
        "work_item_id": work_item_id,
        "disposition": disposition,
        "adjudicator_state": adjudicator_state,
        "adjudicator_id": adjudicator_id,
        "evidence": evidence or [_historical_evidence()],
        "existing_canonical_offering_id": existing_canonical_offering_id,
        "one_object_upper_bound": one_object_upper_bound,
        "max_incremental_offering_contribution": max_incremental_offering_contribution,
        "proposed_currentness_state": proposed_currentness_state,
        "proposed_lifecycle_state": proposed_lifecycle_state,
    }
    record["adjudication_id"] = dr.adjudication_record_id(record)
    return record


def _candidate_item(
    worklist: dict[str, object],
    *,
    source_barrier: bool | None = None,
) -> dict[str, object]:
    for item in worklist["work_items"]:
        if item["work_item_type"] != "CANDIDATE_CLUSTER_REVIEW":
            continue
        if source_barrier is None or item["source_or_abstention_barrier"] is source_barrier:
            return item
    raise AssertionError("candidate work item not found")


def _temporal_item(worklist: dict[str, object], canonical_id: str = "PRD-FLOW-FL-100") -> dict[str, object]:
    for item in worklist["work_items"]:
        if item.get("canonical_offering_id") == canonical_id and item["work_item_type"] == "A_P1_TEMPORAL_STATE_REVIEW":
            return item
    raise AssertionError("temporal work item not found")


def test_default_rule_and_worklist_reconstruct_exactly() -> None:
    rule = dr.load_decision_resolution_rule()
    worklist = dr.load_decision_resolution_worklist()

    assert rule["rule_sha256"] == dr.RULE_SHA256
    assert worklist["worklist_sha256"] == dr.WORKLIST_SHA256
    assert worklist["accounting"] == {
        "candidate_cluster_work_item_count": 268,
        "temporal_state_work_item_count": 2,
        "total_work_item_count": 270,
        "marginal_yield_r2_r3_cluster_count": 234,
        "a3_sensitive_cluster_count": 52,
        "a4_sensitive_cluster_count": 63,
        "marginal_and_a3_overlap_count": 39,
        "marginal_and_a4_overlap_count": 42,
        "a3_and_a4_overlap_count": 0,
        "predecessor_cardinality_unproven_count": 91,
        "predecessor_unbounded_barrier_count": 177,
        "predecessor_one_object_upper_bound_count": 0,
    }

    candidate_items = [item for item in worklist["work_items"] if item["work_item_type"] == "CANDIDATE_CLUSTER_REVIEW"]
    assert len(candidate_items) == 268
    assert len({item["candidate_cluster_id"] for item in candidate_items}) == 268
    assert all(item["capture_ids"] for item in candidate_items)
    assert all(item["source_observation_refs"] for item in candidate_items)

    temporal_ids = {
        item["canonical_offering_id"]
        for item in worklist["work_items"]
        if item["work_item_type"] == "A_P1_TEMPORAL_STATE_REVIEW"
    }
    assert temporal_ids == {"PRD-FLOW-FL-100", "PRD-MODIUS-SPERO"}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_workbench_main_commit", "0" * 40, "source Workbench commit drift"),
        ("analysis_universe_id", "RAU-WRONG", "analysis universe drift"),
        ("world_time_cutoff", "2026-09-25", "world-time cutoff drift"),
        ("knowledge_time_cutoff", "2026-10-25T00:00:00Z", "knowledge-time cutoff drift"),
        ("population_view_id", "A-P6", "population view drift"),
        ("r1_2_candidate_resolution_manifest_sha256", "0" * 64, "R1.2 manifest binding drift"),
        ("r1_2_candidate_cluster_ledger_sha256", "0" * 64, "R1.2 cluster binding drift"),
        ("r1_3_resolution_completeness_rule_sha256", "0" * 64, "R1.3 rule binding drift"),
        ("r1_3_resolution_completeness_checkpoint_sha256", "0" * 64, "R1.3 checkpoint binding drift"),
    ],
)
def test_rule_rejects_upstream_semantic_drift(
    field: str,
    value: object,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = dr.load_decision_resolution_rule()
    changed = copy.deepcopy(rule)
    changed[field] = value
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(dr, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(dr.ProductDiscoveryError, match=message):
        dr.validate_decision_resolution_rule(changed)


def test_rule_rejects_selection_and_authority_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = dr.load_decision_resolution_rule()

    mutations = [
        (
            "marginal-yield frame selection drift",
            lambda x: x["selection_contract"].update({"marginal_yield_frames": ["F1"]}),
        ),
        (
            "marginal-yield round selection drift",
            lambda x: x["selection_contract"].update({"marginal_yield_rounds": ["R3"]}),
        ),
        (
            "decision-relevant selection predicate drift",
            lambda x: x["selection_contract"].update({"include_if_any": ["A3_CAPABILITY_INCREMENT"]}),
        ),
        (
            "temporal-review offering set drift",
            lambda x: x["selection_contract"].update({"temporal_state_reviews": ["PRD-FLOW-FL-100"]}),
        ),
        (
            "preserve exact cross-frame",
            lambda x: x["selection_contract"].update({"preserve_exact_cross_frame_cluster_identity": False}),
        ),
        (
            "cannot substitute probability sampling",
            lambda x: x["selection_contract"].update({"probability_sampling_substitution_permitted": True}),
        ),
        ("adjudication disposition set drift", lambda x: x.update({"adjudication_dispositions": ["TERMINAL_EXCLUDE"]})),
        ("adjudicator-state set drift", lambda x: x.update({"adjudicator_states": ["HUMAN_REVIEWED"]})),
        ("evidence-role set drift", lambda x: x.update({"evidence_roles": ["DIRECT_PRE_CUTOFF_STATE"]})),
        ("supported-proposition set drift", lambda x: x.update({"supported_propositions": ["SCOPE"]})),
        (
            "must not allocate canonical",
            lambda x: x["identity_authority"].update({"worklist_may_allocate_canonical_product_identity": True}),
        ),
        (
            "must require separate identity authority",
            lambda x: x["identity_authority"].update(
                {"new_identity_disposition_requires_separate_identity_authority_successor": False}
            ),
        ),
        (
            "must require cardinality evidence",
            lambda x: x["cardinality_rule"].update(
                {"one_object_upper_bound_requires_cardinality_specific_evidence": False}
            ),
        ),
        (
            "contribution must equal one",
            lambda x: x["cardinality_rule"].update({"one_object_upper_bound_max_incremental_offering_contribution": 0}),
        ),
        (
            "source barriers must fail closed",
            lambda x: x["cardinality_rule"].update(
                {"source_or_abstention_barrier_remains_unbounded_without_source_specific_finite_bound": False}
            ),
        ),
        (
            "temporal-state target set drift",
            lambda x: x["temporal_state_rule"].update({"target_offerings": ["PRD-FLOW-FL-100"]}),
        ),
        (
            "qualifying currentness state drift",
            lambda x: x["temporal_state_rule"].update({"qualifying_currentness_state": "UNRESOLVED"}),
        ),
        (
            "qualifying lifecycle-state set drift",
            lambda x: x["temporal_state_rule"].update({"qualifying_lifecycle_states": ["RELEASED"]}),
        ),
        (
            "must fail closed on missing support",
            lambda x: x["temporal_state_rule"].update(
                {"preserve_nonqualification_without_admissible_currentness_and_lifecycle_support": False}
            ),
        ),
        (
            "checkpoint-only",
            lambda x: x["finality"].update({"checkpoint_only_until_knowledge_window_disposition": False}),
        ),
        ("final R1.3 rebind", lambda x: x["finality"].update({"final_r1_3_rebind_required": False})),
        ("forbidden authority enabled", lambda x: x["finality"].update({"release_a_r1_passed": True})),
    ]

    for message, mutate in mutations:
        changed = copy.deepcopy(rule)
        mutate(changed)
        _reseal(changed, "rule_sha256")
        monkeypatch.setattr(dr, "RULE_SHA256", changed["rule_sha256"])
        with pytest.raises(dr.ProductDiscoveryError, match=message):
            dr.validate_decision_resolution_rule(changed)

    monkeypatch.setattr(dr, "RULE_SHA256", rule["rule_sha256"])


def test_rule_rejects_integrity_and_status_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = dr.load_decision_resolution_rule()

    broken = copy.deepcopy(rule)
    broken["status"] = "DRAFT"
    with pytest.raises(dr.ProductDiscoveryError, match="digest mismatch"):
        dr.validate_decision_resolution_rule(broken)

    changed = copy.deepcopy(rule)
    changed["status"] = "DRAFT"
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(dr, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(dr.ProductDiscoveryError, match="must be FROZEN"):
        dr.validate_decision_resolution_rule(changed)


def test_worklist_rejects_integrity_reconstruction_and_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    worklist = dr.load_decision_resolution_worklist()

    broken = copy.deepcopy(worklist)
    broken["accounting"]["total_work_item_count"] = 269
    with pytest.raises(dr.ProductDiscoveryError, match="digest mismatch"):
        dr.validate_decision_resolution_worklist(broken)

    changed = copy.deepcopy(worklist)
    changed["status"] = "CHANGED"
    _reseal(changed, "worklist_sha256")
    monkeypatch.setattr(dr, "WORKLIST_SHA256", changed["worklist_sha256"])
    with pytest.raises(dr.ProductDiscoveryError, match="must remain pre-execution"):
        dr.validate_decision_resolution_worklist(changed)

    changed = copy.deepcopy(worklist)
    changed["execution_state"] = "EXECUTED"
    _reseal(changed, "worklist_sha256")
    monkeypatch.setattr(dr, "WORKLIST_SHA256", changed["worklist_sha256"])
    with pytest.raises(dr.ProductDiscoveryError, match="cannot contain executed"):
        dr.validate_decision_resolution_worklist(changed)

    changed = copy.deepcopy(worklist)
    changed["work_items"][0]["selection_reasons"] = []
    _reseal(changed, "worklist_sha256")
    monkeypatch.setattr(dr, "WORKLIST_SHA256", changed["worklist_sha256"])
    with pytest.raises(dr.ProductDiscoveryError, match="does not reproduce"):
        dr.validate_decision_resolution_worklist(changed)

    monkeypatch.setattr(dr, "WORKLIST_SHA256", worklist["worklist_sha256"])


def test_machine_provisional_unresolved_adjudication_is_valid() -> None:
    worklist = dr.load_decision_resolution_worklist()
    item = _candidate_item(worklist, source_barrier=False)
    record = _base_record(item["work_item_id"])
    dr.validate_resolution_adjudication(record, worklist=worklist)


def test_adjudication_schema_id_work_item_and_reviewer_guards() -> None:
    worklist = dr.load_decision_resolution_worklist()
    item = _candidate_item(worklist, source_barrier=False)

    record = _base_record(item["work_item_id"])
    record["unexpected"] = True
    record["adjudication_id"] = dr.adjudication_record_id(record)
    with pytest.raises(dr.ProductDiscoveryError, match="schema validation"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(item["work_item_id"])
    record["adjudication_id"] = "R1ADJ-" + "0" * 64
    with pytest.raises(dr.ProductDiscoveryError, match="does not match deterministic"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record("R1WI-NOT-FROZEN")
    with pytest.raises(dr.ProductDiscoveryError, match="outside the frozen worklist"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(item["work_item_id"], adjudicator_state="MACHINE_PROVISIONAL", adjudicator_id="agent")
    with pytest.raises(dr.ProductDiscoveryError, match="must keep adjudicator_id null"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_EXCLUDE",
        adjudicator_state="MACHINE_PROVISIONAL",
        evidence=[_historical_evidence(propositions=["SCOPE"])],
    )
    with pytest.raises(dr.ProductDiscoveryError, match="requires human review"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_EXCLUDE",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id=None,
        evidence=[_historical_evidence(propositions=["SCOPE"])],
    )
    with pytest.raises(dr.ProductDiscoveryError, match="requires adjudicator_id"):
        dr.validate_resolution_adjudication(record, worklist=worklist)


def test_evidence_temporal_and_integrity_guards() -> None:
    worklist = dr.load_decision_resolution_worklist()
    item = _candidate_item(worklist, source_barrier=False)

    duplicate = _historical_evidence(evidence_ref="EV-X")
    record = _base_record(item["work_item_id"], evidence=[duplicate, copy.deepcopy(duplicate)])
    with pytest.raises(dr.ProductDiscoveryError, match="must be unique"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(
        item["work_item_id"],
        evidence=[_historical_evidence(knowledge_observed_at="2026-10-25T00:00:00Z")],
    )
    with pytest.raises(dr.ProductDiscoveryError, match="exceeds the frozen knowledge-time cutoff"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(
        item["work_item_id"],
        evidence=[
            _historical_evidence(
                role="POST_CUTOFF_CURRENT_STATE_ONLY",
                supports_historical=True,
                world_ref="2026-09-24",
            )
        ],
    )
    with pytest.raises(dr.ProductDiscoveryError, match="cannot be back-projected"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(
        item["work_item_id"],
        evidence=[
            _historical_evidence(
                role="POST_CUTOFF_CURRENT_STATE_ONLY",
                supports_historical=False,
                world_ref=None,
                propositions=["CURRENTNESS"],
            )
        ],
    )
    dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(
        item["work_item_id"],
        evidence=[_historical_evidence(supports_historical=False, world_ref=None)],
    )
    with pytest.raises(dr.ProductDiscoveryError, match="must bind a supported world-time reference"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(item["work_item_id"], evidence=[_historical_evidence(world_ref="2026-09-25")])
    with pytest.raises(dr.ProductDiscoveryError, match="only after the world-time cutoff"):
        dr.validate_resolution_adjudication(record, worklist=worklist)

    record = _base_record(
        item["work_item_id"],
        evidence=[_historical_evidence(knowledge_observed_at="2026-09-27 09:00:00")],
    )
    with pytest.raises(dr.ProductDiscoveryError, match="must include a timezone"):
        dr.validate_resolution_adjudication(record, worklist=worklist)


def test_existing_and_pending_identity_inclusion_guards() -> None:
    worklist = dr.load_decision_resolution_worklist()
    item = _candidate_item(worklist, source_barrier=False)
    evidence = [_historical_evidence(propositions=["IDENTITY", "SCOPE"])]

    existing = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_INCLUDE_EXISTING_CANONICAL",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=evidence,
        existing_canonical_offering_id="PRD-SYNCHRON-STENTRODE",
    )
    dr.validate_resolution_adjudication(existing, worklist=worklist)

    unknown = copy.deepcopy(existing)
    unknown["existing_canonical_offering_id"] = "PRD-INVENTED"
    unknown["adjudication_id"] = dr.adjudication_record_id(unknown)
    with pytest.raises(dr.ProductDiscoveryError, match="cannot invent"):
        dr.validate_resolution_adjudication(unknown, worklist=worklist)

    missing_support = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_INCLUDE_EXISTING_CANONICAL",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=[_historical_evidence(propositions=["SCOPE"])],
        existing_canonical_offering_id="PRD-SYNCHRON-STENTRODE",
    )
    with pytest.raises(dr.ProductDiscoveryError, match="identity and scope"):
        dr.validate_resolution_adjudication(missing_support, worklist=worklist)

    pending = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_INCLUDE_NEW_CANONICAL_PENDING_IDENTITY_AUTHORITY",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=evidence,
    )
    dr.validate_resolution_adjudication(pending, worklist=worklist)

    pending_with_existing = copy.deepcopy(pending)
    pending_with_existing["existing_canonical_offering_id"] = "PRD-SYNCHRON-STENTRODE"
    pending_with_existing["adjudication_id"] = dr.adjudication_record_id(pending_with_existing)
    with pytest.raises(dr.ProductDiscoveryError, match="must not populate existing"):
        dr.validate_resolution_adjudication(pending_with_existing, worklist=worklist)


def test_terminal_exclusion_and_unresolved_disposition_guards() -> None:
    worklist = dr.load_decision_resolution_worklist()
    item = _candidate_item(worklist, source_barrier=False)

    excluded = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_EXCLUDE",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=[_historical_evidence(propositions=["SCOPE"])],
    )
    dr.validate_resolution_adjudication(excluded, worklist=worklist)

    excluded_existing = copy.deepcopy(excluded)
    excluded_existing["existing_canonical_offering_id"] = "PRD-SYNCHRON-STENTRODE"
    excluded_existing["adjudication_id"] = dr.adjudication_record_id(excluded_existing)
    with pytest.raises(dr.ProductDiscoveryError, match="must not allocate"):
        dr.validate_resolution_adjudication(excluded_existing, worklist=worklist)

    no_scope = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_EXCLUDE",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=[_historical_evidence(propositions=["IDENTITY"])],
    )
    with pytest.raises(dr.ProductDiscoveryError, match="requires historical scope"):
        dr.validate_resolution_adjudication(no_scope, worklist=worklist)

    unresolved_existing = _base_record(
        item["work_item_id"],
        existing_canonical_offering_id="PRD-SYNCHRON-STENTRODE",
    )
    with pytest.raises(dr.ProductDiscoveryError, match="cannot allocate canonical identity"):
        dr.validate_resolution_adjudication(unresolved_existing, worklist=worklist)

    unresolved_bound = _base_record(
        item["work_item_id"],
        one_object_upper_bound=True,
        max_incremental_offering_contribution=1,
    )
    with pytest.raises(dr.ProductDiscoveryError, match="cannot imply a finite one-object bound"):
        dr.validate_resolution_adjudication(unresolved_bound, worklist=worklist)


def test_one_object_upper_bound_requires_cardinality_and_source_specific_evidence() -> None:
    worklist = dr.load_decision_resolution_worklist()
    candidate = _candidate_item(worklist, source_barrier=False)

    bounded = _base_record(
        candidate["work_item_id"],
        disposition="ONE_OBJECT_UPPER_BOUND_UNRESOLVED",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=[
            _historical_evidence(
                role="CARDINALITY_SPECIFIC",
                propositions=["CARDINALITY"],
            )
        ],
        one_object_upper_bound=True,
        max_incremental_offering_contribution=1,
    )
    dr.validate_resolution_adjudication(bounded, worklist=worklist)

    wrong_max = copy.deepcopy(bounded)
    wrong_max["max_incremental_offering_contribution"] = 0
    wrong_max["adjudication_id"] = dr.adjudication_record_id(wrong_max)
    with pytest.raises(dr.ProductDiscoveryError, match="maximum contribution of one"):
        dr.validate_resolution_adjudication(wrong_max, worklist=worklist)

    missing_cardinality = copy.deepcopy(bounded)
    missing_cardinality["evidence"] = [_historical_evidence(propositions=["IDENTITY"])]
    missing_cardinality["adjudication_id"] = dr.adjudication_record_id(missing_cardinality)
    with pytest.raises(dr.ProductDiscoveryError, match="requires historical cardinality support"):
        dr.validate_resolution_adjudication(missing_cardinality, worklist=worklist)

    barrier = _candidate_item(worklist, source_barrier=True)
    barrier_record = _base_record(
        barrier["work_item_id"],
        disposition="ONE_OBJECT_UPPER_BOUND_UNRESOLVED",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=[
            _historical_evidence(
                role="CARDINALITY_SPECIFIC",
                propositions=["CARDINALITY"],
            )
        ],
        one_object_upper_bound=True,
        max_incremental_offering_contribution=1,
    )
    with pytest.raises(dr.ProductDiscoveryError, match="source-specific finite-bound evidence"):
        dr.validate_resolution_adjudication(barrier_record, worklist=worklist)

    barrier_record["evidence"] = [
        _historical_evidence(
            role="SOURCE_ENUMERATION_SPECIFIC",
            propositions=["CARDINALITY", "SOURCE_ENUMERATION"],
        )
    ]
    barrier_record["adjudication_id"] = dr.adjudication_record_id(barrier_record)
    dr.validate_resolution_adjudication(barrier_record, worklist=worklist)


def test_temporal_review_inclusion_and_exclusion_semantics() -> None:
    worklist = dr.load_decision_resolution_worklist()
    item = _temporal_item(worklist)
    subject = item["canonical_offering_id"]

    inclusion = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_INCLUDE_EXISTING_CANONICAL",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=[
            _historical_evidence(
                role="RETROSPECTIVE_EXPLICIT_HISTORICAL_STATE",
                propositions=["IDENTITY", "SCOPE", "CURRENTNESS", "LIFECYCLE"],
            )
        ],
        existing_canonical_offering_id=subject,
        proposed_currentness_state="CURRENT",
        proposed_lifecycle_state="RELEASED",
    )
    dr.validate_resolution_adjudication(inclusion, worklist=worklist)

    wrong_subject = copy.deepcopy(inclusion)
    wrong_subject["existing_canonical_offering_id"] = "PRD-MODIUS-SPERO"
    wrong_subject["adjudication_id"] = dr.adjudication_record_id(wrong_subject)
    with pytest.raises(dr.ProductDiscoveryError, match="cannot change its canonical offering subject"):
        dr.validate_resolution_adjudication(wrong_subject, worklist=worklist)

    missing_temporal = copy.deepcopy(inclusion)
    missing_temporal["evidence"] = [_historical_evidence(propositions=["IDENTITY", "SCOPE"])]
    missing_temporal["adjudication_id"] = dr.adjudication_record_id(missing_temporal)
    with pytest.raises(dr.ProductDiscoveryError, match="historical currentness and lifecycle"):
        dr.validate_resolution_adjudication(missing_temporal, worklist=worklist)

    wrong_currentness = copy.deepcopy(inclusion)
    wrong_currentness["proposed_currentness_state"] = "UNRESOLVED"
    wrong_currentness["adjudication_id"] = dr.adjudication_record_id(wrong_currentness)
    with pytest.raises(dr.ProductDiscoveryError, match="requires proposed CURRENT"):
        dr.validate_resolution_adjudication(wrong_currentness, worklist=worklist)

    exclusion = _base_record(
        item["work_item_id"],
        disposition="TERMINAL_EXCLUDE",
        adjudicator_state="HUMAN_REVIEWED",
        adjudicator_id="reviewer-1",
        evidence=[
            _historical_evidence(
                role="RETROSPECTIVE_EXPLICIT_HISTORICAL_STATE",
                propositions=["CURRENTNESS"],
            )
        ],
        existing_canonical_offering_id=subject,
        proposed_currentness_state="UNRESOLVED",
        proposed_lifecycle_state="UNRESOLVED",
    )
    dr.validate_resolution_adjudication(exclusion, worklist=worklist)

    contradiction = copy.deepcopy(exclusion)
    contradiction["proposed_currentness_state"] = "CURRENT"
    contradiction["proposed_lifecycle_state"] = "RELEASED"
    contradiction["adjudication_id"] = dr.adjudication_record_id(contradiction)
    with pytest.raises(dr.ProductDiscoveryError, match="contradicts a fully qualifying"):
        dr.validate_resolution_adjudication(contradiction, worklist=worklist)

    unresolved = _base_record(item["work_item_id"])
    with pytest.raises(dr.ProductDiscoveryError, match="may terminate only"):
        dr.validate_resolution_adjudication(unresolved, worklist=worklist)


def test_candidate_review_cannot_mutate_temporal_state() -> None:
    worklist = dr.load_decision_resolution_worklist()
    item = _candidate_item(worklist, source_barrier=False)
    record = _base_record(
        item["work_item_id"],
        proposed_currentness_state="CURRENT",
    )
    with pytest.raises(dr.ProductDiscoveryError, match="cannot mutate offering currentness"):
        dr.validate_resolution_adjudication(record, worklist=worklist)
