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


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.__setitem__("package_id", "WRONG"), "package_id must be"),
        (lambda p: p.__setitem__("status", "DRAFT"), "CONTROLLED_RESEARCH_PACKET"),
        (lambda p: p.__setitem__("package_sha256", "0" * 64), "content digest"),
        (lambda p: p.__setitem__("contract_sha256", "0" * 64), "contract_sha256"),
        (lambda p: p.__setitem__("n_observed", 7), "n_observed must be"),
        (lambda p: p.__setitem__("n_estimated", 100), "must not invent n_estimated"),
        (lambda p: p.__setitem__("boundary", "drift"), "boundary text drift"),
        (lambda p: p.__setitem__("next_required_state", "RELEASE_B"), "A-G_RELEASE_A_RECONSTRUCTION_REVIEW"),
        (
            lambda p: p["components"]["a7_population_estimation_report"].__setitem__("n_estimated", 50),
            "must not invent n_estimated",
        ),
        (
            lambda p: p["components"]["a3_capability_first_recall_study"].__setitem__("packet_sha256", "0" * 64),
            "a3 study digest",
        ),
        (
            lambda p: p["components"]["explicit_unknown_unresolved_register"].__setitem__(
                "unresolved_candidate_count", 1
            ),
            "unresolved_candidate_count",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("does_not_start_ag", False),
            "authority_controls.does_not_start_ag",
        ),
        (
            lambda p: p["authority_controls"].__setitem__("does_not_publish_market_share", False),
            "does_not_publish_market_share",
        ),
        (lambda p: p["key_result"].__setitem__("n_estimated", 12), "must not invent n_estimated"),
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
    ],
)
def test_a8_package_rejects_semantic_drift(mutator: Callable[[dict[str, Any]], Any], match: str) -> None:
    package = deepcopy(load_default_a8_product_population_release_package())
    mutator(package)
    if match != "content digest":
        _rehash(package)
    with pytest.raises(ProductDiscoveryError, match=match):
        validate_a8_product_population_release_package(package)
