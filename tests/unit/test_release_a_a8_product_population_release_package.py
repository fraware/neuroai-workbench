from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from neuroai_workbench.a8_release_package import (
    A8_CONTRACT_SHA256,
    A8_PACKAGE_BOUNDARY,
    A8_PACKAGE_ID,
    A8_PACKAGE_SHA256,
    FORBIDDEN_CLAIM_CLASSES,
    N_OBSERVED,
    UNRESOLVED_CANDIDATE_COUNT,
    UNRESOLVED_REGISTER_SHA256,
    _require_bool,
    _require_int,
    _require_list,
    _require_mapping,
    _require_str,
    content_digest,
    load_default_a8_package_manifest_contract,
    load_default_a8_product_population_release_package,
    validate_a8_product_population_release_package,
)
from neuroai_workbench.product_discovery_frames import ProductDiscoveryError


def _rehash(package: dict[str, Any]) -> None:
    package["package_sha256"] = content_digest(package, exclude="package_sha256")


def test_a8_package_binds_contract_and_preserves_a7_fail_closed() -> None:
    package = load_default_a8_product_population_release_package()
    contract = load_default_a8_package_manifest_contract()

    assert package["package_id"] == A8_PACKAGE_ID
    assert package["package_sha256"] == A8_PACKAGE_SHA256
    assert content_digest(package, exclude="package_sha256") == A8_PACKAGE_SHA256
    assert package["contract_sha256"] == A8_CONTRACT_SHA256 == contract["contract_sha256"]
    assert package["boundary"] == A8_PACKAGE_BOUNDARY
    assert package["n_observed"] == N_OBSERVED
    assert package["n_estimated"] is None
    assert package["components"]["a7_population_estimation_report"]["n_estimated"] is None
    assert package["components"]["explicit_unknown_unresolved_register"]["unresolved_candidate_count"] == (
        UNRESOLVED_CANDIDATE_COUNT
    )
    assert package["components"]["explicit_unknown_unresolved_register"]["unresolved_register_sha256"] == (
        UNRESOLVED_REGISTER_SHA256
    )
    assert tuple(package["forbidden_claims_absent"]) == FORBIDDEN_CLAIM_CLASSES
    assert package["next_required_state"] == "A-G_RELEASE_A_RECONSTRUCTION_REVIEW"
    assert package["authority_controls"]["does_not_start_ag"] is True
    assert package["key_result"]["n_estimated"] is None


def test_a8_package_headlines_name_denominators() -> None:
    package = load_default_a8_product_population_release_package()
    for headline in package["headline_counts"]:
        assert headline["denominator_label"]
        assert headline["population_view_id"]
        assert headline["claim_class"] not in FORBIDDEN_CLAIM_CLASSES
    n_obs = next(h for h in package["headline_counts"] if h["headline_id"] == "N_OBSERVED_A_P1")
    n_est = next(h for h in package["headline_counts"] if h["headline_id"] == "N_ESTIMATED_A_P1")
    assert n_obs["value"] == 6
    assert n_est["value"] is None


def test_helpers_reject_non_objects() -> None:
    with pytest.raises(ProductDiscoveryError, match="missing fields"):
        validate_a8_product_population_release_package({})
    with pytest.raises(ProductDiscoveryError, match="must be an object"):
        _require_mapping([], "x")
    with pytest.raises(ProductDiscoveryError, match="must be an array"):
        _require_list({}, "x")
    with pytest.raises(ProductDiscoveryError, match="must be a non-empty string"):
        _require_str("", "x")
    with pytest.raises(ProductDiscoveryError, match="must be a boolean"):
        _require_bool("true", "x")
    with pytest.raises(ProductDiscoveryError, match="must be an integer"):
        _require_int(True, "x")


def test_load_rejects_constant_digest_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    import neuroai_workbench.a8_release_package as mod

    monkeypatch.setattr(mod, "A8_PACKAGE_SHA256", "0" * 64)
    with pytest.raises(ProductDiscoveryError, match="A8_PACKAGE_SHA256"):
        mod.load_default_a8_product_population_release_package()
    monkeypatch.setattr(mod, "A8_CONTRACT_SHA256", "0" * 64)
    with pytest.raises(ProductDiscoveryError, match="A8_CONTRACT_SHA256"):
        mod.load_default_a8_package_manifest_contract()


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.__setitem__("package_id", "WRONG"), "package_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "CONTROLLED_RESEARCH_PACKET"),
        (lambda p: p.__setitem__("contract_id", "WRONG"), "contract_id must be"),
        (lambda p: p.__setitem__("package_sha256", "0" * 64), "content digest"),
        (lambda p: p.__setitem__("contract_sha256", "0" * 64), "contract_sha256"),
        (lambda p: p.__setitem__("analysis_universe_id", "RAU-" + ("0" * 64)), "frozen A2 analysis universe"),
        (lambda p: p.__setitem__("world_time_cutoff", "2020-01-01"), "world_time_cutoff"),
        (lambda p: p.__setitem__("knowledge_time_cutoff", "2020-01-01T00:00:00Z"), "knowledge_time_cutoff"),
        (lambda p: p.__setitem__("a2_checkpoint_id", "WRONG"), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("a2_checkpoint_sha256", "0" * 64), "frozen A2 checkpoint"),
        (lambda p: p.__setitem__("observed_offering_set_sha256", "0" * 64), "A1 known-identity"),
        (lambda p: p.__setitem__("observed_offering_ids", ["PRD-X"]), "observed_offering_ids"),
        (lambda p: p.__setitem__("population_view_id", "A-P8"), "population_view_id must be"),
        (lambda p: p.__setitem__("n_observed", 7), "n_observed must be"),
        (lambda p: p.__setitem__("n_estimated", 100), "must not invent n_estimated"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("next_required_state", "RELEASE_B"), "A-G_RELEASE_A_RECONSTRUCTION_REVIEW"),
        (lambda p: p.__setitem__("components", {}), "components key set"),
        (
            lambda p: p["components"]["product_registry"].__setitem__("resource_sha256", "0" * 64),
            "product_registry.resource_sha256",
        ),
        (
            lambda p: p["components"]["product_registry"].__setitem__("identity_registry_sha256", "0" * 64),
            "product_registry.identity_registry_sha256",
        ),
        (
            lambda p: p["components"]["product_registry"].__setitem__("row_count", 1),
            "product_registry counts",
        ),
        (
            lambda p: p["components"]["d4_reference_standard_summary"].__setitem__("reference_standard_id", "WRONG"),
            "d4 reference_standard_id",
        ),
        (
            lambda p: p["components"]["d4_reference_standard_summary"].__setitem__("reference_standard_version", "9.9"),
            "d4 reference_standard_version",
        ),
        (
            lambda p: p["components"]["d4_reference_standard_summary"]["working_distribution"].__setitem__(
                "INCLUDE", 1
            ),
            "d4 working_distribution.INCLUDE",
        ),
        (
            lambda p: p["components"]["discovery_frame_register"].__setitem__("frame_register_version", "WRONG"),
            "frame_register_version",
        ),
        (
            lambda p: p["components"]["discovery_frame_register"].__setitem__("frame_register_blob_sha", "0" * 40),
            "frame_register_blob_sha",
        ),
        (
            lambda p: p["components"]["discovery_frame_register"].__setitem__("f9_completion_ledger_sha256", "0" * 64),
            "f9_completion_ledger_sha256",
        ),
        (
            lambda p: p["components"]["a3_capability_first_recall_study"].__setitem__("packet_sha256", "0" * 64),
            "a3 study digest",
        ),
        (
            lambda p: p["components"]["a3_capability_first_recall_study"].__setitem__(
                "preregistration_sha256", "0" * 64
            ),
            "a3 preregistration digest",
        ),
        (
            lambda p: p["components"]["a3_capability_first_recall_study"].__setitem__("delta_n_capability", 1),
            "delta_n_capability",
        ),
        (
            lambda p: p["components"]["a4_multilingual_coverage_sensitivity_report"].__setitem__(
                "packet_sha256", "0" * 64
            ),
            "a4 study digest",
        ),
        (
            lambda p: p["components"]["a4_multilingual_coverage_sensitivity_report"].__setitem__(
                "preregistration_sha256", "0" * 64
            ),
            "a4 preregistration digest",
        ),
        (
            lambda p: p["components"]["a4_multilingual_coverage_sensitivity_report"].__setitem__(
                "language_jurisdiction_strata_sha256", "0" * 64
            ),
            "language strata digest",
        ),
        (
            lambda p: p["components"]["a4_multilingual_coverage_sensitivity_report"].__setitem__(
                "delta_n_multilingual", 1
            ),
            "delta_n_multilingual",
        ),
        (
            lambda p: p["components"]["a6_coverage_saturation_report"].__setitem__("packet_sha256", "0" * 64),
            "a6 study digest",
        ),
        (
            lambda p: p["components"]["a6_coverage_saturation_report"].__setitem__("preregistration_sha256", "0" * 64),
            "a6 preregistration digest",
        ),
        (
            lambda p: p["components"]["a6_coverage_saturation_report"].__setitem__(
                "final_stop_state", "GLOBAL_COMPLETE"
            ),
            "a6 final_stop_state",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__("packet_sha256", "0" * 64),
            "a7 report digest",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__(
                "capture_history_sha256", "0" * 64
            ),
            "a7 capture_history digest",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__(
                "model_specification_sha256", "0" * 64
            ),
            "a7 model_specification digest",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__(
                "eligible_capture_records_sha256", "0" * 64
            ),
            "a7 eligible capture digest",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__("n_observed", 1),
            "a7 component n_observed",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__("n_estimated", 50),
            "must not invent n_estimated",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__(
                "estimation_outcome", "POINT_ESTIMATE"
            ),
            "FAIL_CLOSED",
        ),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__("fail_closed_outcome", "WRONG"),
            "a7 fail_closed_outcome",
        ),
        (
            lambda p: p["components"]["analytical_workbook_figure_data"]["tables"].__setitem__(
                "observed_offerings_by_form_factor", []
            ),
            "must be non-empty",
        ),
        (
            lambda p: p["components"]["analytical_workbook_figure_data"]["tables"][
                "observed_offerings_by_form_factor"
            ].__setitem__(0, {"value": "X", "count": 1}),
            "must name denominator and population view",
        ),
        (
            lambda p: p["components"]["source_coverage_uncertainty_register"].__setitem__("entries", []),
            "major residual uncertainties",
        ),
        (
            lambda p: p["components"]["explicit_unknown_unresolved_register"].__setitem__(
                "unresolved_candidate_count", 1
            ),
            "unresolved_candidate_count",
        ),
        (
            lambda p: p["components"]["explicit_unknown_unresolved_register"].__setitem__(
                "unresolved_register_sha256", "0" * 64
            ),
            "unresolved_register_sha256",
        ),
        (
            lambda p: p["components"]["explicit_unknown_unresolved_register"].__setitem__(
                "candidates", p["components"]["explicit_unknown_unresolved_register"]["candidates"][:10]
            ),
            "unresolved candidates length",
        ),
        (
            lambda p: p["components"]["explicit_unknown_unresolved_register"]["candidates"].__setitem__(
                0,
                {
                    **p["components"]["explicit_unknown_unresolved_register"]["candidates"][0],
                    "candidate_key": "TAMPERED",
                },
            ),
            "unresolved candidates content digest",
        ),
        (
            lambda p: p.__setitem__("headline_counts", []),
            "headline_counts must be non-empty",
        ),
        (
            lambda p: p["headline_counts"].__setitem__(0, {**p["headline_counts"][0], "claim_class": "MARKET_SHARE"}),
            "forbidden claim class",
        ),
        (
            lambda p: p["headline_counts"].__setitem__(0, {**p["headline_counts"][0], "claim_class": "NOT_A_CLASS"}),
            "permitted claim class",
        ),
        (
            lambda p: next(h for h in p["headline_counts"] if h["headline_id"] == "N_OBSERVED_A_P1").__setitem__(
                "value", 99
            ),
            "N_OBSERVED headline value",
        ),
        (
            lambda p: next(h for h in p["headline_counts"] if h["headline_id"] == "N_ESTIMATED_A_P1").__setitem__(
                "value", 99
            ),
            "N_ESTIMATED headline must remain null",
        ),
        (
            lambda p: p.__setitem__("forbidden_claims_absent", list(FORBIDDEN_CLAIM_CLASSES[:-1])),
            "forbidden_claims_absent",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("does_not_start_ag", False),
            "authority_controls.does_not_start_ag",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("does_not_publish_market_share", False),
            "does_not_publish_market_share",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("preserves_a7_fail_closed", False),
            "preserves_a7_fail_closed",
        ),
        (lambda p: p["key_result"].__setitem__("n_estimated", 12), "must not invent n_estimated"),
        (lambda p: p["key_result"].__setitem__("n_observed", 1), "key_result.n_observed"),
        (lambda p: p["key_result"].__setitem__("estimation_outcome", "OK"), "key_result.estimation_outcome"),
        (lambda p: p["key_result"].__setitem__("population_view_id", "A-P8"), "key_result.population_view_id"),
        (lambda p: p["key_result"].__setitem__("package_complete", False), "package_complete"),
    ],
)
def test_a8_package_rejects_semantic_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    package = deepcopy(load_default_a8_product_population_release_package())
    mutator(package)
    if match != "content digest":
        _rehash(package)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a8_product_population_release_package(package)
