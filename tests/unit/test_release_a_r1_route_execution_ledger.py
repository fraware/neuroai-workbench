from __future__ import annotations

import copy

import pytest

import neuroai_workbench.release_a_r1_route_execution_ledger as ledger
from neuroai_workbench.release_a_r1_execution_unit_routing import (
    LITERATURE_RECORD_EXTRACTION,
    SOURCE_SURFACE_RESOLUTION,
    extracted_lead_id,
    load_execution_unit_routing,
    route_execution_record_id,
)
from neuroai_workbench.release_a_r1_resolution import (
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)


def _source_records() -> dict[str, dict[str, object]]:
    manifest = load_r1_candidate_resolution_manifest()
    rows = compile_r1_source_records(manifest)
    return {str(item["capture_id"]): item for item in rows}


def _item(route: str, *, multi: bool = False) -> dict[str, object]:
    checkpoint = load_execution_unit_routing()
    return next(
        item
        for item in checkpoint["route_table"]
        if item["execution_route"] == route and (not multi or len(item["capture_ids"]) > 1)
    )


def _evidence(
    item: dict[str, object],
    route: str,
    completion_state: str,
    *,
    evidence_suffix: str = "",
    source_scope_exhausted: bool = False,
) -> list[dict[str, object]]:
    source_records = _source_records()
    if route == SOURCE_SURFACE_RESOLUTION:
        if completion_state == "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS":
            role = "SOURCE_QUERY_EXECUTION"
            propositions = {"SOURCE_QUERY_ZERO_LEADS"}
        elif completion_state == "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS":
            role = "SOURCE_QUERY_EXECUTION"
            propositions = {"SOURCE_QUERY_WITH_LEADS"}
        elif completion_state == "SOURCE_SPECIFIC_FINITE_CARDINALITY_ESTABLISHED":
            role = "SOURCE_ENUMERATION"
            propositions = {"SOURCE_FINITE_CARDINALITY_ESTABLISHED"}
        else:
            role = "SOURCE_ACCESS_BARRIER"
            propositions = {"SOURCE_BARRIER_UNRESOLVED"}
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

    result = []
    for index, capture_id_raw in enumerate(item["capture_ids"], start=1):
        capture_id = str(capture_id_raw)
        source = source_records[capture_id]
        result.append(
            {
                "evidence_ref": f"EVIDENCE-{index:04d}{evidence_suffix}",
                "capture_id": capture_id,
                "query_or_seed_id": source["query_or_seed_id"],
                "source_locator": f"https://example.invalid/{index}{evidence_suffix}",
                "knowledge_observed_at": "2026-09-28T00:00:00Z",
                "sha256": f"{index:064x}",
                "evidence_role": role,
                "supported_propositions": sorted(propositions),
            }
        )
    return result


def _lead(
    item: dict[str, object],
    *,
    candidate_key: str = "Example::Offering",
    evidence_ref: str = "EVIDENCE-0001",
) -> dict[str, object]:
    work_item_id = str(item["work_item_id"])
    source_observation_ref = "OBS-R1-LEDGER-TEST"
    return {
        "lead_id": extracted_lead_id(work_item_id, candidate_key, source_observation_ref),
        "candidate_key": candidate_key,
        "source_observation_ref": source_observation_ref,
        "evidence_ref": evidence_ref,
        "canonical_offering_id": None,
    }


def _record(
    item: dict[str, object],
    route: str,
    completion_state: str,
    *,
    work_item_completion_claimed: bool = True,
    extracted_leads: list[dict[str, object]] | None = None,
    evidence_suffix: str = "",
    source_scope_exhausted: bool = False,
    finite_cardinality_upper_bound: int | None = None,
    review_state: str = "MACHINE_PROVISIONAL",
    reviewer_id: str | None = None,
    covered_capture_ids: list[str] | None = None,
) -> dict[str, object]:
    covered = [str(value) for value in item["capture_ids"]] if covered_capture_ids is None else covered_capture_ids
    full_evidence = _evidence(
        item,
        route,
        completion_state,
        evidence_suffix=evidence_suffix,
        source_scope_exhausted=source_scope_exhausted,
    )
    by_capture = {str(entry["capture_id"]): entry for entry in full_evidence}
    evidence = [by_capture[capture_id] for capture_id in covered]

    record: dict[str, object] = {
        "execution_record_id": "",
        "work_item_id": item["work_item_id"],
        "execution_route": route,
        "completion_state": completion_state,
        "review_state": review_state,
        "reviewer_id": reviewer_id,
        "evidence": evidence,
        "extracted_leads": extracted_leads or [],
        "source_scope_exhausted": source_scope_exhausted,
        "finite_cardinality_upper_bound": finite_cardinality_upper_bound,
        "global_source_exhaustion_claimed": False,
        "covered_capture_ids": covered,
        "work_item_completion_claimed": work_item_completion_claimed,
    }
    record["execution_record_id"] = route_execution_record_id(record)
    return record


def _entry(
    record: dict[str, object],
    *,
    supersedes: list[str] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "ledger_entry_id": "",
        "route_execution_record": record,
        "supersedes_ledger_entry_ids": supersedes or [],
    }
    value["ledger_entry_id"] = ledger.ledger_entry_id(value)
    return value


def _reseal_record(record: dict[str, object]) -> None:
    record["execution_record_id"] = route_execution_record_id(record)


def _reseal_entry(entry: dict[str, object]) -> None:
    entry["ledger_entry_id"] = ledger.ledger_entry_id(entry)


def test_frozen_rule_and_execution_population_are_exact() -> None:
    rule = ledger.load_route_execution_ledger_rule()
    population = ledger.derive_execution_population()
    assert rule["rule_sha256"] == ledger.RULE_SHA256
    assert len(population) == 192
    assert sum(len(item["capture_ids"]) for item in population) == 247
    assert sum(item["execution_route"] == SOURCE_SURFACE_RESOLUTION for item in population) == 158
    assert sum(item["execution_route"] == LITERATURE_RECORD_EXTRACTION for item in population) == 34


def test_empty_ledger_state_is_nonfinal_and_fully_pending() -> None:
    state = ledger.derive_ledger_state([])
    assert state["frozen_work_item_count"] == 192
    assert state["frozen_capture_count"] == 247
    assert state["ledger_entry_count"] == 0
    assert state["completed_work_item_count"] == 0
    assert state["pending_work_item_count"] == 192
    assert state["extracted_lead_count"] == 0


def test_valid_source_and_record_completion_aggregate() -> None:
    source_item = _item(SOURCE_SURFACE_RESOLUTION)
    record_item = _item(LITERATURE_RECORD_EXTRACTION)
    source_entry = _entry(
        _record(
            source_item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        )
    )
    record_entry = _entry(
        _record(
            record_item,
            LITERATURE_RECORD_EXTRACTION,
            "RECORD_EXTRACTED_ZERO_OFFERING_LEADS",
        )
    )

    state = ledger.derive_ledger_state([source_entry, record_entry])
    assert state["active_ledger_entry_count"] == 2
    assert state["completed_work_item_count"] == 2
    assert state["active_entry_count_by_route"] == {
        SOURCE_SURFACE_RESOLUTION: 1,
        LITERATURE_RECORD_EXTRACTION: 1,
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_workbench_main_commit", "0" * 40, "source_workbench_main_commit drift"),
        ("r1_6_rule_sha256", "0" * 64, "r1_6_rule_sha256 drift"),
        ("r1_6_routing_sha256", "0" * 64, "r1_6_routing_sha256 drift"),
        ("expected_work_item_count", 191, "expected_work_item_count drift"),
        ("expected_capture_count", 246, "expected_capture_count drift"),
    ],
)
def test_rule_rejects_upstream_or_population_drift(
    field: str,
    value: object,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = ledger.load_route_execution_ledger_rule()
    changed = copy.deepcopy(rule)
    changed[field] = value
    changed["rule_sha256"] = ledger.artifact_sha256(changed, digest_field="rule_sha256")
    monkeypatch.setattr(ledger, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(ledger.ProductDiscoveryError, match=message):
        ledger.validate_route_execution_ledger_rule(changed)


def test_rule_rejects_digest_schema_aggregation_lead_and_finality_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = ledger.load_route_execution_ledger_rule()

    broken = copy.deepcopy(rule)
    broken["status"] = "CHANGED"
    with pytest.raises(ledger.ProductDiscoveryError, match="digest mismatch"):
        ledger.validate_route_execution_ledger_rule(broken)

    for field, message in [
        ("ledger_entry_schema", "ledger-entry schema drift"),
        ("aggregation_contract", "aggregation contract drift"),
        ("extracted_lead_contract", "extracted-lead contract drift"),
        ("completion_contract", "completion contract drift"),
        ("evidence_archive_contract", "evidence-archive contract drift"),
        ("temporal_interpretation_contract", "temporal-interpretation contract drift"),
        ("finality", "finality boundary drift"),
    ]:
        changed = copy.deepcopy(rule)
        first_key = next(iter(changed[field]))
        current = changed[field][first_key]
        changed[field][first_key] = not current if isinstance(current, bool) else "CHANGED"
        changed["rule_sha256"] = ledger.artifact_sha256(changed, digest_field="rule_sha256")
        monkeypatch.setattr(ledger, "RULE_SHA256", changed["rule_sha256"])
        with pytest.raises(ledger.ProductDiscoveryError, match=message):
            ledger.validate_route_execution_ledger_rule(changed)

    changed = copy.deepcopy(rule)
    changed["incompatible_proposition_sets"][SOURCE_SURFACE_RESOLUTION] = []
    changed["rule_sha256"] = ledger.artifact_sha256(changed, digest_field="rule_sha256")
    monkeypatch.setattr(ledger, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(ledger.ProductDiscoveryError, match="proposition-conflict contract drift"):
        ledger.validate_route_execution_ledger_rule(changed)


def test_ledger_entry_rejects_field_id_route_and_supersession_list_drift() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    record = _record(
        item,
        SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
    )
    entry = _entry(record)

    changed = copy.deepcopy(entry)
    changed["unexpected"] = True
    with pytest.raises(ledger.ProductDiscoveryError, match="fields drift"):
        ledger.validate_ledger_entry(changed)

    changed = copy.deepcopy(entry)
    changed["ledger_entry_id"] = "R1LEDGER-" + "0" * 64
    with pytest.raises(ledger.ProductDiscoveryError, match="does not match deterministic content"):
        ledger.validate_ledger_entry(changed)

    changed = copy.deepcopy(entry)
    changed["route_execution_record"] = "bad"
    _reseal_entry(changed)
    with pytest.raises(ledger.ProductDiscoveryError, match="requires route_execution_record"):
        ledger.validate_ledger_entry(changed)

    changed = copy.deepcopy(entry)
    changed["route_execution_record"]["execution_route"] = "EMPIRICAL_CANDIDATE_ADJUDICATION"
    _reseal_record(changed["route_execution_record"])
    _reseal_entry(changed)
    with pytest.raises(ledger.ProductDiscoveryError, match="outside the governed"):
        ledger.validate_ledger_entry(changed)

    changed = copy.deepcopy(entry)
    changed["supersedes_ledger_entry_ids"] = "bad"
    _reseal_entry(changed)
    with pytest.raises(ledger.ProductDiscoveryError, match="must be a list"):
        ledger.validate_ledger_entry(changed)

    changed = copy.deepcopy(entry)
    changed["supersedes_ledger_entry_ids"] = ["B", "A", "A"]
    _reseal_entry(changed)
    with pytest.raises(ledger.ProductDiscoveryError, match="unique and canonical"):
        ledger.validate_ledger_entry(changed)


def test_partial_multi_capture_record_cannot_claim_completion() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION, multi=True)
    record = _record(
        item,
        SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        covered_capture_ids=[str(item["capture_ids"][0])],
        work_item_completion_claimed=True,
    )
    entry = _entry(record)
    with pytest.raises(ledger.ProductDiscoveryError, match="completion requires full frozen capture coverage"):
        ledger.derive_ledger_state([entry])


def test_explicit_supersession_replaces_active_support_without_erasing_history() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    lead = _lead(item)
    first = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
            extracted_leads=[lead],
        )
    )
    second = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            evidence_suffix="-2",
        ),
        supersedes=[str(first["ledger_entry_id"])],
    )

    state = ledger.derive_ledger_state([first, second])
    assert state["ledger_entry_count"] == 2
    assert state["active_ledger_entry_count"] == 1
    assert state["superseded_ledger_entry_count"] == 1
    assert state["extracted_lead_count"] == 1
    assert state["active_extracted_lead_count"] == 0
    assert state["extracted_lead_ledger"][0]["active_support"] is False


def test_conflicting_active_records_fail_closed_without_supersession() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    zero = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            work_item_completion_claimed=False,
        )
    )
    lead = _lead(item, evidence_ref="EVIDENCE-0001-X")
    with_lead = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
            extracted_leads=[lead],
            evidence_suffix="-X",
            work_item_completion_claimed=False,
        )
    )

    with pytest.raises(ledger.ProductDiscoveryError, match="conflicting active propositions"):
        ledger.derive_ledger_state([zero, with_lead])


def test_compatible_overlapping_active_records_are_retained() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    first = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            work_item_completion_claimed=False,
        )
    )
    second = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            evidence_suffix="-2",
            work_item_completion_claimed=True,
        )
    )
    state = ledger.derive_ledger_state([first, second])
    assert state["active_ledger_entry_count"] == 2
    assert state["completed_work_item_count"] == 1


def test_multiple_active_completion_records_fail_closed() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    first = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        )
    )
    second = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            evidence_suffix="-2",
        )
    )
    with pytest.raises(ledger.ProductDiscoveryError, match="multiple active completion records"):
        ledger.derive_ledger_state([first, second])


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("future", "prior ledger entry"),
        ("cross_work_item", "cannot cross work-item identity"),
        ("disjoint", "requires overlapping capture coverage"),
    ],
)
def test_supersession_is_strictly_scoped(kind: str, message: str) -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION, multi=True)
    first_record = _record(
        item,
        SOURCE_SURFACE_RESOLUTION,
        "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        covered_capture_ids=[str(item["capture_ids"][0])],
        work_item_completion_claimed=False,
    )
    first = _entry(first_record)

    if kind == "future":
        second = _entry(
            _record(
                item,
                SOURCE_SURFACE_RESOLUTION,
                "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
                evidence_suffix="-2",
                work_item_completion_claimed=False,
            ),
            supersedes=["R1LEDGER-" + "f" * 64],
        )
    elif kind == "cross_work_item":
        other = next(
            candidate
            for candidate in load_execution_unit_routing()["route_table"]
            if candidate["execution_route"] == SOURCE_SURFACE_RESOLUTION
            and candidate["work_item_id"] != item["work_item_id"]
        )
        second = _entry(
            _record(
                other,
                SOURCE_SURFACE_RESOLUTION,
                "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
                work_item_completion_claimed=False,
            ),
            supersedes=[str(first["ledger_entry_id"])],
        )
    else:
        second_record = _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            covered_capture_ids=[str(item["capture_ids"][1])],
            evidence_suffix="-2",
            work_item_completion_claimed=False,
        )
        second = _entry(second_record, supersedes=[str(first["ledger_entry_id"])])

    with pytest.raises(ledger.ProductDiscoveryError, match=message):
        ledger.derive_ledger_state([first, second])


def test_duplicate_entry_and_execution_record_ids_fail_closed() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    first = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            work_item_completion_claimed=False,
        )
    )

    with pytest.raises(ledger.ProductDiscoveryError, match="duplicate ledger_entry_id"):
        ledger.derive_ledger_state([first, copy.deepcopy(first)])

    second = copy.deepcopy(first)
    second["supersedes_ledger_entry_ids"] = []
    second["ledger_entry_id"] = "R1LEDGER-" + "1" * 64
    with pytest.raises(ledger.ProductDiscoveryError, match="does not match deterministic content"):
        ledger.derive_ledger_state([first, second])

    second = _entry(
        copy.deepcopy(first["route_execution_record"]),
        supersedes=[str(first["ledger_entry_id"])],
    )
    with pytest.raises(ledger.ProductDiscoveryError, match="duplicate execution_record_id"):
        ledger.derive_ledger_state([first, second])


def test_same_lead_id_with_conflicting_payload_fails_closed() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    lead1 = _lead(item)
    first = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
            extracted_leads=[lead1],
            work_item_completion_claimed=False,
        )
    )

    lead2 = copy.deepcopy(lead1)
    lead2["evidence_ref"] = "EVIDENCE-0001-X"
    second = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_WITH_EXTRACTED_LEADS",
            extracted_leads=[lead2],
            evidence_suffix="-X",
            work_item_completion_claimed=False,
        )
    )
    with pytest.raises(ledger.ProductDiscoveryError, match="identical lead_id has conflicting payload"):
        ledger.derive_ledger_state([first, second])


def test_execution_population_rejects_count_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    checkpoint = load_execution_unit_routing()
    monkeypatch.setattr(ledger, "validate_execution_unit_routing", lambda _: None)

    changed = copy.deepcopy(checkpoint)
    changed["route_table"] = [
        item for item in changed["route_table"] if item["execution_route"] != LITERATURE_RECORD_EXTRACTION
    ]
    with pytest.raises(ledger.ProductDiscoveryError, match="work-item count drift"):
        ledger.derive_execution_population(changed)

    changed = copy.deepcopy(checkpoint)
    target = next(
        item
        for item in changed["route_table"]
        if item["execution_route"] == SOURCE_SURFACE_RESOLUTION and len(item["capture_ids"]) > 1
    )
    target["capture_ids"] = list(target["capture_ids"][:-1])
    with pytest.raises(ledger.ProductDiscoveryError, match="capture count drift"):
        ledger.derive_execution_population(changed)


def test_supersession_cannot_drop_uncorrected_capture_claims() -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION, multi=True)
    prior_captures = [str(value) for value in item["capture_ids"][:2]]
    first = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            covered_capture_ids=prior_captures,
            work_item_completion_claimed=False,
        )
    )
    second = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            covered_capture_ids=[prior_captures[0]],
            evidence_suffix="-2",
            work_item_completion_claimed=False,
        ),
        supersedes=[str(first["ledger_entry_id"])],
    )

    with pytest.raises(ledger.ProductDiscoveryError, match="cover every capture"):
        ledger.derive_ledger_state([first, second])


def test_cross_route_supersession_fails_closed_even_under_adversarial_validator_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _item(SOURCE_SURFACE_RESOLUTION)
    first = _entry(
        _record(
            item,
            SOURCE_SURFACE_RESOLUTION,
            "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
            work_item_completion_claimed=False,
        )
    )
    second_record = copy.deepcopy(first["route_execution_record"])
    second_record["execution_route"] = LITERATURE_RECORD_EXTRACTION
    _reseal_record(second_record)
    second = _entry(second_record, supersedes=[str(first["ledger_entry_id"])])

    monkeypatch.setattr(ledger, "validate_ledger_entry", lambda *args, **kwargs: None)
    with pytest.raises(ledger.ProductDiscoveryError, match="cannot cross execution route"):
        ledger.derive_ledger_state([first, second])
