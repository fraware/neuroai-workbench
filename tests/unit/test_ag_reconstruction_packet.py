from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from neuroai_workbench.a7_population_estimation import VALID_NO_ESTIMATE_OUTCOME
from neuroai_workbench.a8_release_package import A8_CONTRACT_SHA256, A8_PACKAGE_SHA256, N_OBSERVED
from neuroai_workbench.ag_reconstruction import (
    AG_PACKET_BOUNDARY,
    AG_PACKET_ID,
    AG_PACKET_SHA256,
    AG_PROTOCOL_SHA256,
    REQUIRED_HEADLINE_IDS,
    REQUIRED_RECONSTRUCTION_FIELDS,
    build_ag_reconstruction_evidence_table,
    content_digest,
    determine_ag_outcome,
    load_default_ag_reconstruction_packet,
    load_default_ag_reconstruction_protocol,
    reject_adversarial_reconstruction_claims,
    validate_ag_reconstruction_packet,
)
from neuroai_workbench.product_discovery_frames import (
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS,
    ProductDiscoveryError,
)


def _rehash(packet: dict[str, Any]) -> None:
    packet["packet_sha256"] = content_digest(packet, exclude="packet_sha256")


def test_ag_packet_passes_with_full_evidence_table() -> None:
    packet = load_default_ag_reconstruction_packet()
    protocol = load_default_ag_reconstruction_protocol()

    assert packet["packet_id"] == AG_PACKET_ID
    assert packet["packet_sha256"] == AG_PACKET_SHA256
    assert content_digest(packet, exclude="packet_sha256") == AG_PACKET_SHA256
    assert packet["protocol_sha256"] == AG_PROTOCOL_SHA256 == protocol["protocol_sha256"]
    assert packet["a8_package_sha256"] == A8_PACKAGE_SHA256
    assert packet["a8_contract_sha256"] == A8_CONTRACT_SHA256
    assert packet["outcome"] == "PASSED"
    assert packet["n_observed"] == N_OBSERVED
    assert packet["n_estimated"] is None
    assert packet["boundary"] == AG_PACKET_BOUNDARY
    assert packet["next_required_state"] == "RELEASE_A_COMPLETE_AG_PASSED_NO_BCD_AUTHORIZATION"
    assert packet["authority_controls"]["does_not_authorize_release_b_c_d"] is True
    assert packet["key_result"]["a7_fail_closed_outcome"] == VALID_NO_ESTIMATE_OUTCOME

    assert [row["headline_id"] for row in packet["evidence_table"]] == list(REQUIRED_HEADLINE_IDS)
    for row in packet["evidence_table"]:
        assert row["reconstruction_status"] == "RESOLVED"
        assert set(row["fields"]) == set(REQUIRED_RECONSTRUCTION_FIELDS)
        for field_name in REQUIRED_RECONSTRUCTION_FIELDS:
            assert row["fields"][field_name]["resolved"] is True


def test_live_reconstruction_walk_matches_packet() -> None:
    table = build_ag_reconstruction_evidence_table()
    assert determine_ag_outcome(table) == "PASSED"
    packet = load_default_ag_reconstruction_packet()
    assert [row["headline_id"] for row in table] == [row["headline_id"] for row in packet["evidence_table"]]


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_ag_reconstruction_packet({})


def test_load_rejects_constant_digest_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    import neuroai_workbench.ag_reconstruction as mod

    monkeypatch.setattr(mod, "AG_PACKET_SHA256", "0" * 64)
    with pytest.raises(ProductDiscoveryError, match="AG_PACKET_SHA256"):
        mod.load_default_ag_reconstruction_packet()


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.__setitem__("packet_id", "WRONG"), "packet_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "CONTROLLED_RESEARCH_PACKET"),
        (lambda p: p.__setitem__("packet_sha256", "0" * 64), "content digest"),
        (lambda p: p.__setitem__("protocol_sha256", "0" * 64), "protocol_sha256"),
        (lambda p: p.__setitem__("a8_package_sha256", "0" * 64), "a8_package_sha256"),
        (lambda p: p.__setitem__("a8_contract_sha256", "0" * 64), "a8_contract_sha256"),
        (
            lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)),
            "mixed universe rejected",
        ),
        (lambda p: p.__setitem__("n_observed", 7), "n_observed must be"),
        (lambda p: p.__setitem__("n_estimated", 100), "invented n_estimated"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("outcome", "UNPASSED"), "outcome must match live"),
        (
            lambda p: p.__setitem__("next_required_state", "RELEASE_B"),
            "PASSED packet next_required_state must refuse B/C/D",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("does_not_authorize_release_b_c_d", False),
            "Release B/C/D authorization rejected",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("f9_exhaustion_is_not_global_completeness", False),
            "completeness overclaim rejected",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("open_world_saturation_is_not_census", False),
            "completeness overclaim rejected",
        ),
        (
            lambda p: p.__setitem__("estimator_excluded_frame_ids", ["F7", "F9"]),
            "estimator contamination from F7/F9/F11",
        ),
        (
            lambda p: p["evidence_table"][0].__setitem__("reconstruction_status", "UNRESOLVED"),
            "reconstruction_status drift",
        ),
        (
            lambda p: p["evidence_table"][0]["fields"]["counted_object"].__setitem__("resolved", False),
            "resolved flag drift",
        ),
        (
            lambda p: p["evidence_table"].__setitem__(0, {**p["evidence_table"][0], "reconstructed_value": 99}),
            "reconstructed_value drift",
        ),
        (
            lambda p: p["key_result"].__setitem__("n_estimated", 12),
            "key_result must not invent n_estimated",
        ),
    ],
)
def test_ag_packet_rejects_adversarial_mutations(
    mutator: Callable[[dict[str, Any]], None],
    match: str,
) -> None:
    packet = load_default_ag_reconstruction_packet()
    mutator(packet)
    if "packet_sha256" in packet and match != "content digest":
        _rehash(packet)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_ag_reconstruction_packet(packet)


def test_reject_adversarial_helper_covers_core_fail_closed() -> None:
    packet = load_default_ag_reconstruction_packet()
    reject_adversarial_reconstruction_claims(packet)

    bad = dict(packet)
    bad["n_estimated"] = 99
    with pytest.raises(ProductDiscoveryError, match="invented n_estimated"):
        reject_adversarial_reconstruction_claims(bad)

    bad = dict(packet)
    bad["analysis_universe_id"] = "RAU-" + ("0" * 64)
    with pytest.raises(ProductDiscoveryError, match="mixed universe"):
        reject_adversarial_reconstruction_claims(bad)

    bad = dict(packet)
    bad["estimator_excluded_frame_ids"] = ["F7"]
    with pytest.raises(ProductDiscoveryError, match="estimator contamination"):
        reject_adversarial_reconstruction_claims(bad)
    assert set(packet["estimator_excluded_frame_ids"]) == PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS
    assert packet["analysis_universe_id"] == DEFAULT_ANALYSIS_UNIVERSE_ID


def test_missing_upstream_digest_marks_headline_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    import neuroai_workbench.ag_reconstruction as mod

    a8 = mod.load_default_a8_product_population_release_package()
    contract = mod.load_default_a8_package_manifest_contract()
    contract = dict(contract)
    bindings = dict(contract["upstream_digest_bindings"])
    bindings["a7_estimation_report_sha256"] = "0" * 64
    contract["upstream_digest_bindings"] = bindings

    row = mod.reconstruct_headline_evidence("N_ESTIMATED_A_P1", a8_package=a8, contract=contract)
    assert row["reconstruction_status"] == "UNRESOLVED"
    assert determine_ag_outcome([row]) == "UNPASSED"
