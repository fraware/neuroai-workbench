from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a3_capability_recall import A3_PREREG_SHA256, A3_STUDY_PACKET_SHA256
from neuroai_workbench.a4_multilingual_sensitivity import A4_PREREG_SHA256, A4_STUDY_PACKET_SHA256
from neuroai_workbench.a6_saturation_analysis import A6_PREREG_SHA256, A6_STUDY_PACKET_SHA256
from neuroai_workbench.a7_population_estimation import (
    A7_CAPTURE_HISTORY_SHA256,
    A7_MODEL_SPEC_SHA256,
    A7_STUDY_PACKET_SHA256,
    N_OBSERVED,
)
from neuroai_workbench.a8_release_package import (
    A8_BOUNDARY,
    A8_CONTRACT_ID,
    A8_CONTRACT_SHA256,
    A8_PACKAGE_ID,
    CLAIM_CLASSES,
    FORBIDDEN_CLAIM_CLASSES,
    REQUIRED_PACKAGE_COMPONENTS,
    a8_freeze_does_not_emit_package,
    content_digest,
    frozen_product_identity_registry_sha256,
    frozen_product_registry_sha256,
    load_default_a8_package_manifest_contract,
    validate_a8_package_manifest_contract,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(contract: dict[str, Any]) -> None:
    contract["contract_sha256"] = content_digest(contract, exclude="contract_sha256")


def test_a8_contract_binds_upstream_before_package() -> None:
    contract = load_default_a8_package_manifest_contract()
    validate_a8_package_manifest_contract(contract)

    assert contract["contract_id"] == A8_CONTRACT_ID
    assert contract["contract_sha256"] == A8_CONTRACT_SHA256
    assert content_digest(contract, exclude="contract_sha256") == A8_CONTRACT_SHA256
    assert contract["package_id"] == A8_PACKAGE_ID
    assert contract["boundary"] == A8_BOUNDARY
    assert a8_freeze_does_not_emit_package() == "PREREGISTERED_AWAITING_PACKAGE_MATERIALIZATION"

    bindings = contract["upstream_digest_bindings"]
    assert bindings["product_registry_sha256"] == frozen_product_registry_sha256()
    assert bindings["product_identity_registry_sha256"] == frozen_product_identity_registry_sha256()
    assert bindings["a3_preregistration_sha256"] == A3_PREREG_SHA256
    assert bindings["a3_study_sha256"] == A3_STUDY_PACKET_SHA256
    assert bindings["a4_preregistration_sha256"] == A4_PREREG_SHA256
    assert bindings["a4_study_sha256"] == A4_STUDY_PACKET_SHA256
    assert bindings["a6_preregistration_sha256"] == A6_PREREG_SHA256
    assert bindings["a6_study_sha256"] == A6_STUDY_PACKET_SHA256
    assert bindings["a7_capture_history_sha256"] == A7_CAPTURE_HISTORY_SHA256
    assert bindings["a7_model_specification_sha256"] == A7_MODEL_SPEC_SHA256
    assert bindings["a7_estimation_report_sha256"] == A7_STUDY_PACKET_SHA256
    assert contract["n_observed_declared"] == N_OBSERVED
    assert contract["a7_fail_closed_preservation"]["n_estimated"] is None
    assert tuple(contract["required_package_components"]) == REQUIRED_PACKAGE_COMPONENTS
    assert tuple(contract["claim_classes"]) == CLAIM_CLASSES
    assert tuple(contract["forbidden_claim_classes"]) == FORBIDDEN_CLAIM_CLASSES
    assert contract["execution_gate"]["does_not_start_ag"] is True
    assert contract["execution_gate"]["freeze_alone_does_not_emit_package"] is True


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a8_package_manifest_contract({})


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.pop("status", None), "missing fields"),
        (lambda p: p.__setitem__("contract_id", "WRONG"), "contract_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "must be FROZEN_v1.0"),
        (lambda p: p.__setitem__("package_id", "WRONG"), "package_id must be"),
        (lambda p: p.__setitem__("contract_sha256", "0" * 64), "content digest"),
        (lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("observed_offering_set_sha256", "0" * 64), "A1 known-identity"),
        (lambda p: p.__setitem__("n_observed_declared", 7), "n_observed_declared must be"),
        (lambda p: p.__setitem__("population_view_id", "A-P8"), "population_view_id must be"),
        (lambda p: p.__setitem__("frame_register_version", "WRONG"), "frame_register_version"),
        (lambda p: p.__setitem__("frame_register_blob_sha", "0" * 40), "frame_register_blob_sha"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (
            lambda p: p["upstream_digest_bindings"].__setitem__("a7_estimation_report_sha256", "0" * 64),
            "upstream_digest_bindings.a7_estimation_report_sha256",
        ),
        (
            lambda p: p["upstream_digest_bindings"].__setitem__("a3_study_sha256", "0" * 64),
            "upstream_digest_bindings.a3_study_sha256",
        ),
        (
            lambda p: p.__setitem__("required_package_components", list(REQUIRED_PACKAGE_COMPONENTS[:-1])),
            "required_package_components",
        ),
        (lambda p: p.__setitem__("claim_classes", ["OBSERVED_FACT"]), "claim_classes"),
        (
            lambda p: p.__setitem__("forbidden_claim_classes", ["MARKET_SHARE"]),
            "forbidden_claim_classes",
        ),
        (
            lambda p: p["headline_count_rules"].__setitem__("every_headline_must_name_denominator", False),
            "headline_count_rules.every_headline_must_name_denominator",
        ),
        (
            lambda p: p["headline_count_rules"].__setitem__("primary_population_view_id", "A-P8"),
            "headline_count_rules.primary_population_view_id",
        ),
        (
            lambda p: p["headline_count_rules"].__setitem__("primary_denominator_label", "wrong"),
            "headline_count_rules.primary_denominator_label",
        ),
        (
            lambda p: p["d4_binding_policy"].__setitem__("reference_standard_id", "WRONG"),
            "d4_binding_policy.reference_standard_id",
        ),
        (
            lambda p: p["d4_binding_policy"].__setitem__("reference_standard_version", "9.9"),
            "d4_binding_policy.reference_standard_version",
        ),
        (
            lambda p: p["d4_binding_policy"].__setitem__("bind_version_and_working_summary_only", False),
            "d4_binding_policy.bind_version_and_working_summary_only",
        ),
        (
            lambda p: p["d4_binding_policy"].__setitem__("do_not_invent_d4_case_results", False),
            "d4_binding_policy.do_not_invent_d4_case_results",
        ),
        (
            lambda p: p["d4_binding_policy"]["working_distribution"].__setitem__("EXCLUDE", 0),
            "d4_binding_policy.working_distribution.EXCLUDE",
        ),
        (
            lambda p: p["a7_fail_closed_preservation"].__setitem__("n_observed", 1),
            "a7_fail_closed_preservation.n_observed",
        ),
        (
            lambda p: p["a7_fail_closed_preservation"].__setitem__("n_estimated", 100),
            "n_estimated null",
        ),
        (
            lambda p: p["a7_fail_closed_preservation"].__setitem__("estimation_outcome", "OK"),
            "a7_fail_closed_preservation.estimation_outcome",
        ),
        (
            lambda p: p["a7_fail_closed_preservation"].__setitem__("fail_closed_outcome", "WRONG"),
            "a7_fail_closed_preservation.fail_closed_outcome",
        ),
        (
            lambda p: p["a7_fail_closed_preservation"].__setitem__(
                "observed_count_reported_separately_from_estimate", False
            ),
            "observed_count_reported_separately_from_estimate",
        ),
        (
            lambda p: p["a7_fail_closed_preservation"].__setitem__("forbid_invented_n_estimated", False),
            "forbid_invented_n_estimated",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("does_not_start_ag", False),
            "execution_gate.does_not_start_ag",
        ),
        (
            lambda p: p["execution_gate"].__setitem__("preserves_a7_fail_closed", False),
            "execution_gate.preserves_a7_fail_closed",
        ),
        (
            lambda p: p.__setitem__("predeclaration_rule", "no claim separation and no A-G mention"),
            "claim-class",
        ),
        (
            lambda p: p.__setitem__(
                "predeclaration_rule",
                "Bind claim-class separations before package materialization. Freeze alone does not start A-G.",
            ),
            "denominator",
        ),
        (
            lambda p: p.__setitem__(
                "predeclaration_rule",
                "Bind claim-class separations and denominators before package materialization.",
            ),
            "A-G",
        ),
    ],
)
def test_a8_contract_rejects_semantic_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    contract = deepcopy(load_default_a8_package_manifest_contract())
    mutator(contract)
    if match != "content digest":
        _rehash(contract)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a8_package_manifest_contract(contract)
