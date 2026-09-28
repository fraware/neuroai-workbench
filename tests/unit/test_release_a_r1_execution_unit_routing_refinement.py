from __future__ import annotations

import copy

import pytest

import neuroai_workbench.release_a_r1_execution_unit_routing_refinement as refinement
from neuroai_workbench.release_a_r1_execution_unit_routing import (
    LITERATURE_RECORD_EXTRACTION,
    MIXED_OR_UNRESOLVED_UNIT_REVIEW,
    SOURCE_SURFACE_RESOLUTION,
    load_execution_unit_routing,
    route_execution_record_id,
    validate_route_execution_record,
)
from neuroai_workbench.release_a_r1_resolution import (
    compile_r1_source_records,
    load_r1_candidate_resolution_manifest,
)


def _reseal(value: dict[str, object], digest_field: str) -> None:
    value[digest_field] = refinement.artifact_sha256(
        value,
        digest_field=digest_field,
    )


def _source_records_by_capture_id() -> dict[str, dict[str, object]]:
    manifest = load_r1_candidate_resolution_manifest()
    rows = compile_r1_source_records(manifest)
    return {str(row["capture_id"]): row for row in rows}


def test_frozen_refinement_reconstructs_exactly() -> None:
    rule = refinement.load_routing_refinement_rule()
    checkpoint = refinement.load_routing_refinement()

    assert rule["rule_sha256"] == refinement.RULE_SHA256
    assert checkpoint["checkpoint_sha256"] == refinement.CHECKPOINT_SHA256
    assert checkpoint["work_item_count"] == 270
    assert checkpoint["capture_count"] == 389
    assert checkpoint["changed_work_item_count"] == 13
    assert checkpoint["changed_capture_count"] == 17
    assert checkpoint["work_item_counts_by_route"] == {
        "EMPIRICAL_CANDIDATE_ADJUDICATION": 76,
        "SOURCE_SURFACE_RESOLUTION": 171,
        "LITERATURE_RECORD_EXTRACTION": 21,
        "MIXED_OR_UNRESOLVED_UNIT_REVIEW": 0,
        "A_P1_TEMPORAL_STATE_REVIEW": 2,
    }
    assert checkpoint["capture_counts_by_route"] == {
        "EMPIRICAL_CANDIDATE_ADJUDICATION": 142,
        "SOURCE_SURFACE_RESOLUTION": 226,
        "LITERATURE_RECORD_EXTRACTION": 21,
        "MIXED_OR_UNRESOLVED_UNIT_REVIEW": 0,
        "A_P1_TEMPORAL_STATE_REVIEW": 0,
    }
    assert checkpoint["refined_predecessor_subtype_counts"] == {
        refinement.ACTUAL_LITERATURE_RECORD: {"work_items": 21, "captures": 21},
        refinement.EMPTY_LITERATURE_QUERY_SENTINEL: {
            "work_items": 11,
            "captures": 11,
        },
        refinement.EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL: {
            "work_items": 2,
            "captures": 6,
        },
        refinement.UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE: {
            "work_items": 0,
            "captures": 0,
        },
    }


def test_only_empty_query_sentinels_change_r1_6_route() -> None:
    predecessor = load_execution_unit_routing()
    checkpoint = refinement.load_routing_refinement()
    predecessor_by_id = {
        str(item["work_item_id"]): item for item in predecessor["route_table"]
    }

    changed = [
        item
        for item in checkpoint["route_table"]
        if item["execution_route"] != item["r1_6_execution_route"]
    ]
    assert len(changed) == 13
    assert sum(len(item["capture_ids"]) for item in changed) == 17

    for item in checkpoint["route_table"]:
        prior = predecessor_by_id[str(item["work_item_id"])]
        assert item["capture_ids"] == prior["capture_ids"]
        assert item["frame_rounds"] == prior["frame_rounds"]
        assert item["selection_reasons"] == prior["selection_reasons"]
        assert item["r1_6_execution_route"] == prior["execution_route"]

        if item in changed:
            assert prior["execution_route"] == LITERATURE_RECORD_EXTRACTION
            assert item["execution_route"] == SOURCE_SURFACE_RESOLUTION
            assert item["execution_subtype"] in {
                refinement.EMPTY_LITERATURE_QUERY_SENTINEL,
                refinement.EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL,
            }
        elif prior["execution_route"] == LITERATURE_RECORD_EXTRACTION:
            assert item["execution_subtype"] == refinement.ACTUAL_LITERATURE_RECORD
            assert item["execution_route"] == LITERATURE_RECORD_EXTRACTION
        else:
            assert item["execution_subtype"] == refinement.UNCHANGED_FROM_R1_6
            assert item["execution_route"] == prior["execution_route"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("lit-42505450", refinement.ACTUAL_LITERATURE_RECORD),
        ("LIT-42505450", refinement.ACTUAL_LITERATURE_RECORD),
        ("empty-europepmc", refinement.EMPTY_LITERATURE_QUERY_SENTINEL),
        (
            "empty-europepmc-sentinel",
            refinement.EMPTY_LITERATURE_QUERY_SENTINEL,
        ),
        (
            "empty-trial-lit",
            refinement.EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL,
        ),
        (
            "empty-trial-lit-v2",
            refinement.EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL,
        ),
        (
            "plausible-product-looking-name",
            refinement.UNRESOLVED_OR_MIXED_LITERATURE_PROBE_SUBTYPE,
        ),
    ],
)
def test_literature_probe_subtype_is_explicit_and_fail_closed(
    label: str,
    expected: str,
) -> None:
    rule = refinement.load_routing_refinement_rule()
    assert refinement._literature_probe_subtype(label, rule) == expected


@pytest.mark.parametrize(
    ("subtypes", "expected"),
    [
        (
            [refinement.ACTUAL_LITERATURE_RECORD],
            LITERATURE_RECORD_EXTRACTION,
        ),
        (
            [refinement.EMPTY_LITERATURE_QUERY_SENTINEL],
            SOURCE_SURFACE_RESOLUTION,
        ),
        (
            [refinement.EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL],
            SOURCE_SURFACE_RESOLUTION,
        ),
        (
            [
                refinement.ACTUAL_LITERATURE_RECORD,
                refinement.EMPTY_LITERATURE_QUERY_SENTINEL,
            ],
            MIXED_OR_UNRESOLVED_UNIT_REVIEW,
        ),
        ([], MIXED_OR_UNRESOLVED_UNIT_REVIEW),
    ],
)
def test_refined_route_for_subtypes_fails_closed(
    subtypes: list[str],
    expected: str,
) -> None:
    assert refinement._refined_route_for_subtypes(subtypes) == expected


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_workbench_main_commit", "0" * 40, "source_workbench_main_commit drift"),
        ("r1_6_rule_sha256", "0" * 64, "r1_6_rule_sha256 drift"),
        ("r1_6_routing_sha256", "0" * 64, "r1_6_routing_sha256 drift"),
        (
            "expected_work_item_counts_by_route",
            {},
            "expected_work_item_counts_by_route drift",
        ),
        (
            "expected_capture_counts_by_route",
            {},
            "expected_capture_counts_by_route drift",
        ),
        (
            "expected_refined_predecessor_subtype_counts",
            {},
            "expected_refined_predecessor_subtype_counts drift",
        ),
    ],
)
def test_rule_rejects_upstream_and_count_drift(
    field: str,
    value: object,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = refinement.load_routing_refinement_rule()
    changed = copy.deepcopy(rule)
    changed[field] = value
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(refinement, "RULE_SHA256", changed["rule_sha256"])

    with pytest.raises(refinement.ProductDiscoveryError, match=message):
        refinement.validate_routing_refinement_rule(changed)


def test_rule_rejects_refinement_semantic_relaxation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = refinement.load_routing_refinement_rule()
    changed = copy.deepcopy(rule)
    changed["refinement_contract"][
        "empty_query_sentinel_route"
    ] = LITERATURE_RECORD_EXTRACTION
    _reseal(changed, "rule_sha256")
    monkeypatch.setattr(refinement, "RULE_SHA256", changed["rule_sha256"])

    with pytest.raises(refinement.ProductDiscoveryError, match="refinement contract drift"):
        refinement.validate_routing_refinement_rule(changed)


def test_checkpoint_digest_and_reproduction_guards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint = refinement.load_routing_refinement()

    broken = copy.deepcopy(checkpoint)
    broken["changed_capture_count"] = 18
    with pytest.raises(refinement.ProductDiscoveryError, match="checkpoint digest mismatch"):
        refinement.validate_routing_refinement(broken)

    resealed = copy.deepcopy(checkpoint)
    resealed["aggregate_disposition"] = "CHANGED"
    _reseal(resealed, "checkpoint_sha256")
    monkeypatch.setattr(
        refinement,
        "CHECKPOINT_SHA256",
        resealed["checkpoint_sha256"],
    )
    with pytest.raises(refinement.ProductDiscoveryError, match="does not reproduce"):
        refinement.validate_routing_refinement(resealed)


def test_derive_rejects_missing_refined_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = load_r1_candidate_resolution_manifest()
    records = compile_r1_source_records(manifest)
    predecessor = load_execution_unit_routing()
    literature_item = next(
        item
        for item in predecessor["route_table"]
        if item["execution_route"] == LITERATURE_RECORD_EXTRACTION
    )
    missing_capture = str(literature_item["capture_ids"][0])
    reduced = [
        record for record in records if str(record["capture_id"]) != missing_capture
    ]
    monkeypatch.setattr(
        refinement,
        "compile_r1_source_records",
        lambda _: reduced,
    )

    with pytest.raises(refinement.ProductDiscoveryError, match="unknown capture ID"):
        refinement.derive_routing_refinement()


def test_empty_trial_sentinel_preserves_three_round_capture_identity() -> None:
    checkpoint = refinement.load_routing_refinement()
    rows = [
        item
        for item in checkpoint["route_table"]
        if item["execution_subtype"]
        == refinement.EMPTY_TRIAL_PUBLICATION_QUERY_SENTINEL
    ]

    assert len(rows) == 2
    for item in rows:
        assert item["execution_route"] == SOURCE_SURFACE_RESOLUTION
        assert len(item["capture_ids"]) == 3
        assert item["frame_rounds"] == ["F11:R1", "F11:R2", "F11:R3"]


def test_refined_sentinel_accepts_source_query_execution_contract() -> None:
    checkpoint = refinement.load_routing_refinement()
    item = next(
        row
        for row in checkpoint["route_table"]
        if row["execution_subtype"]
        == refinement.EMPTY_LITERATURE_QUERY_SENTINEL
    )
    source_records = _source_records_by_capture_id()

    evidence = []
    for index, capture_id_raw in enumerate(item["capture_ids"], start=1):
        capture_id = str(capture_id_raw)
        source_record = source_records[capture_id]
        evidence.append(
            {
                "evidence_ref": f"R161-EVIDENCE-{index:04d}",
                "capture_id": capture_id,
                "query_or_seed_id": source_record["query_or_seed_id"],
                "source_locator": "https://example.invalid/query",
                "knowledge_observed_at": "2026-09-28T00:00:00Z",
                "sha256": f"{index:064x}",
                "evidence_role": "SOURCE_QUERY_EXECUTION",
                "supported_propositions": ["SOURCE_QUERY_ZERO_LEADS"],
            }
        )

    record: dict[str, object] = {
        "execution_record_id": "",
        "work_item_id": item["work_item_id"],
        "execution_route": SOURCE_SURFACE_RESOLUTION,
        "completion_state": "SOURCE_QUERY_INTERROGATED_ZERO_EXTRACTED_LEADS",
        "review_state": "MACHINE_PROVISIONAL",
        "reviewer_id": None,
        "evidence": evidence,
        "extracted_leads": [],
        "source_scope_exhausted": False,
        "finite_cardinality_upper_bound": None,
        "global_source_exhaustion_claimed": False,
        "covered_capture_ids": list(item["capture_ids"]),
        "work_item_completion_claimed": True,
    }
    record["execution_record_id"] = route_execution_record_id(record)

    validate_route_execution_record(record, routing_checkpoint=checkpoint)
