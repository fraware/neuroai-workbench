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
