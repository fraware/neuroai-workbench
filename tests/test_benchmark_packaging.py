"""Tests for packaged PRE-G2 public benchmark resources on the selected lineage."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import patch

import pytest

from neuroai_workbench.benchmark_packaging import (
    load_all_packaged_public_contracts,
    load_packaged_public_contract,
    load_synthetic_fixtures,
    validate_packaged_public_contract,
    validate_synthetic_fixture,
)
from neuroai_workbench.evaluation_benchmarks import (
    BOUNDARY_DISPOSITIONS,
    LABEL_DOMAIN_SEPARATOR,
    MEMBERSHIP_DOMAIN_SEPARATOR,
    REQUIRED_BOUNDARY_DISPOSITIONS,
    REQUIRED_STRATA,
    BenchmarkContractError,
    keyed_commitment,
    validate_prediction_rows,
)


def test_packaged_public_contracts_validate_and_remain_draft() -> None:
    contracts = load_all_packaged_public_contracts()
    assert set(contracts) == {"PATENT", "PRODUCT"}
    for kind, contract in contracts.items():
        assert contract["schema_version"] == "0.2"
        assert contract["benchmark_kind"] == kind
        assert contract["state"] == "DRAFT_UNFROZEN"
        assert contract["g1_gate_state"] == "APPROVED_REFERENCE_PROVIDED"
        assert contract["g2_passed"] is False
        assert contract["canonical_s2_authority"] is False
        assert contract["publication_authority"] is False
        assert contract["assessment_effect"] == "NONE"
        assert contract["membership_commitment"] is None
        assert contract["label_commitment"] is None
        assert contract["commitment_scheme"] == "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1"
        assert set(contract["required_strata"]) == REQUIRED_STRATA[kind]
        semantics = contract["boundary_semantics"]
        assert set(semantics["allowed_dispositions"]) == BOUNDARY_DISPOSITIONS
        assert set(semantics["required_g2_coverage_dispositions"]) == REQUIRED_BOUNDARY_DISPOSITIONS
        assert semantics["binary_projection"]["projection_id"] == "D1_INCLUDE_EXCLUDE_BINARY_V1"


def test_packaged_patent_strata_no_longer_conflate_boundary_outcomes() -> None:
    contract = load_packaged_public_contract("PATENT")
    assert not {"POSITIVE", "NEGATIVE", "BORDERLINE"} & set(contract["required_strata"])
    assert set(contract["boundary_semantics"]["required_g2_coverage_dispositions"]) == {
        "INCLUDE",
        "EXCLUDE",
        "BORDERLINE",
    }


def test_packaged_contract_rejects_authority_escalation() -> None:
    contract = load_packaged_public_contract("PATENT")
    contract["g2_passed"] = True
    with pytest.raises(BenchmarkContractError, match="g2_passed"):
        validate_packaged_public_contract(contract)


def test_packaged_contract_rejects_unknown_kind() -> None:
    contract = load_packaged_public_contract("PATENT")
    contract["benchmark_kind"] = "UNKNOWN"
    with pytest.raises(BenchmarkContractError, match="benchmark_kind"):
        validate_packaged_public_contract(contract)


def test_packaged_contract_rejects_schema_violations_with_path() -> None:
    contract = load_packaged_public_contract("PRODUCT")
    contract["double_label_subset_required"] = False
    with pytest.raises(BenchmarkContractError, match=r"\$\.double_label_subset_required"):
        validate_packaged_public_contract(contract)


def test_packaged_contract_rejects_boundary_semantics_schema_drift() -> None:
    contract = load_packaged_public_contract("PATENT")
    contract["boundary_semantics"]["allowed_dispositions"] = ["INCLUDE", "EXCLUDE"]
    with pytest.raises(BenchmarkContractError, match=r"\$\.boundary_semantics"):
        validate_packaged_public_contract(contract)


def test_load_packaged_public_contract_rejects_unknown_kind() -> None:
    with pytest.raises(BenchmarkContractError, match="Unsupported packaged contract kind"):
        load_packaged_public_contract("NOT_A_KIND")


def test_packaged_contract_rejects_nested_oracle_key_before_schema() -> None:
    contract = dict(load_packaged_public_contract("PATENT"))
    semantics = dict(contract["boundary_semantics"])
    semantics["reviewer_dispositions"] = ["INCLUDE"]
    contract["boundary_semantics"] = semantics
    with pytest.raises(BenchmarkContractError, match="prohibited field"):
        validate_packaged_public_contract(contract)


def test_packaged_contract_rejects_top_level_leakage_key() -> None:
    contract = dict(load_packaged_public_contract("PRODUCT"))
    contract["licensed_bytes"] = "x"
    with pytest.raises(BenchmarkContractError, match="prohibited field"):
        validate_packaged_public_contract(contract)


def test_synthetic_fixtures_preserve_four_way_human_semantics_and_untrusted_model_authority() -> None:
    fixtures = load_synthetic_fixtures()
    assert {fixture["benchmark_kind"] for fixture in fixtures} == {"PATENT", "PRODUCT"}
    assert {fixture["adjudication"]["final_boundary_disposition"] for fixture in fixtures} >= {
        None,
        "ABSTAIN",
        "BORDERLINE",
        "INCLUDE",
    }
    for fixture in fixtures:
        assert fixture["synthetic"] is True
        assert fixture["benchmark_status"] == "SYNTHETIC_TEST_ONLY"
        assert fixture["adjudication"]["basis"] == "HUMAN_SYNTHETIC_ANNOTATIONS"
        assert all(
            annotation["boundary_disposition"] in BOUNDARY_DISPOSITIONS for annotation in fixture["human_annotations"]
        )
        assert all(output["authority"] == "UNTRUSTED_DRAFT_ONLY" for output in fixture["model_outputs"])
        assert all(output["boundary_prediction"] in BOUNDARY_DISPOSITIONS for output in fixture["model_outputs"])


def test_synthetic_fixture_rejects_model_authority_elevation() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["model_outputs"][0]["authority"] = "GOLD_LABEL_AUTHORITY"
    with pytest.raises(BenchmarkContractError, match="untrusted drafts"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_freeze_claim() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["benchmark_status"] = "FROZEN"
    with pytest.raises(BenchmarkContractError, match="cannot claim frozen"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_non_synthetic_flag_and_bad_kind() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["synthetic"] = False
    with pytest.raises(BenchmarkContractError, match="explicitly synthetic"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["benchmark_kind"] = "patent"
    with pytest.raises(BenchmarkContractError, match="benchmark_kind"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_legacy_human_label_and_bad_annotation_shape() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["human_annotations"][0] = {"annotator_id": "A", "label": "ABSTAIN"}
    with pytest.raises(BenchmarkContractError, match="legacy label"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["human_annotations"] = ["bad"]
    with pytest.raises(BenchmarkContractError, match="must be an object"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["human_annotations"][0]["annotator_id"] = ""
    with pytest.raises(BenchmarkContractError, match="annotator_id"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_inconsistent_agreement_and_unresolved_disagreement() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["human_annotations"][0]["boundary_disposition"] = "INCLUDE"
    with pytest.raises(BenchmarkContractError, match="AGREE"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["human_annotations"][1]["boundary_disposition"] = "EXCLUDE"
    with pytest.raises(BenchmarkContractError, match="unresolved disagreement"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_bad_adjudication_and_missing_rationale() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["adjudication"] = "missing"
    with pytest.raises(BenchmarkContractError, match="adjudication object"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["adjudication"]["basis"] = "MODEL"
    with pytest.raises(BenchmarkContractError, match="human-annotation based"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["adjudication"]["rationale"] = ""
    with pytest.raises(BenchmarkContractError, match="recorded rationale"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_legacy_or_invalid_model_routing() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    output = fixture["model_outputs"][0]
    output["prediction"] = output.pop("boundary_prediction")
    with pytest.raises(BenchmarkContractError, match="legacy prediction"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["model_outputs"][0]["boundary_prediction"] = "POSITIVE"
    with pytest.raises(BenchmarkContractError, match="four-way domain"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_accepts_empty_model_outputs() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[1])
    fixture["model_outputs"] = []
    validate_synthetic_fixture(fixture)


def test_load_synthetic_fixtures_rejects_non_list_payload() -> None:
    with patch(
        "neuroai_workbench.benchmark_packaging._resource_json",
        return_value={"not": "a list"},
    ):
        with pytest.raises(BenchmarkContractError, match="non-empty list"):
            load_synthetic_fixtures()


def test_load_synthetic_fixtures_rejects_non_object_entries() -> None:
    with patch(
        "neuroai_workbench.benchmark_packaging._resource_json",
        return_value=["not-an-object"],
    ):
        with pytest.raises(BenchmarkContractError, match="must be an object"):
            load_synthetic_fixtures()


def test_synthetic_model_prediction_rows_reject_oracle_fields() -> None:
    with pytest.raises(BenchmarkContractError, match="prohibited oracle field"):
        validate_prediction_rows(
            [
                {
                    "item_id": "SYN-LEAK",
                    "boundary_prediction": "EXCLUDE",
                    "metadata": {"nested": {"ground_truth": "INCLUDE"}},
                }
            ]
        )


def test_packaging_does_not_regress_domain_separated_hmac_lineage() -> None:
    payload: dict[str, Any] = {"items": ["S3-002", "S3-001"]}
    key = b"k" * 32
    membership = keyed_commitment(payload, key, domain_separator=MEMBERSHIP_DOMAIN_SEPARATOR)
    label = keyed_commitment(payload, key, domain_separator=LABEL_DOMAIN_SEPARATOR)
    assert membership != label
    contract = load_packaged_public_contract("PATENT")
    assert contract["commitment_scheme"] == "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1"
