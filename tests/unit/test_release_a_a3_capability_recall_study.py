from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a3_capability_recall import (
    A3_PREREG_SHA256,
    A3_STUDY_PACKET_ID,
    A3_STUDY_PACKET_SHA256,
    SOURCE_PACKET_SHA256,
    content_digest,
    load_default_a3_capability_recall_preregistration,
    load_default_a3_capability_recall_study,
    validate_a3_capability_recall_study,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(packet: dict[str, Any]) -> None:
    packet["packet_sha256"] = content_digest(packet, exclude="packet_sha256")


def test_a3_study_reports_zero_delta_n_with_companion_rates() -> None:
    packet = load_default_a3_capability_recall_study()
    prereg = load_default_a3_capability_recall_preregistration()

    assert packet["packet_id"] == A3_STUDY_PACKET_ID
    assert packet["packet_sha256"] == A3_STUDY_PACKET_SHA256
    assert content_digest(packet, exclude="packet_sha256") == A3_STUDY_PACKET_SHA256
    assert packet["preregistration_sha256"] == A3_PREREG_SHA256 == prereg["preregistration_sha256"]
    assert packet["n_conventional_terminology"] == 6
    assert packet["n_all_discovery"] == 6
    assert packet["delta_n_capability"] == 0
    assert packet["unique_product_gain"] == 0
    assert packet["unique_capability_offering_ids"] == []
    assert packet["new_canonical_allocations"] == 0
    assert packet["key_result"]["headline"] == "DELTA_N_CAPABILITY"
    assert packet["key_result"]["delta_n_capability"] == 0

    rates = packet["capability_arm_rates"]
    assert rates["frame_id"] == "F6"
    assert rates["raw_candidates"] == 99
    assert rates["false_positive_rate"] == 0.0
    assert rates["unresolved_rate"] == pytest.approx(48 / 99)
    assert rates["duplicate_rate"] == pytest.approx(6 / 99)

    sources = {row["frame_id"]: row["packet_sha256"] for row in packet["evidence_substrate_bindings"]["source_packets"]}
    assert sources == SOURCE_PACKET_SHA256
    assert packet["authority_controls"]["f8_reserved_for_a4_not_executed"] is True
    assert "A4" in packet["next_required_state"]
    assert "not A5" in packet["next_required_state"] or "not A5–A8" in packet["next_required_state"]


def test_a3_study_stratification_marks_empty_classes_not_defensible() -> None:
    packet = load_default_a3_capability_recall_study()
    by_class = {row["stratum_id"]: row for row in packet["stratification"]["by_product_class"]}
    assert by_class["INTEGRATED_SYSTEM"]["defensible"] is True
    assert by_class["INTEGRATED_SYSTEM"]["delta_n_capability"] == 0
    assert by_class["COMPONENT_OR_SUBSYSTEM"]["defensible"] is False
    assert by_class["STANDALONE_SOFTWARE_OR_SERVICE"]["defensible"] is False
    assert packet["stratification"]["by_jurisdiction"][0]["stratum_id"] == "GLOBAL"
    assert packet["stratification"]["by_jurisdiction"][0]["delta_n_capability"] == 0


def test_a3_study_rejects_missing_fields_and_digest_drift() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a3_capability_recall_study({})

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["packet_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="content digest"):
        validate_a3_capability_recall_study(packet)


def test_a3_study_rejects_post_hoc_family_or_increment_edits() -> None:
    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["capability_search_family_set_id"] = "POST_HOC"
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="capability_search_family_set_id"):
        validate_a3_capability_recall_study(packet)

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["delta_n_capability"] = 99
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="delta_n_capability"):
        validate_a3_capability_recall_study(packet)

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["unique_capability_offering_ids"] = ["PRD-INVENTED"]
    packet["all_discovery_offering_ids"] = list(packet["all_discovery_offering_ids"]) + ["PRD-INVENTED"]
    packet["n_all_discovery"] = 7
    packet["delta_n_capability"] = 1
    packet["unique_product_gain"] = 1
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="all_discovery_offering_set_sha256|delta_n_capability"):
        validate_a3_capability_recall_study(packet)


def test_a3_study_rejects_source_digest_and_authority_drift() -> None:
    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["evidence_substrate_bindings"]["source_packets"][5]["packet_sha256"] = "0" * 64
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="source packet digest drift"):
        validate_a3_capability_recall_study(packet)

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["new_canonical_allocations"] = 1
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="new_canonical_allocations must be 0"):
        validate_a3_capability_recall_study(packet)

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["authority_controls"]["rau_not_mutated"] = False
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="rau_not_mutated must be true"):
        validate_a3_capability_recall_study(packet)

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["preregistration_sha256"] = "0" * 64
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="preregistration_sha256"):
        validate_a3_capability_recall_study(packet)

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["capability_arm_rates"]["false_positive_rate"] = 0.99
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="false_positive_rate"):
        validate_a3_capability_recall_study(packet)

    packet = deepcopy(load_default_a3_capability_recall_study())
    packet["key_result"]["headline"] = "F6_FOUND_N_THINGS"
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="DELTA_N_CAPABILITY"):
        validate_a3_capability_recall_study(packet)


def test_load_rejects_study_digest_constant_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "neuroai_workbench.a3_capability_recall.A3_STUDY_PACKET_SHA256",
        "0" * 64,
    )
    with pytest.raises(ProductDiscoveryError, match="A3_STUDY_PACKET_SHA256"):
        load_default_a3_capability_recall_study()


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.__setitem__("packet_id", "WRONG"), "packet_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "CONTROLLED_RESEARCH_PACKET"),
        (lambda p: p.__setitem__("study_id", "WRONG"), "study_id must be"),
        (lambda p: p.__setitem__("preregistration_id", "WRONG"), "preregistration_id"),
        (lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("round_start_known_identity_set_sha256", "0" * 64), "A1 known-identity"),
        (lambda p: p.__setitem__("language_scope_id", "EN_ONLY"), "language_scope_id"),
        (lambda p: p.__setitem__("conventional_search_family_set_id", "WRONG"), "conventional_search_family_set_id"),
        (lambda p: p.__setitem__("f6_query_universe_id", "WRONG"), "f6_query_universe_id"),
        (lambda p: p.__setitem__("f6_query_universe_sha256", "0" * 64), "f6_query_universe_sha256"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("final_known_identity_ids", ["PRD-ONLY"]), "final_known_identity_ids"),
        (lambda p: p.__setitem__("final_known_identity_set_sha256", "0" * 64), "final_known_identity_set_sha256"),
        (lambda p: p.__setitem__("n_conventional_terminology", 0), "n_conventional_terminology"),
        (lambda p: p.__setitem__("n_all_discovery", 0), "n_all_discovery"),
        (lambda p: p.__setitem__("unique_product_gain", 9), "unique_product_gain"),
        (
            lambda p: (
                p.__setitem__("unique_capability_offering_ids", ["PRD-EMOTIV-EPOC-X"]),
                p.__setitem__("delta_n_capability", 0),
                p.__setitem__("unique_product_gain", 0),
            ),
            "unique_capability_offering_ids drift",
        ),
        (lambda p: p.__setitem__("conventional_offering_set_sha256", "0" * 64), "conventional_offering_set_sha256"),
        (
            lambda p: p["evidence_substrate_bindings"].__setitem__("conventional_frame_ids", ["F1"]),
            "conventional_frame_ids must be F1-F5",
        ),
        (
            lambda p: p["evidence_substrate_bindings"].__setitem__("capability_frame_ids", ["F6", "F8"]),
            "capability_frame_ids must be F6 only",
        ),
        (
            lambda p: p["evidence_substrate_bindings"].__setitem__("all_discovery_frame_ids", ["F1"]),
            "all_discovery_frame_ids must be F1-F6",
        ),
        (
            lambda p: p["evidence_substrate_bindings"]["source_packets"].pop(),
            "source_packets must bind exactly F1-F6",
        ),
        (
            lambda p: p["evidence_substrate_bindings"]["source_packets"][0].__setitem__("frame_id", "F99"),
            "unexpected source frame_id",
        ),
        (
            lambda p: (
                p["evidence_substrate_bindings"]["source_packets"].__setitem__(
                    0, p["evidence_substrate_bindings"]["source_packets"][1]
                ),
                p["evidence_substrate_bindings"]["source_packets"].__setitem__(
                    1,
                    deepcopy(load_default_a3_capability_recall_study())["evidence_substrate_bindings"][
                        "source_packets"
                    ][0],
                ),
            ),
            "source_packets must be ordered F1-F6",
        ),
        (lambda p: p["capability_arm_rates"].__setitem__("frame_id", "F1"), "capability_arm_rates.frame_id must be F6"),
        (lambda p: p["key_result"].__setitem__("delta_n_capability", 99), "key_result.delta_n_capability mismatch"),
        (lambda p: p.__setitem__("next_required_state", "done"), "must gate A4 next"),
        (
            lambda p: p.__setitem__(
                "next_required_state",
                "A4 complete; proceed to A5 saturation without exclusion wording",
            ),
            "A5\\+ out of scope",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("post_hoc_family_edits_prohibited", False),
            "post_hoc_family_edits_prohibited must be true",
        ),
    ],
)
def test_a3_study_adversarial_field_drift(mutator, match: str) -> None:
    packet = deepcopy(load_default_a3_capability_recall_study())
    mutator(packet)
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a3_capability_recall_study(packet)
