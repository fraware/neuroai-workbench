from __future__ import annotations

import copy

import pytest

import neuroai_workbench.release_a_r1_candidate_unit_audit as cu


def _reseal(value: dict[str, object], field: str) -> None:
    value[field] = cu.artifact_sha256(value, digest_field=field)


def _record(
    *,
    label: str,
    outcome: str = "ABSTAIN",
    canonical_offering_id: str | None = None,
) -> dict[str, object]:
    return {
        "capture_id": "PDC-test",
        "source_record_id": "PDC-test",
        "candidate_cluster_id": "R1CC-test",
        "frame_id": "F1",
        "round_id": "R2",
        "query_or_seed_id": "Q-1",
        "query_family": "TEST",
        "source_class": "TEST",
        "source_observation_ref": "OBS-test",
        "normalized_candidate_key": f"test::{label}",
        "normalized_candidate_label": label,
        "outcome": outcome,
        "canonical_offering_id": canonical_offering_id,
        "uncertainty_cardinality_class": "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER",
    }


def _classification(
    unit_class: str,
    *,
    key: str | None = None,
    frame_id: str = "F1",
    round_id: str = "R2",
) -> dict[str, object]:
    return {
        "frame_id": frame_id,
        "round_id": round_id,
        "unit_class": unit_class,
        "candidate_object_dedup_key": key,
    }


def _packet(*, raw: int, y: int, m: float) -> dict[str, object]:
    return {
        "packet_sha256": "a" * 64,
        "round_summaries": [
            {
                "round_id": "R2",
                "raw_candidates": raw,
                "new_resolved_include_identities": y,
                "marginal_new_identity_yield": m,
            }
        ],
    }


def test_default_candidate_unit_audit_reconstructs_exactly() -> None:
    rule = cu.load_candidate_unit_audit_rule()
    audit = cu.load_candidate_unit_audit()

    assert rule["rule_sha256"] == cu.RULE_SHA256
    assert audit["audit_sha256"] == cu.AUDIT_SHA256
    assert audit["audited_capture_row_count"] == 342
    assert audit["unit_class_counts"] == {
        "OFFERING_CANDIDATE_OBJECT": 46,
        "SOURCE_OR_QUERY_PROBE": 156,
        "LITERATURE_OR_RECORD_PROBE": 29,
        "UNRESOLVED_EMPIRICAL_UNIT": 111,
    }
    assert audit["aggregate_scientific_disposition"] == (
        "NO_HISTORICAL_MARGINAL_YIELD_FRAME_CURRENTLY_SUPPORTS_CANDIDATE_UNIT_SATURATION"
    )

    frame_states = {item["frame_id"]: item["candidate_unit_scientific_state"] for item in audit["frame_results"]}
    assert frame_states == {
        "F1": "CANDIDATE_UNIT_RESOLUTION_CENSORED",
        "F4": "CANDIDATE_UNIT_RESOLUTION_CENSORED",
        "F5": "CANDIDATE_UNIT_RESOLUTION_CENSORED",
        "F6": "CANDIDATE_UNIT_RESOLUTION_CENSORED",
        "F8": "CANDIDATE_UNIT_RESOLUTION_CENSORED",
        "F11": "CANDIDATE_UNIT_DENOMINATOR_INSUFFICIENT",
    }
    assert all(
        item["historical_final_stop_state"] == "SATURATION_UNDER_DECLARED_PROTOCOL" for item in audit["frame_results"]
    )


def test_f8_r2_exposes_capture_row_denominator_failure() -> None:
    audit = cu.load_candidate_unit_audit()
    result = next(item for item in audit["round_results"] if item["frame_id"] == "F8" and item["round_id"] == "R2")

    assert result["C_capture"] == 21
    assert result["C_candidate"] == 0
    assert result["source_or_query_probe_count"] == 21
    assert result["literature_or_record_probe_count"] == 0
    assert result["unresolved_empirical_unit_count"] == 0
    assert result["m_capture"] == 0
    assert result["m_candidate"] is None
    assert result["candidate_denominator_identified"] is True
    assert result["candidate_object_count_meets_historical_numeric_floor"] is False
    assert result["candidate_unit_state"] == "CANDIDATE_UNIT_DENOMINATOR_INSUFFICIENT"


def test_f11_tail_deduplicates_known_offering_objects() -> None:
    audit = cu.load_candidate_unit_audit()
    tail = [item for item in audit["round_results"] if item["frame_id"] == "F11"]

    assert [item["round_id"] for item in tail] == ["R2", "R3"]
    assert all(item["C_capture"] == 40 for item in tail)
    assert all(item["offering_candidate_object_row_count"] == 15 for item in tail)
    assert all(item["C_candidate"] == 5 for item in tail)
    assert all(item["m_candidate"] == 0 for item in tail)
    assert all(item["candidate_object_count_meets_historical_numeric_floor"] is False for item in tail)
    assert all(item["candidate_unit_state"] == "CANDIDATE_UNIT_DENOMINATOR_INSUFFICIENT" for item in tail)


@pytest.mark.parametrize(
    ("record", "unit_class", "basis", "key"),
    [
        (
            _record(label="Muse S Athena", outcome="INCLUDE_RESOLVED", canonical_offering_id="PRD-MUSE-S-ATHENA"),
            "OFFERING_CANDIDATE_OBJECT",
            "HISTORICAL_INCLUDE_RESOLVED_CANONICAL",
            "PRD-MUSE-S-ATHENA",
        ),
        (
            _record(label="page-surface"),
            "SOURCE_OR_QUERY_PROBE",
            "EXPLICIT_SOURCE_OR_QUERY_PROBE_SENTINEL",
            None,
        ),
        (
            _record(label="Modius::product_to_related_product"),
            "SOURCE_OR_QUERY_PROBE",
            "EXPLICIT_SOURCE_OR_QUERY_PROBE_SENTINEL",
            None,
        ),
        (
            _record(label="distributor/shop channel"),
            "SOURCE_OR_QUERY_PROBE",
            "EXPLICIT_SOURCE_OR_QUERY_PROBE_SENTINEL",
            None,
        ),
        (
            _record(label="lit-42505450"),
            "LITERATURE_OR_RECORD_PROBE",
            "EXPLICIT_LITERATURE_RECORD_SENTINEL",
            None,
        ),
        (
            _record(label="empty-europepmc"),
            "LITERATURE_OR_RECORD_PROBE",
            "EXPLICIT_LITERATURE_RECORD_SENTINEL",
            None,
        ),
        (
            _record(label="Open-LIFU (literature)", outcome="UNRESOLVED_IDENTITY"),
            "UNRESOLVED_EMPIRICAL_UNIT",
            "EMPIRICAL_UNIT_NOT_GOVERNED_PRE_ADJUDICATION",
            None,
        ),
    ],
)
def test_classification_contract_is_fail_closed(
    record: dict[str, object],
    unit_class: str,
    basis: str,
    key: str | None,
) -> None:
    result = cu.classify_capture_unit(record, cu.load_candidate_unit_audit_rule())
    assert result["unit_class"] == unit_class
    assert result["classification_basis"] == basis
    assert result["candidate_object_dedup_key"] == key


def test_round_result_resolution_censored() -> None:
    result = cu._round_result(
        frame_id="F1",
        round_id="R2",
        classifications=[
            _classification("OFFERING_CANDIDATE_OBJECT", key="PRD-1"),
            _classification("UNRESOLVED_EMPIRICAL_UNIT"),
        ],
        packet=_packet(raw=2, y=0, m=0),
    )
    assert result["C_candidate"] == 1
    assert result["m_candidate"] is None
    assert result["candidate_unit_state"] == "CANDIDATE_UNIT_RESOLUTION_CENSORED"


def test_round_result_denominator_insufficient_with_zero_candidates() -> None:
    result = cu._round_result(
        frame_id="F1",
        round_id="R2",
        classifications=[
            _classification("SOURCE_OR_QUERY_PROBE"),
            _classification("LITERATURE_OR_RECORD_PROBE"),
        ],
        packet=_packet(raw=2, y=0, m=0),
    )
    assert result["candidate_denominator_identified"] is True
    assert result["C_candidate"] == 0
    assert result["m_candidate"] is None
    assert result["candidate_unit_state"] == "CANDIDATE_UNIT_DENOMINATOR_INSUFFICIENT"


def test_round_result_candidate_unit_saturation_path() -> None:
    rows = [_classification("OFFERING_CANDIDATE_OBJECT", key=f"PRD-{index}") for index in range(20)]
    result = cu._round_result(
        frame_id="F1",
        round_id="R2",
        classifications=rows,
        packet=_packet(raw=20, y=1, m=0.05),
    )
    assert result["C_candidate"] == 20
    assert result["m_candidate"] == 0.05
    assert result["candidate_object_count_meets_historical_numeric_floor"] is True
    assert result["candidate_unit_state"] == "CANDIDATE_UNIT_SATURATION_IDENTIFIED"


def test_round_result_detects_capture_candidate_disagreement() -> None:
    rows = [
        _classification("OFFERING_CANDIDATE_OBJECT", key=f"PRD-{index}")
        for index in range(20)
    ]
    result = cu._round_result(
        frame_id="F1",
        round_id="R2",
        classifications=rows,
        packet=_packet(raw=20, y=2, m=0.1),
    )
    assert result["m_candidate"] == 0.1
    assert result["candidate_unit_state"] == "MECHANICAL_CAPTURE_ROW_SATURATION_ONLY"


def test_round_result_rejects_capture_count_mismatch() -> None:
    with pytest.raises(cu.ProductDiscoveryError, match="do not reproduce C_capture"):
        cu._round_result(
            frame_id="F1",
            round_id="R2",
            classifications=[_classification("SOURCE_OR_QUERY_PROBE")],
            packet=_packet(raw=2, y=0, m=0),
        )


def test_round_result_rejects_candidate_without_dedup_key() -> None:
    with pytest.raises(cu.ProductDiscoveryError, match="lacks a deterministic dedup key"):
        cu._round_result(
            frame_id="F1",
            round_id="R2",
            classifications=[_classification("OFFERING_CANDIDATE_OBJECT")],
            packet=_packet(raw=1, y=0, m=0),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_workbench_main_commit", "0" * 40, "source_workbench_main_commit drift"),
        ("analysis_universe_id", "RAU-WRONG", "analysis_universe_id drift"),
        ("world_time_cutoff", "2026-09-25", "world_time_cutoff drift"),
        ("knowledge_time_cutoff", "2026-10-25T00:00:00Z", "knowledge_time_cutoff drift"),
        ("population_view_id", "A-P6", "population_view_id drift"),
        ("r1_2_candidate_resolution_manifest_sha256", "0" * 64, "r1_2_candidate_resolution_manifest_sha256 drift"),
        ("r1_2_candidate_cluster_ledger_sha256", "0" * 64, "r1_2_candidate_cluster_ledger_sha256 drift"),
        ("r1_3_resolution_completeness_rule_sha256", "0" * 64, "r1_3_resolution_completeness_rule_sha256 drift"),
        (
            "r1_3_resolution_completeness_checkpoint_sha256",
            "0" * 64,
            "r1_3_resolution_completeness_checkpoint_sha256 drift",
        ),
        ("r1_4_worklist_rule_sha256", "0" * 64, "r1_4_worklist_rule_sha256 drift"),
        ("r1_4_worklist_sha256", "0" * 64, "r1_4_worklist_sha256 drift"),
        ("audited_frames", ["F1"], "audited_frames drift"),
        ("audited_rounds", ["R3"], "audited_rounds drift"),
    ],
)
def test_rule_rejects_upstream_drift(
    field: str,
    value: object,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = cu.load_candidate_unit_audit_rule()
    changed = copy.deepcopy(rule)
    changed[field] = value
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(cu, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match=message):
        cu.validate_candidate_unit_audit_rule(changed)


def test_rule_rejects_semantic_contract_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = cu.load_candidate_unit_audit_rule()

    changed = copy.deepcopy(rule)
    changed["historical_mechanical_contract"]["minimum_raw_candidates_per_round"] = 19
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(cu, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match="mechanical contract drift"):
        cu.validate_candidate_unit_audit_rule(changed)

    changed = copy.deepcopy(rule)
    changed["classification_contract"]["all_other_nonterminal_rows_default_to"] = "OFFERING_CANDIDATE_OBJECT"
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(cu, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match="unresolved empirical-unit default drift"):
        cu.validate_candidate_unit_audit_rule(changed)

    changed = copy.deepcopy(rule)
    changed["classification_contract"]["inference_from_product_looking_name_alone_prohibited"] = False
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(cu, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match="product-looking-name inference"):
        cu.validate_candidate_unit_audit_rule(changed)

    changed = copy.deepcopy(rule)
    changed["candidate_unit_accounting"][
        "candidate_denominator_identified_only_if_unresolved_empirical_unit_count_is_zero"
    ] = False
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(cu, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match="identifiability rule drift"):
        cu.validate_candidate_unit_audit_rule(changed)

    changed = copy.deepcopy(rule)
    changed["candidate_unit_accounting"]["historical_numeric_floor_sensitivity"] = 19
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(cu, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match="numeric-floor sensitivity drift"):
        cu.validate_candidate_unit_audit_rule(changed)

    changed = copy.deepcopy(rule)
    changed["finality"]["final_rebind_after_r1_4_adjudication_required"] = False
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(cu, "RULE_SHA256", changed["rule_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match="final rebind contract drift"):
        cu.validate_candidate_unit_audit_rule(changed)


def test_rule_and_audit_digest_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = cu.load_candidate_unit_audit_rule()
    broken_rule = copy.deepcopy(rule)
    broken_rule["status"] = "CHANGED"
    with pytest.raises(cu.ProductDiscoveryError, match="rule digest mismatch"):
        cu.validate_candidate_unit_audit_rule(broken_rule)

    audit = cu.load_candidate_unit_audit()
    broken_audit = copy.deepcopy(audit)
    broken_audit["aggregate_scientific_disposition"] = "CHANGED"
    with pytest.raises(cu.ProductDiscoveryError, match="audit digest mismatch"):
        cu.validate_candidate_unit_audit(broken_audit)

    resealed = copy.deepcopy(audit)
    resealed["aggregate_scientific_disposition"] = "CHANGED"
    _reseal(resealed, "audit_sha256")
    monkeypatch.setattr(cu, "AUDIT_SHA256", resealed["audit_sha256"])
    with pytest.raises(cu.ProductDiscoveryError, match="does not reproduce"):
        cu.validate_candidate_unit_audit(resealed)


def test_historical_stop_state_supports_packet_variants() -> None:
    assert cu._historical_stop_state({"final_stop_state": "A"}) == "A"
    assert cu._historical_stop_state({"frame_stop_state": "B"}) == "B"
    assert cu._historical_stop_state({"runs": [{"stop_state": "C"}]}) == "C"


def test_derive_rejects_wrong_r1_4_worklist_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    worklist = cu.load_decision_resolution_worklist()
    changed = copy.deepcopy(worklist)
    changed["worklist_sha256"] = "0" * 64
    monkeypatch.setattr(cu, "load_decision_resolution_worklist", lambda: changed)
    with pytest.raises(cu.ProductDiscoveryError, match="exact R1.4 worklist"):
        cu.derive_candidate_unit_audit()


def test_derive_rejects_duplicate_audited_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = cu.load_r1_candidate_resolution_manifest()
    records = cu.compile_r1_source_records(manifest)
    target = next(
        record
        for record in records
        if record["frame_id"] in cu.AUDITED_FRAMES and record["round_id"] in cu.AUDITED_ROUNDS
    )
    monkeypatch.setattr(cu, "compile_r1_source_records", lambda _: records + [target])
    with pytest.raises(cu.ProductDiscoveryError, match="capture rows must be unique"):
        cu.derive_candidate_unit_audit()


def test_derive_rejects_historical_stop_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cu, "_historical_stop_state", lambda _: "CONTINUE")
    with pytest.raises(cu.ProductDiscoveryError, match="does not bind mechanical saturation"):
        cu.derive_candidate_unit_audit()
