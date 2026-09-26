from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from neuroai_workbench.a8_release_package import A8_CONTRACT_SHA256, A8_PACKAGE_SHA256, N_OBSERVED
from neuroai_workbench.ag_reconstruction import (
    AG_PROTOCOL_BOUNDARY,
    AG_PROTOCOL_ID,
    AG_PROTOCOL_SHA256,
    AG_STUDY_ID,
    REQUIRED_HEADLINE_IDS,
    REQUIRED_RECONSTRUCTION_FIELDS,
    ag_freeze_does_not_emit_outcome,
    content_digest,
    load_default_ag_reconstruction_protocol,
    validate_ag_reconstruction_protocol,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(protocol: dict[str, Any]) -> None:
    protocol["protocol_sha256"] = content_digest(protocol, exclude="protocol_sha256")


def test_ag_protocol_binds_a8_before_packet() -> None:
    protocol = load_default_ag_reconstruction_protocol()
    validate_ag_reconstruction_protocol(protocol)

    assert protocol["protocol_id"] == AG_PROTOCOL_ID
    assert protocol["protocol_sha256"] == AG_PROTOCOL_SHA256
    assert content_digest(protocol, exclude="protocol_sha256") == AG_PROTOCOL_SHA256
    assert protocol["study_id"] == AG_STUDY_ID
    assert protocol["boundary"] == AG_PROTOCOL_BOUNDARY
    assert protocol["a8_package_sha256"] == A8_PACKAGE_SHA256
    assert protocol["a8_contract_sha256"] == A8_CONTRACT_SHA256
    assert protocol["n_observed_declared"] == N_OBSERVED
    assert protocol["n_estimated_declared"] is None
    assert tuple(protocol["required_reconstruction_fields"]) == REQUIRED_RECONSTRUCTION_FIELDS
    assert tuple(protocol["required_headline_ids"]) == REQUIRED_HEADLINE_IDS
    assert ag_freeze_does_not_emit_outcome() == "PREREGISTERED_AWAITING_RECONSTRUCTION_PACKET"
    assert protocol["execution_gate"]["freeze_alone_does_not_emit_outcome"] is True
    assert protocol["execution_gate"]["does_not_authorize_release_b_c_d"] is True
    assert protocol["fail_closed_rules"]["invented_n_estimated_is_rejected"] is True
    assert protocol["fail_closed_rules"]["estimator_contamination_f7_f9_f11_is_rejected"] is True


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_ag_reconstruction_protocol({})


def test_load_rejects_constant_digest_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    import neuroai_workbench.ag_reconstruction as mod

    monkeypatch.setattr(mod, "AG_PROTOCOL_SHA256", "0" * 64)
    with pytest.raises(ProductDiscoveryError, match="AG_PROTOCOL_SHA256"):
        mod.load_default_ag_reconstruction_protocol()


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.pop("status", None), "missing fields"),
        (lambda p: p.__setitem__("protocol_id", "WRONG"), "protocol_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda p: p.__setitem__("study_id", "WRONG"), "study_id must be"),
        (lambda p: p.__setitem__("protocol_sha256", "0" * 64), "content digest"),
        (lambda p: p.__setitem__("a8_package_sha256", "0" * 64), "a8_package_sha256"),
        (lambda p: p.__setitem__("a8_contract_sha256", "0" * 64), "a8_contract_sha256"),
        (lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("language_scope_id", "WRONG"), "language_scope_id"),
        (lambda p: p.__setitem__("jurisdiction_scope", "WRONG"), "jurisdiction_scope"),
        (lambda p: p.__setitem__("population_view_id", "A-P8"), "population_view_id must be"),
        (lambda p: p.__setitem__("n_observed_declared", 7), "n_observed_declared must be"),
        (lambda p: p.__setitem__("n_estimated_declared", 100), "must remain null"),
        (lambda p: p.__setitem__("unresolved_candidate_count_declared", 1), "unresolved_candidate_count_declared"),
        (lambda p: p.__setitem__("d4_working_include_declared", 1), "d4_working_include_declared"),
        (lambda p: p.__setitem__("d4_working_total_declared", 1), "d4_working_total_declared"),
        (lambda p: p.__setitem__("observed_offering_ids", ["PRD-X"]), "observed_offering_ids"),
        (
            lambda p: p.__setitem__("required_reconstruction_fields", ["counted_object"]),
            "required_reconstruction_fields",
        ),
        (lambda p: p.__setitem__("required_headline_ids", ["N_OBSERVED_A_P1"]), "required_headline_ids"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (
            lambda p: p["headline_reconstruction_bindings"].pop("FRAME_STOP_STATE_A6", None),
            "headline_reconstruction_bindings key set",
        ),
        (
            lambda p: p["headline_reconstruction_bindings"]["N_OBSERVED_A_P1"].__setitem__(
                "required_fields", ["counted_object"]
            ),
            "must require all twelve reconstruction fields",
        ),
        (
            lambda p: p["fail_closed_rules"].__setitem__("invented_n_estimated_is_rejected", False),
            "invented_n_estimated_is_rejected must be true",
        ),
        (
            lambda p: p["fail_closed_rules"].__setitem__("completeness_overclaim_is_rejected", False),
            "completeness_overclaim_is_rejected must be true",
        ),
        (
            lambda p: p["fail_closed_rules"].__setitem__("mixed_universe_is_rejected", False),
            "mixed_universe_is_rejected must be true",
        ),
        (
            lambda p: p["fail_closed_rules"].__setitem__("estimator_contamination_f7_f9_f11_is_rejected", False),
            "estimator_contamination_f7_f9_f11_is_rejected must be true",
        ),
        (
            lambda p: p["estimator_exclusion_policy"].__setitem__("excluded_frame_ids", ["F7", "F9"]),
            "estimator exclusion must be exactly F7/F9/F11",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("does_not_authorize_release_b_c_d", False),
            "does_not_authorize_release_b_c_d must be true",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("freeze_alone_does_not_emit_outcome", False),
            "freeze_alone_does_not_emit_outcome must be true",
        ),
        (
            lambda p: p.__setitem__("predeclaration_rule", "no field count and no package binding"),
            "predeclaration_rule must require the twelve reconstruction fields",
        ),
        (
            lambda p: p.__setitem__(
                "predeclaration_rule",
                "Bind the twelve reconstruction fields for each required headline. Freeze alone does not authorize Release C or D.",
            ),
            "predeclaration_rule must bind the A8 package",
        ),
        (
            lambda p: p.__setitem__(
                "predeclaration_rule",
                "Bind the exact A8 package digest and the twelve reconstruction fields before emitting any packet.",
            ),
            "predeclaration_rule must refuse authorizing Release B/C/D",
        ),
    ],
)
def test_ag_protocol_rejects_adversarial_mutations(
    mutator: Callable[[dict[str, Any]], None],
    match: str,
) -> None:
    protocol = load_default_ag_reconstruction_protocol()
    mutator(protocol)
    if "protocol_sha256" in protocol and match != "content digest":
        _rehash(protocol)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_ag_reconstruction_protocol(protocol)
