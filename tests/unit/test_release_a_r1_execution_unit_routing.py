from __future__ import annotations

import copy

import pytest

import neuroai_workbench.release_a_r1_execution_unit_routing as routing


def _reseal(value: dict[str, object], digest_field: str) -> None:
    value[digest_field] = routing.artifact_sha256(value, digest_field=digest_field)


def test_default_execution_unit_routing_reconstructs_exactly() -> None:
    rule = routing.load_execution_unit_routing_rule()
    checkpoint = routing.load_execution_unit_routing()

    assert rule["rule_sha256"] == routing.RULE_SHA256
    assert checkpoint["routing_sha256"] == routing.ROUTING_SHA256
    assert checkpoint["work_item_count"] == 270
    assert checkpoint["route_counts"] == {
        "EMPIRICAL_CANDIDATE_ADJUDICATION": 76,
        "SOURCE_SURFACE_RESOLUTION": 158,
        "LITERATURE_RECORD_EXTRACTION": 34,
        "MIXED_OR_UNRESOLVED_UNIT_REVIEW": 0,
        "A_P1_TEMPORAL_STATE_REVIEW": 2,
    }
    assert checkpoint["decision_role_counts_by_route"] == {
        "EMPIRICAL_CANDIDATE_ADJUDICATION": {
            "total": 76,
            "marginal_yield_sensitive": 76,
            "a3_sensitive": 13,
            "a4_sensitive": 12,
            "a_p1_sensitive": 76,
        },
        "SOURCE_SURFACE_RESOLUTION": {
            "total": 158,
            "marginal_yield_sensitive": 158,
            "a3_sensitive": 18,
            "a4_sensitive": 51,
            "a_p1_sensitive": 158,
        },
        "LITERATURE_RECORD_EXTRACTION": {
            "total": 34,
            "marginal_yield_sensitive": 34,
            "a3_sensitive": 21,
            "a4_sensitive": 0,
            "a_p1_sensitive": 34,
        },
        "MIXED_OR_UNRESOLVED_UNIT_REVIEW": {
            "total": 0,
            "marginal_yield_sensitive": 0,
            "a3_sensitive": 0,
            "a4_sensitive": 0,
            "a_p1_sensitive": 0,
        },
        "A_P1_TEMPORAL_STATE_REVIEW": {
            "total": 2,
            "marginal_yield_sensitive": 0,
            "a3_sensitive": 0,
            "a4_sensitive": 0,
            "a_p1_sensitive": 2,
        },
    }


def test_default_routes_preserve_empirical_unit_semantics() -> None:
    checkpoint = routing.load_execution_unit_routing()

    for item in checkpoint["route_table"]:
        route = item["execution_route"]
        classes = set(item["constituent_unit_classes"])
        if route == routing.SOURCE_SURFACE_RESOLUTION:
            assert classes == {"SOURCE_OR_QUERY_PROBE"}
        elif route == routing.LITERATURE_RECORD_EXTRACTION:
            assert classes == {"LITERATURE_OR_RECORD_PROBE"}
        elif route == routing.EMPIRICAL_CANDIDATE_ADJUDICATION:
            assert classes == {"UNRESOLVED_EMPIRICAL_UNIT"}
        elif route == routing.A_P1_TEMPORAL_STATE_REVIEW:
            assert classes == set()
        else:
            assert route == routing.MIXED_OR_UNRESOLVED_UNIT_REVIEW


def test_temporal_route_contains_only_flow_and_modius() -> None:
    checkpoint = routing.load_execution_unit_routing()
    temporal = {
        item["canonical_offering_id"]
        for item in checkpoint["route_table"]
        if item["execution_route"] == routing.A_P1_TEMPORAL_STATE_REVIEW
    }
    assert temporal == {"PRD-FLOW-FL-100", "PRD-MODIUS-SPERO"}


@pytest.mark.parametrize(
    ("unit_classes", "expected"),
    [
        (["UNRESOLVED_EMPIRICAL_UNIT"], routing.EMPIRICAL_CANDIDATE_ADJUDICATION),
        (["SOURCE_OR_QUERY_PROBE"], routing.SOURCE_SURFACE_RESOLUTION),
        (["LITERATURE_OR_RECORD_PROBE"], routing.LITERATURE_RECORD_EXTRACTION),
        (["OFFERING_CANDIDATE_OBJECT"], routing.MIXED_OR_UNRESOLVED_UNIT_REVIEW),
        (
            ["SOURCE_OR_QUERY_PROBE", "UNRESOLVED_EMPIRICAL_UNIT"],
            routing.MIXED_OR_UNRESOLVED_UNIT_REVIEW,
        ),
        ([], routing.MIXED_OR_UNRESOLVED_UNIT_REVIEW),
    ],
)
def test_route_for_unit_classes_is_fail_closed(unit_classes: list[str], expected: str) -> None:
    assert routing.route_for_unit_classes(unit_classes) == expected


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_workbench_main_commit", "0" * 40, "source_workbench_main_commit drift"),
        ("analysis_universe_id", "RAU-WRONG", "analysis_universe_id drift"),
        ("world_time_cutoff", "2026-09-25", "world_time_cutoff drift"),
        ("knowledge_time_cutoff", "2026-10-25T00:00:00Z", "knowledge_time_cutoff drift"),
        ("r1_4_worklist_sha256", "0" * 64, "r1_4_worklist_sha256 drift"),
        ("r1_5_candidate_unit_rule_sha256", "0" * 64, "r1_5_candidate_unit_rule_sha256 drift"),
        (
            "r1_5_candidate_unit_checkpoint_sha256",
            "0" * 64,
            "r1_5_candidate_unit_checkpoint_sha256 drift",
        ),
        (
            "mixed_or_multiple_unit_classes_route",
            "EMPIRICAL_CANDIDATE_ADJUDICATION",
            "mixed_or_multiple_unit_classes_route drift",
        ),
        ("temporal_work_item_route", "SOURCE_SURFACE_RESOLUTION", "temporal_work_item_route drift"),
    ],
)
def test_rule_rejects_upstream_or_route_drift(
    field: str,
    value: object,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = routing.load_execution_unit_routing_rule()
    changed = copy.deepcopy(rule)
    changed[field] = value
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(routing, "RULE_SHA256", changed["rule_sha256"])

    with pytest.raises(routing.ProductDiscoveryError, match=message):
        routing.validate_execution_unit_routing_rule(changed)


def test_rule_rejects_execution_authority_relaxation(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = routing.load_execution_unit_routing_rule()

    changed = copy.deepcopy(rule)
    changed["execution_controls"]["source_surface_itself_may_receive_product_include_exclude"] = True
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(routing, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(routing.ProductDiscoveryError, match="execution controls drift"):
        routing.validate_execution_unit_routing_rule(changed)

    changed = copy.deepcopy(rule)
    changed["execution_controls"]["literature_record_itself_may_be_counted_as_product_candidate"] = True
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(routing, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(routing.ProductDiscoveryError, match="execution controls drift"):
        routing.validate_execution_unit_routing_rule(changed)

    changed = copy.deepcopy(rule)
    changed["execution_controls"]["extracted_candidate_leads_may_allocate_canonical_identity"] = True
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(routing, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(routing.ProductDiscoveryError, match="execution controls drift"):
        routing.validate_execution_unit_routing_rule(changed)

    changed = copy.deepcopy(rule)
    changed["execution_controls"]["zero_extracted_leads_implies_global_source_exhaustion"] = True
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(routing, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(routing.ProductDiscoveryError, match="execution controls drift"):
        routing.validate_execution_unit_routing_rule(changed)


def test_rule_and_checkpoint_digest_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = routing.load_execution_unit_routing_rule()
    broken_rule = copy.deepcopy(rule)
    broken_rule["status"] = "CHANGED"
    with pytest.raises(routing.ProductDiscoveryError, match="rule digest mismatch"):
        routing.validate_execution_unit_routing_rule(broken_rule)

    checkpoint = routing.load_execution_unit_routing()
    broken_checkpoint = copy.deepcopy(checkpoint)
    broken_checkpoint["aggregate_execution_disposition"] = "CHANGED"
    with pytest.raises(routing.ProductDiscoveryError, match="routing digest mismatch"):
        routing.validate_execution_unit_routing(broken_checkpoint)

    resealed = copy.deepcopy(checkpoint)
    resealed["aggregate_execution_disposition"] = "CHANGED"
    _reseal(resealed, "routing_sha256")
    monkeypatch.setattr(routing, "ROUTING_SHA256", resealed["routing_sha256"])
    with pytest.raises(routing.ProductDiscoveryError, match="does not reproduce"):
        routing.validate_execution_unit_routing(resealed)


def test_derive_rejects_wrong_r1_4_worklist_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    worklist = routing.load_decision_resolution_worklist()
    changed = copy.deepcopy(worklist)
    changed["worklist_sha256"] = "0" * 64
    monkeypatch.setattr(routing, "load_decision_resolution_worklist", lambda: changed)

    with pytest.raises(routing.ProductDiscoveryError, match="exact R1.4 worklist"):
        routing.derive_execution_unit_routing()


def test_derive_rejects_missing_capture_record(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = routing.load_r1_candidate_resolution_manifest()
    records = routing.compile_r1_source_records(manifest)
    worklist = routing.load_decision_resolution_worklist()
    candidate = next(item for item in worklist["work_items"] if item["work_item_type"] == "CANDIDATE_CLUSTER_REVIEW")
    missing_capture = candidate["capture_ids"][0]

    reduced = [item for item in records if item["capture_id"] != missing_capture]
    monkeypatch.setattr(routing, "compile_r1_source_records", lambda _: reduced)

    with pytest.raises(routing.ProductDiscoveryError, match="unknown capture ID"):
        routing.derive_execution_unit_routing()


def test_checkpoint_contains_no_mixed_route_in_current_state() -> None:
    checkpoint = routing.load_execution_unit_routing()
    assert checkpoint["route_counts"][routing.MIXED_OR_UNRESOLVED_UNIT_REVIEW] == 0


def _route_item(execution_route: str) -> dict[str, object]:
    checkpoint = routing.load_execution_unit_routing()
    return next(item for item in checkpoint["route_table"] if item["execution_route"] == execution_route)


def _source_records_by_capture_id() -> dict[str, dict[str, object]]:
    manifest = routing.load_r1_candidate_resolution_manifest()
    records = routing.compile_r1_source_records(manifest)
    return {str(item["capture_id"]): item for item in records}


def _evidence_for_item(
    item: dict[str, object],
    execution_route: str,
    completion_state: str,
    covered_capture_ids: list[str],
    *,
    has_leads: bool,
    source_scope_exhausted: bool,
) -> list[dict[str, object]]:
    if execution_route == routing.SOURCE_SURFACE_RESOLUTION:
        if completion_state == "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS":
            role = "SOURCE_QUERY_EXECUTION"
            propositions = {"SOURCE_QUERY_ZERO_LEADS"}
        elif completion_state == "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS":
            role = "SOURCE_QUERY_EXECUTION"
            propositions = {"SOURCE_QUERY_WITH_LEADS"}
        elif completion_state == "SOURCE_SPECIFIC_FINITE_CARDINALITY_ESTABLISHED":
            role = "SOURCE_ENUMERATION"
            propositions = {"SOURCE_FINITE_CARDINALITY_ESTABLISHED"}
            if has_leads:
                propositions.add("SOURCE_QUERY_WITH_LEADS")
        else:
            role = "SOURCE_ACCESS_BARRIER"
            propositions = {"SOURCE_BARRIER_UNRESOLVED"}
            if has_leads:
                propositions.add("SOURCE_QUERY_WITH_LEADS")
        if source_scope_exhausted:
            propositions.add("SOURCE_SCOPE_EXHAUSTED")
    else:
        role = "RECORD_EXTRACTION"
        if completion_state == "RECORD_EXTRACTED_ZERO_OFFERING_LEADS":
            propositions = {"RECORD_ZERO_OFFERING_LEADS"}
        elif completion_state == "RECORD_EXTRACTED_WITH_OFFERING_LEADS":
            propositions = {"RECORD_WITH_OFFERING_LEADS"}
        else:
            role = "RECORD_ACCESS_BARRIER"
            propositions = {"RECORD_EXTRACTION_UNRESOLVED"}

    source_records = _source_records_by_capture_id()
    evidence: list[dict[str, object]] = []
    for index, capture_id in enumerate(covered_capture_ids, start=1):
        source_record = source_records.get(capture_id)
        query_or_seed_id = source_record["query_or_seed_id"] if source_record is not None else "UNKNOWN"
        evidence.append(
            {
                "evidence_ref": f"EVIDENCE-{index:04d}",
                "capture_id": capture_id,
                "query_or_seed_id": query_or_seed_id,
                "source_locator": f"https://example.invalid/source/{index}",
                "knowledge_observed_at": "2026-09-27T00:00:00Z",
                "sha256": f"{index:064x}",
                "evidence_role": role,
                "supported_propositions": sorted(propositions),
            }
        )
    return evidence


def _lead(work_item_id: str, *, candidate_key: str = "Example::Candidate") -> dict[str, object]:
    source_observation_ref = "OBS-R1-TEST-1"
    return {
        "lead_id": routing.extracted_lead_id(work_item_id, candidate_key, source_observation_ref),
        "candidate_key": candidate_key,
        "source_observation_ref": source_observation_ref,
        "evidence_ref": "EVIDENCE-0001",
        "canonical_offering_id": None,
    }


def _route_execution_record(
    execution_route: str,
    completion_state: str,
    *,
    item: dict[str, object] | None = None,
    extracted_leads: list[dict[str, object]] | None = None,
    source_scope_exhausted: bool = False,
    finite_cardinality_upper_bound: int | None = None,
    review_state: str = "MACHINE_PROVISIONAL",
    reviewer_id: str | None = None,
    covered_capture_ids: list[str] | None = None,
    work_item_completion_claimed: bool = True,
) -> dict[str, object]:
    item = _route_item(execution_route) if item is None else item
    covered = list(item["capture_ids"]) if covered_capture_ids is None else covered_capture_ids
    leads = extracted_leads or []
    record: dict[str, object] = {
        "execution_record_id": "",
        "work_item_id": item["work_item_id"],
        "execution_route": execution_route,
        "completion_state": completion_state,
        "review_state": review_state,
        "reviewer_id": reviewer_id,
        "evidence": _evidence_for_item(
            item,
            execution_route,
            completion_state,
            covered,
            has_leads=bool(leads),
            source_scope_exhausted=source_scope_exhausted,
        ),
        "extracted_leads": leads,
        "source_scope_exhausted": source_scope_exhausted,
        "finite_cardinality_upper_bound": finite_cardinality_upper_bound,
        "global_source_exhaustion_claimed": False,
        "covered_capture_ids": covered,
        "work_item_completion_claimed": work_item_completion_claimed,
    }
    record["execution_record_id"] = routing.route_execution_record_id(record)
    return record


def _reseal_execution_record(record: dict[str, object]) -> None:
    record["execution_record_id"] = routing.route_execution_record_id(record)


def test_source_zero_lead_query_does_not_imply_exhaustion() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )

    routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)
    assert record["source_scope_exhausted"] is False
    assert record["global_source_exhaustion_claimed"] is False


def test_source_exhaustion_requires_human_review() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        source_scope_exhausted=True,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="requires human review"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)

    reviewed = copy.deepcopy(record)
    reviewed["review_state"] = "HUMAN_REVIEWED"
    reviewed["reviewer_id"] = "reviewer-1"
    _reseal_execution_record(reviewed)
    routing.validate_route_execution_record(reviewed, routing_checkpoint=checkpoint)


def test_source_specific_finite_cardinality_requires_human_review() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.SOURCE_SURFACE_RESOLUTION)
    lead = _lead(str(item["work_item_id"]))
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_SPECIFIC_FINITE_CARDINALITY_ESTABLISHED",
        extracted_leads=[lead],
        finite_cardinality_upper_bound=1,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="requires human review"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)

    reviewed = copy.deepcopy(record)
    reviewed["review_state"] = "HUMAN_REVIEWED"
    reviewed["reviewer_id"] = "reviewer-1"
    _reseal_execution_record(reviewed)
    routing.validate_route_execution_record(reviewed, routing_checkpoint=checkpoint)


def test_source_completion_rejects_duplicate_extracted_leads() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.SOURCE_SURFACE_RESOLUTION)
    lead = _lead(str(item["work_item_id"]))
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
        extracted_leads=[lead, copy.deepcopy(lead)],
    )

    with pytest.raises(
        routing.ProductDiscoveryError,
        match="lead IDs must be unique|duplicate extracted candidate lead",
    ):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_extracted_lead_cannot_allocate_canonical_identity() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.SOURCE_SURFACE_RESOLUTION)
    lead = _lead(str(item["work_item_id"]))
    lead["canonical_offering_id"] = "PRD-FORBIDDEN"
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
        extracted_leads=[lead],
    )

    with pytest.raises(routing.ProductDiscoveryError, match="cannot allocate canonical identity"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_literature_record_requires_extraction_before_product_lead() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.LITERATURE_RECORD_EXTRACTION)
    lead = _lead(str(item["work_item_id"]), candidate_key="Article-derived::Offering")
    record = _route_execution_record(
        routing.LITERATURE_RECORD_EXTRACTION,
        "RECORD_EXTRACTED_WITH_OFFERING_LEADS",
        extracted_leads=[lead],
    )
    routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)

    invalid = copy.deepcopy(record)
    invalid["extracted_leads"] = []
    _reseal_execution_record(invalid)
    with pytest.raises(routing.ProductDiscoveryError, match="requires at least one extracted lead"):
        routing.validate_route_execution_record(invalid, routing_checkpoint=checkpoint)


def test_literature_record_cannot_assert_source_exhaustion_or_cardinality() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.LITERATURE_RECORD_EXTRACTION,
        "RECORD_EXTRACTED_ZERO_OFFERING_LEADS",
        source_scope_exhausted=True,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="cannot assert source exhaustion or cardinality"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_rejects_global_exhaustion_claim() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    record["global_source_exhaustion_claimed"] = True
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="cannot claim global source exhaustion"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_rejects_post_knowledge_cutoff_evidence() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    evidence = copy.deepcopy(record["evidence"])
    evidence[0]["knowledge_observed_at"] = "2026-10-25T00:00:00Z"
    record["evidence"] = evidence
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="exceeds the frozen knowledge-time cutoff"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_must_match_frozen_route() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    record["execution_route"] = routing.LITERATURE_RECORD_EXTRACTION
    record["completion_state"] = "RECORD_EXTRACTED_ZERO_OFFERING_LEADS"
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="does not match the frozen execution route"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_candidate_work_item_cannot_use_route_execution_contract() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.EMPIRICAL_CANDIDATE_ADJUDICATION)
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    record["work_item_id"] = item["work_item_id"]
    record["execution_route"] = routing.EMPIRICAL_CANDIDATE_ADJUDICATION
    record["covered_capture_ids"] = list(item["capture_ids"])
    record["work_item_completion_claimed"] = True
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="existing governed contracts"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_work_item_completion_requires_full_capture_coverage() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = next(
        candidate
        for candidate in checkpoint["route_table"]
        if candidate["execution_route"] == routing.SOURCE_SURFACE_RESOLUTION and len(candidate["capture_ids"]) > 1
    )
    first_capture = [str(item["capture_ids"][0])]
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        item=item,
        covered_capture_ids=first_capture,
        work_item_completion_claimed=True,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="requires full frozen capture coverage"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)

    partial = copy.deepcopy(record)
    partial["work_item_completion_claimed"] = False
    _reseal_execution_record(partial)
    routing.validate_route_execution_record(partial, routing_checkpoint=checkpoint)


def test_route_execution_rejects_capture_outside_work_item() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.SOURCE_SURFACE_RESOLUTION)
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        item=item,
        covered_capture_ids=["PDC-" + "0" * 64],
        work_item_completion_claimed=False,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="outside the frozen work item"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_requires_nonempty_capture_coverage() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        covered_capture_ids=[],
        work_item_completion_claimed=False,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="requires explicit covered_capture_ids"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_record_id_is_content_bound() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    record["notes"] = "changed without resealing"

    with pytest.raises(routing.ProductDiscoveryError, match="execution_record_id does not match"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_rejects_noncanonical_evidence_order() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = next(
        candidate
        for candidate in checkpoint["route_table"]
        if candidate["execution_route"] == routing.SOURCE_SURFACE_RESOLUTION and len(candidate["capture_ids"]) > 1
    )
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        item=item,
    )
    record["evidence"] = list(reversed(record["evidence"]))
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="canonical evidence_ref order"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_requires_evidence_for_every_covered_capture() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = next(
        candidate
        for candidate in checkpoint["route_table"]
        if candidate["execution_route"] == routing.SOURCE_SURFACE_RESOLUTION and len(candidate["capture_ids"]) > 1
    )
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        item=item,
    )
    record["evidence"] = list(record["evidence"][:-1])
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="every covered capture requires"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_rejects_query_seed_provenance_drift() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    evidence = copy.deepcopy(record["evidence"])
    evidence[0]["query_or_seed_id"] = "WRONG-QUERY"
    record["evidence"] = evidence
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="query_or_seed_id drift"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_source_completion_rejects_incompatible_evidence_proposition() -> None:
    checkpoint = routing.load_execution_unit_routing()
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    evidence = copy.deepcopy(record["evidence"])
    evidence[0]["supported_propositions"] = ["SOURCE_QUERY_WITH_LEADS"]
    record["evidence"] = evidence
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="per-capture zero-lead evidence"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_extracted_lead_requires_lead_bearing_evidence() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.SOURCE_SURFACE_RESOLUTION)
    lead = _lead(str(item["work_item_id"]))
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
        item=item,
        extracted_leads=[lead],
    )
    evidence = copy.deepcopy(record["evidence"])
    evidence[0]["supported_propositions"] = ["SOURCE_QUERY_ZERO_LEADS"]
    record["evidence"] = evidence
    _reseal_execution_record(record)

    with pytest.raises(routing.ProductDiscoveryError, match="does not support an extracted-lead proposition"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_rejects_noncanonical_lead_order() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = _route_item(routing.SOURCE_SURFACE_RESOLUTION)
    work_item_id = str(item["work_item_id"])
    leads = [
        _lead(work_item_id, candidate_key="Example::Candidate A"),
        _lead(work_item_id, candidate_key="Example::Candidate B"),
    ]
    leads.sort(key=lambda item: str(item["lead_id"]), reverse=True)
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
        item=item,
        extracted_leads=leads,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="canonical lead_id order"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)


def test_route_execution_rejects_noncanonical_capture_order() -> None:
    checkpoint = routing.load_execution_unit_routing()
    item = next(
        candidate
        for candidate in checkpoint["route_table"]
        if candidate["execution_route"] == routing.SOURCE_SURFACE_RESOLUTION and len(candidate["capture_ids"]) > 1
    )
    covered = list(reversed([str(capture_id) for capture_id in item["capture_ids"]]))
    record = _route_execution_record(
        routing.SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        item=item,
        covered_capture_ids=covered,
        work_item_completion_claimed=False,
    )

    with pytest.raises(routing.ProductDiscoveryError, match="preserve frozen capture order"):
        routing.validate_route_execution_record(record, routing_checkpoint=checkpoint)
