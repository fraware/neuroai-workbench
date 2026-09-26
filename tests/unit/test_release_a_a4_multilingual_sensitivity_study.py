from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a4_multilingual_sensitivity import (
    A4_PREREG_SHA256,
    A4_STUDY_PACKET_ID,
    A4_STUDY_PACKET_SHA256,
    REQUIRED_STRATUM_IDS,
    SOURCE_PACKET_SHA256,
    content_digest,
    load_default_a4_multilingual_sensitivity_preregistration,
    load_default_a4_multilingual_sensitivity_study,
    validate_a4_multilingual_sensitivity_study,
)
from neuroai_workbench.f8_f10_protocol import LANGUAGE_STRATA_SHA256
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(packet: dict[str, Any]) -> None:
    packet["packet_sha256"] = content_digest(packet, exclude="packet_sha256")


def test_a4_study_reports_zero_delta_n_with_companion_rates() -> None:
    packet = load_default_a4_multilingual_sensitivity_study()
    prereg = load_default_a4_multilingual_sensitivity_preregistration()

    assert packet["packet_id"] == A4_STUDY_PACKET_ID
    assert packet["packet_sha256"] == A4_STUDY_PACKET_SHA256
    assert content_digest(packet, exclude="packet_sha256") == A4_STUDY_PACKET_SHA256
    assert packet["preregistration_sha256"] == A4_PREREG_SHA256 == prereg["preregistration_sha256"]
    assert packet["language_jurisdiction_strata_sha256"] == LANGUAGE_STRATA_SHA256
    assert packet["n_english"] == 6
    assert packet["n_english_plus_native"] == 6
    assert packet["delta_n_multilingual"] == 0
    assert packet["unique_product_gain"] == 0
    assert packet["capability_gain"] == 0
    assert packet["unique_native_offering_ids"] == []
    assert packet["new_canonical_allocations"] == 0
    assert packet["key_result"]["headline"] == "DELTA_N_MULTILINGUAL"
    assert packet["key_result"]["delta_n_multilingual"] == 0

    rates = packet["native_arm_rates"]
    assert rates["frame_id"] == "F8"
    assert rates["raw_candidates"] == 63
    assert rates["false_positive_rate"] == 0.0
    assert rates["unresolved_rate"] == pytest.approx(12 / 63)
    assert rates["duplicate_rate"] == 0.0

    sources = {row["frame_id"]: row["packet_sha256"] for row in packet["evidence_substrate_bindings"]["source_packets"]}
    assert sources == SOURCE_PACKET_SHA256
    assert packet["authority_controls"]["no_post_hoc_language_selection"] is True
    assert packet["substantive_conclusion_change"]["any_substantive_conclusion_changed"] is False
    assert packet["substantive_conclusion_change"]["changed_conclusions"] == []
    assert "A5" in packet["next_required_state"]
    assert "not A6" in packet["next_required_state"] or "not A6–A8" in packet["next_required_state"]


def test_a4_study_stratification_covers_frozen_strata_without_post_hoc() -> None:
    packet = load_default_a4_multilingual_sensitivity_study()
    rows = packet["stratification"]["by_frozen_language_stratum"]
    assert [row["stratum_id"] for row in rows] == list(REQUIRED_STRATUM_IDS)
    assert all(row["delta_j"] == 0 for row in rows)
    assert all(row["native_include_resolved"] == 0 for row in rows)
    assert all(row["defensible"] is False for row in rows)
    assert all(row["reason"] == "NOT_DEFENSIBLE" for row in rows)

    gains = packet["source_class_gain"]
    assert [row["source_class"] for row in gains] == [
        "LOCAL_LANGUAGE_PUBLIC",
        "LOCAL_REGULATORY_OR_INSTITUTIONAL",
        "MANUFACTURER_VENDOR_OFFICIAL",
    ]
    assert all(row["unique_offering_gain"] == 0 for row in gains)


def test_a4_study_rejects_missing_fields_and_digest_drift() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a4_multilingual_sensitivity_study({})

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["packet_sha256"] = "0" * 64
    with pytest.raises(ProductDiscoveryError, match="content digest"):
        validate_a4_multilingual_sensitivity_study(packet)


def test_a4_study_rejects_post_hoc_language_or_increment_edits() -> None:
    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["matched_protocol_set_id"] = "POST_HOC"
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="matched_protocol_set_id"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["delta_n_multilingual"] = 99
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="delta_n_multilingual"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["unique_native_offering_ids"] = ["PRD-INVENTED"]
    packet["english_plus_native_offering_ids"] = list(packet["english_plus_native_offering_ids"]) + ["PRD-INVENTED"]
    packet["n_english_plus_native"] = 7
    packet["delta_n_multilingual"] = 1
    packet["unique_product_gain"] = 1
    packet["substantive_conclusion_change"]["any_substantive_conclusion_changed"] = True
    packet["substantive_conclusion_change"]["changed_conclusions"] = ["invented"]
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="english_plus_native_offering_set_sha256|delta_n_multilingual"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["stratification"]["by_frozen_language_stratum"].append(
        {
            "stratum_id": "LL-POST-HOC",
            "language_code": "xx",
            "defensible": True,
            "n_j_english": 0,
            "n_j_english_plus_native": 1,
            "delta_j": 1,
            "native_raw_candidates": 1,
            "native_include_resolved": 1,
        }
    )
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="by_frozen_language_stratum must cover|unexpected stratum"):
        validate_a4_multilingual_sensitivity_study(packet)


def test_a4_study_rejects_source_digest_and_authority_drift() -> None:
    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["evidence_substrate_bindings"]["source_packets"][6]["packet_sha256"] = "0" * 64
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="source packet digest drift"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["new_canonical_allocations"] = 1
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="new_canonical_allocations must be 0"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["authority_controls"]["no_post_hoc_language_selection"] = False
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="no_post_hoc_language_selection must be true"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["preregistration_sha256"] = "0" * 64
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="preregistration_sha256"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["native_arm_rates"]["false_positive_rate"] = 0.99
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="false_positive_rate"):
        validate_a4_multilingual_sensitivity_study(packet)

    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    packet["substantive_conclusion_change"]["any_substantive_conclusion_changed"] = True
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match="any_substantive_conclusion_changed must be false"):
        validate_a4_multilingual_sensitivity_study(packet)


def test_load_rejects_study_digest_constant_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "neuroai_workbench.a4_multilingual_sensitivity.A4_STUDY_PACKET_SHA256",
        "0" * 64,
    )
    with pytest.raises(ProductDiscoveryError, match="A4_STUDY_PACKET_SHA256"):
        load_default_a4_multilingual_sensitivity_study()


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
        (
            lambda p: p.__setitem__("language_jurisdiction_strata_sha256", "0" * 64),
            "language_jurisdiction_strata_sha256",
        ),
        (lambda p: p.__setitem__("f8_query_universe_id", "WRONG"), "f8_query_universe_id"),
        (lambda p: p.__setitem__("f8_query_universe_sha256", "0" * 64), "f8_query_universe_sha256"),
        (lambda p: p.__setitem__("a3_study_sha256", "0" * 64), "a3_study_sha256"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("final_known_identity_ids", ["PRD-ONLY"]), "final_known_identity_ids"),
        (lambda p: p.__setitem__("final_known_identity_set_sha256", "0" * 64), "final_known_identity_set_sha256"),
        (lambda p: p.__setitem__("n_english", 0), "n_english"),
        (lambda p: p.__setitem__("n_english_plus_native", 0), "n_english_plus_native"),
        (lambda p: p.__setitem__("unique_product_gain", 9), "unique_product_gain"),
        (lambda p: p.__setitem__("capability_gain", 3), "capability_gain must equal"),
        (
            lambda p: (
                p.__setitem__("unique_native_offering_ids", ["PRD-EMOTIV-EPOC-X"]),
                p.__setitem__("delta_n_multilingual", 0),
                p.__setitem__("unique_product_gain", 0),
            ),
            "unique_native_offering_ids drift",
        ),
        (lambda p: p.__setitem__("english_offering_set_sha256", "0" * 64), "english_offering_set_sha256"),
        (
            lambda p: p["evidence_substrate_bindings"].__setitem__("english_frame_ids", ["F1"]),
            "english_frame_ids must be F1-F6",
        ),
        (
            lambda p: p["evidence_substrate_bindings"].__setitem__("native_frame_ids", ["F6", "F8"]),
            "native_frame_ids must be F8 only",
        ),
        (
            lambda p: p["evidence_substrate_bindings"]["source_packets"].pop(),
            "source_packets must bind exactly F1-F6 and F8",
        ),
        (
            lambda p: p["key_result"].__setitem__("headline", "F8_FOUND_N_THINGS"),
            "DELTA_N_MULTILINGUAL",
        ),
        (
            lambda p: p.__setitem__("next_required_state", "done forever"),
            "next_required_state must gate A5",
        ),
    ],
)
def test_a4_study_rejects_binding_drift(mutator: Any, match: str) -> None:
    packet = deepcopy(load_default_a4_multilingual_sensitivity_study())
    mutator(packet)
    _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a4_multilingual_sensitivity_study(packet)
