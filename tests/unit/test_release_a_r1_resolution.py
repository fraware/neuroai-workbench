from __future__ import annotations

import copy

import pytest

from neuroai_workbench import release_a_r1_resolution as r1
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


EXPECTED_A_P1_IDS = [
    "PRD-EMOTIV-EPOC-X",
    "PRD-MUSE-S-ATHENA",
    "PRD-NEXTSENSE-SMARTBUDS",
    "PRD-SYNCHRON-STENTRODE",
]


def _reseal(value: dict[str, object], field: str) -> None:
    value[field] = r1.artifact_sha256(value, digest_field=field)


def _synthetic_capture(
    *,
    capture_id: str,
    candidate_key: str,
    outcome: str = "UNRESOLVED_IDENTITY",
    canonical_offering_id: str | None = None,
    frame_id: str = "F1",
) -> dict[str, object]:
    return {
        "capture_id": capture_id,
        "source_packet_id": "PACKET-TEST",
        "frame_id": frame_id,
        "round_id": "R1",
        "query_or_seed_id": "Q1",
        "query_family": "QF",
        "source_class": "PUBLIC",
        "candidate_key": candidate_key,
        "canonical_offering_id": canonical_offering_id,
        "source_observation_ref": f"OBS-{capture_id}",
        "language": "en",
        "jurisdiction": "GLOBAL",
        "outcome": outcome,
        "observed_at": "2026-09-24T12:00:00Z",
        "analysis_universe_id": r1.DEFAULT_ANALYSIS_UNIVERSE_ID,
        "population_view_id": "A-P1",
        "world_time_alignment": "UNRESOLVED"
        if canonical_offering_id is None
        else "EVIDENCE_SUPPORTS_AT_OR_BEFORE_CUTOFF",
        "world_time_support_ref": None,
    }


def test_default_r1_resolution_state_reconstructs() -> None:
    state = r1.validate_default_r1_resolution_state()

    assert state["analysis_universe_id"] == r1.DEFAULT_ANALYSIS_UNIVERSE_ID
    assert state["a_p1_identity_ids"] == EXPECTED_A_P1_IDS
    assert state["n_observed"] == 4

    accounting = state["candidate_resolution_accounting"]
    assert accounting == {
        "raw_capture_row_count": 1335,
        "unique_raw_candidate_key_count": 1119,
        "governed_candidate_cluster_count": 1105,
        "unresolved_identity_capture_row_count": 691,
        "unresolved_scope_boundary_capture_row_count": 15,
        "abstain_capture_row_count": 445,
        "borderline_capture_row_count": 15,
        "failed_inaccessible_capture_row_count": 71,
        "include_resolved_capture_row_count": 75,
        "exclude_capture_row_count": 38,
        "unresolved_clusters_capable_of_changing_a_p1_membership": 1061,
        "unresolved_clusters_capable_of_changing_a3_increment": 52,
        "unresolved_clusters_capable_of_changing_a4_increment": 63,
        "unresolved_clusters_capable_of_changing_marginal_yield_stop": 334,
        "cardinality_bounded_unresolved_cluster_count": 591,
        "unbounded_source_or_abstention_barrier_cluster_count": 470,
        "cardinality_bounded_clusters_capable_of_changing_marginal_yield_stop": 109,
        "unbounded_barrier_clusters_capable_of_changing_marginal_yield_stop": 225,
        "cardinality_bounded_clusters_capable_of_changing_a3_increment": 13,
        "unbounded_barrier_clusters_capable_of_changing_a3_increment": 39,
        "cardinality_bounded_clusters_capable_of_changing_a4_increment": 12,
        "unbounded_barrier_clusters_capable_of_changing_a4_increment": 51,
    }


def test_r1_registry_preserves_flow_and_modius_as_nonqualifying_unresolved() -> None:
    registry = r1.load_r1_product_registry()
    rows = {row["canonical_entity_id"]: row for row in registry["rows"]}

    for canonical_id in ("PRD-FLOW-FL-100", "PRD-MODIUS-SPERO"):
        assert rows[canonical_id]["currentness_state"] == "UNRESOLVED"
        assert rows[canonical_id]["lifecycle_state"] == "UNRESOLVED"
        assert canonical_id not in r1.derive_r1_a_p1_identity_ids(registry)

    denominator = r1.load_r1_denominator_control()
    declared = {item["canonical_entity_id"]: item for item in denominator["nonqualifying_canonical_offerings"]}
    assert set(declared) == {"PRD-FLOW-FL-100", "PRD-MODIUS-SPERO"}
    assert all(item["disposition"] == "PRESERVE_NONQUALIFYING_UNRESOLVED" for item in declared.values())


def test_r1_registry_rejects_universe_drift_and_identity_allocation() -> None:
    registry = r1.load_r1_product_registry()

    wrong_cutoff = copy.deepcopy(registry)
    wrong_cutoff["metadata"]["knowledge_time_cutoff"] = "2026-09-24T21:00:00Z"
    with pytest.raises(ProductDiscoveryError, match="knowledge_time_cutoff drift"):
        r1.validate_r1_product_registry(wrong_cutoff)

    extra_identity = copy.deepcopy(registry)
    extra = copy.deepcopy(extra_identity["rows"][0])
    extra["canonical_entity_id"] = "PRD-UNAUTHORIZED-NEW"
    extra["product_offering_id"] = "PRD-UNAUTHORIZED-NEW"
    extra["registry_row_id"] = "PRR-" + "0" * 64
    extra_identity["rows"].append(extra)
    extra_identity["metadata"]["row_count"] = len(extra_identity["rows"])
    with pytest.raises(ProductDiscoveryError):
        r1.validate_r1_product_registry(extra_identity)


def test_denominator_rejects_hardcoded_or_misaligned_population_count() -> None:
    registry = r1.load_r1_product_registry()
    packet = r1.load_r1_denominator_control()

    wrong_count = copy.deepcopy(packet)
    wrong_count["n_observed"] = 6
    _reseal(wrong_count, "packet_sha256")
    with pytest.raises(ProductDiscoveryError, match="n_observed"):
        r1.validate_r1_denominator_control(wrong_count, registry)

    wrong_ids = copy.deepcopy(packet)
    wrong_ids["qualifying_offering_ids"] = list(wrong_ids["qualifying_offering_ids"]) + ["PRD-FLOW-FL-100"]
    _reseal(wrong_ids, "packet_sha256")
    with pytest.raises(ProductDiscoveryError, match="machine-derived"):
        r1.validate_r1_denominator_control(wrong_ids, registry)


def test_candidate_normalization_clusters_only_exact_normalized_keys_or_canonical_ids() -> None:
    left = _synthetic_capture(capture_id="PDC-A", candidate_key="OpenBCI::Galea")
    same = _synthetic_capture(capture_id="PDC-B", candidate_key="  openbci::galea  ")
    alias = _synthetic_capture(capture_id="PDC-C", candidate_key="OpenBCI::Galea Headset")

    assert r1.candidate_cluster_id(left) == r1.candidate_cluster_id(same)
    assert r1.candidate_cluster_id(left) != r1.candidate_cluster_id(alias)
    assert r1.normalized_candidate_label("OpenBCI::  Galea  ") == "Galea"
    assert r1.developer_or_organization_label("OpenBCI::Galea") == "OpenBCI"
    assert r1.developer_or_organization_label("F1-R1-CAT-X::seed-locator") is None

    canonical_a = _synthetic_capture(
        capture_id="PDC-D",
        candidate_key="Vendor::Name One",
        outcome="INCLUDE_RESOLVED",
        canonical_offering_id="PRD-X",
    )
    canonical_b = _synthetic_capture(
        capture_id="PDC-E",
        candidate_key="Different Label",
        outcome="INCLUDE_RESOLVED",
        canonical_offering_id="PRD-X",
    )
    assert r1.candidate_cluster_id(canonical_a) == r1.candidate_cluster_id(canonical_b)


def test_source_record_derivation_is_conservative_for_unresolved_rows() -> None:
    unresolved = r1.derive_r1_source_record(
        _synthetic_capture(capture_id="PDC-U", candidate_key="Vendor::Candidate", frame_id="F6")
    )
    assert unresolved["identity_resolution_state"] == "UNRESOLVED"
    assert unresolved["adjudication_state"] == "IDENTITY_REVIEW_REQUIRED"
    assert unresolved["evidence_sufficiency_state"] == "INSUFFICIENT_FOR_TERMINAL_PRODUCT_ACCOUNTING"
    assert unresolved["could_change_a_p1_membership"] is True
    assert unresolved["could_change_a3_increment"] is True
    assert unresolved["could_change_marginal_yield_stop"] is True
    assert unresolved["cardinality_bounded_candidate_object"] is True
    assert unresolved["source_or_abstention_barrier"] is False
    assert unresolved["uncertainty_cardinality_class"] == "ONE_OBJECT_UPPER_BOUND"

    barrier = r1.derive_r1_source_record(
        _synthetic_capture(
            capture_id="PDC-BARRIER",
            candidate_key="Vendor::Catalogue Surface",
            outcome="FAILED_INACCESSIBLE",
            frame_id="F6",
        )
    )
    assert barrier["cardinality_bounded_candidate_object"] is False
    assert barrier["source_or_abstention_barrier"] is True
    assert barrier["uncertainty_cardinality_class"] == "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER"

    excluded = r1.derive_r1_source_record(
        _synthetic_capture(capture_id="PDC-X", candidate_key="Vendor::Excluded", outcome="EXCLUDE")
    )
    assert excluded["identity_resolution_state"] == "NOT_REQUIRED_EXCLUDED"
    assert excluded["scope_boundary_disposition_state"] == "EXCLUDED"
    assert excluded["could_change_a_p1_membership"] is False


def test_cluster_builder_keeps_noncanonical_uncertainty_and_terminal_exclusions_distinct() -> None:
    raw = [
        r1.derive_r1_source_record(_synthetic_capture(capture_id="PDC-1", candidate_key="Vendor::Candidate")),
        r1.derive_r1_source_record(
            _synthetic_capture(capture_id="PDC-2", candidate_key="vendor::candidate", outcome="ABSTAIN")
        ),
        r1.derive_r1_source_record(
            _synthetic_capture(capture_id="PDC-3", candidate_key="Vendor::Excluded", outcome="EXCLUDE")
        ),
    ]
    clusters = r1.build_r1_candidate_clusters(raw)
    by_state = {cluster["cluster_state"]: cluster for cluster in clusters}

    unresolved = by_state["UNRESOLVED_IDENTITY"]
    assert unresolved["noncanonical_cluster"] is True
    assert unresolved["outcomes"] == ["ABSTAIN", "UNRESOLVED_IDENTITY"]
    assert unresolved["could_change_a_p1_membership"] is True

    terminal = by_state["TERMINAL_EXCLUDED"]
    assert terminal["identity_resolution_state"] == "NOT_REQUIRED_EXCLUDED"
    assert terminal["could_change_a_p1_membership"] is False
    assert terminal["uncertainty_cardinality_class"] == "TERMINAL"


def test_manifest_binds_all_22_source_packets_and_every_capture_exactly_once() -> None:
    manifest = r1.load_r1_candidate_resolution_manifest()
    assert len(manifest["source_packet_bindings"]) == 22
    assert len(manifest["source_ledger_shards"]) == 10

    records = r1.compile_r1_source_records(manifest)
    capture_ids = [record["capture_id"] for record in records]
    assert len(capture_ids) == 1335
    assert len(set(capture_ids)) == 1335
    assert set(record["frame_id"] for record in records) == {
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F6",
        "F8",
        "F9",
        "F10",
        "F11",
    }


def test_manifest_rejects_source_packet_binding_and_accounting_drift() -> None:
    manifest = r1.load_r1_candidate_resolution_manifest()

    bad_binding = copy.deepcopy(manifest)
    bad_binding["source_packet_bindings"][0]["source_packet_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="source_packet_bindings"):
        r1.compile_r1_source_records(bad_binding)

    omitted_packet = copy.deepcopy(manifest)
    omitted_packet["source_packet_bindings"].pop()
    with pytest.raises(ProductDiscoveryError, match="complete immutable A2 capture-packet universe"):
        r1.compile_r1_source_records(omitted_packet)

    bad_accounting = copy.deepcopy(manifest)
    bad_accounting["accounting"]["raw_capture_row_count"] = 1334
    _reseal(bad_accounting, "ledger_manifest_sha256")
    with pytest.raises(ProductDiscoveryError, match="accounting"):
        r1.validate_r1_candidate_resolution_ledger(bad_accounting)


def test_cluster_artifact_is_frozen_and_noncanonical_clusters_do_not_allocate_identity() -> None:
    manifest = r1.load_r1_candidate_resolution_manifest()
    cluster_binding = manifest["cluster_ledger_binding"]
    cluster_artifact = r1._load(r1.DISCOVERY_RESOURCE_PACKAGE, cluster_binding["resource"])

    assert cluster_artifact["candidate_cluster_count"] == 1105
    clusters = cluster_artifact["clusters"]
    noncanonical = [cluster for cluster in clusters if cluster["noncanonical_cluster"]]
    canonical = [cluster for cluster in clusters if not cluster["noncanonical_cluster"]]

    assert len(canonical) == 6
    assert all(cluster["canonical_offering_id"] for cluster in canonical)
    assert all(cluster["canonical_offering_id"] is None for cluster in noncanonical)
    assert sum(bool(cluster["could_change_a_p1_membership"]) for cluster in clusters) == 1061
    assert sum(cluster["uncertainty_cardinality_class"] == "ONE_OBJECT_UPPER_BOUND" for cluster in clusters) == 591
    assert (
        sum(
            cluster["uncertainty_cardinality_class"] == "UNBOUNDED_SOURCE_OR_ABSTENTION_BARRIER" for cluster in clusters
        )
        == 470
    )
