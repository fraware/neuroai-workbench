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
    LABEL_DOMAIN_SEPARATOR,
    MEMBERSHIP_DOMAIN_SEPARATOR,
    BenchmarkContractError,
    keyed_commitment,
    validate_prediction_rows,
)

EXPECTED_G1_DISPOSITION_ID = "HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1"
EXPECTED_G1_DISPOSITION_SHA256 = "ed6489fe1085b5aec1b594970dd1c574b57bd6bbd25a659643e9bd1b7b72d8ef"


def test_packaged_public_contracts_validate_and_remain_draft() -> None:
    contracts = load_all_packaged_public_contracts()
    assert set(contracts) == {"PATENT", "PRODUCT"}
    for kind, contract in contracts.items():
        assert contract["benchmark_kind"] == kind
        assert contract["state"] == "DRAFT_UNFROZEN"
        assert contract["g1_gate_state"] == "APPROVED_REFERENCE_PROVIDED"
        assert contract["g1_disposition_id"] == EXPECTED_G1_DISPOSITION_ID
        assert contract["g1_disposition_sha256"] == EXPECTED_G1_DISPOSITION_SHA256
        assert contract["g2_passed"] is False
        assert contract["canonical_s2_authority"] is False
        assert contract["publication_authority"] is False
        assert contract["assessment_effect"] == "NONE"
        assert contract["membership_commitment"] is None
        assert contract["label_commitment"] is None
        assert contract["private_membership_location"] == "S3_CONTROLLED"
        assert contract["private_labels_location"] == "S3_CONTROLLED"
        assert contract["commitment_scheme"] == "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1"


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


def test_load_packaged_public_contract_rejects_unknown_kind() -> None:
    with pytest.raises(BenchmarkContractError, match="Unsupported packaged contract kind"):
        load_packaged_public_contract("NOT_A_KIND")


def test_packaged_contract_rejects_nested_oracle_key_before_schema() -> None:
    contract = dict(load_packaged_public_contract("PATENT"))
    strata = list(contract["required_strata"])
    strata.append({"nonce": "deadbeef"})  # type: ignore[arg-type]
    contract["required_strata"] = strata
    with pytest.raises(BenchmarkContractError, match="prohibited field"):
        validate_packaged_public_contract(contract)


def test_packaged_contract_rejects_top_level_leakage_key() -> None:
    contract = dict(load_packaged_public_contract("PRODUCT"))
    contract["licensed_bytes"] = "x"
    with pytest.raises(BenchmarkContractError, match="prohibited field"):
        validate_packaged_public_contract(contract)


def test_synthetic_fixtures_preserve_untrusted_draft_authority() -> None:
    fixtures = load_synthetic_fixtures()
    assert {fixture["benchmark_kind"] for fixture in fixtures} == {"PATENT", "PRODUCT"}
    for fixture in fixtures:
        assert fixture["synthetic"] is True
        assert fixture["benchmark_status"] == "SYNTHETIC_TEST_ONLY"
        assert fixture["adjudication"]["basis"] == "HUMAN_SYNTHETIC_ANNOTATIONS"
        assert all(output["authority"] == "UNTRUSTED_DRAFT_ONLY" for output in fixture["model_outputs"])


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


def test_synthetic_fixture_rejects_non_synthetic_flag() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["synthetic"] = False
    with pytest.raises(BenchmarkContractError, match="explicitly synthetic"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_invalid_kind_and_annotations() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["benchmark_kind"] = "patent"
    with pytest.raises(BenchmarkContractError, match="benchmark_kind"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["human_annotations"] = []
    with pytest.raises(BenchmarkContractError, match="human_annotations"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["human_annotations"] = ["not-an-object"]
    with pytest.raises(BenchmarkContractError, match="must be an object"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["human_annotations"] = [{"annotator_id": "", "label": "NEGATIVE"}]
    with pytest.raises(BenchmarkContractError, match="annotator_id"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["human_annotations"] = [{"annotator_id": "A", "label": ""}]
    with pytest.raises(BenchmarkContractError, match="non-empty label"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_rejects_bad_adjudication_and_outputs() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["adjudication"] = "missing"
    with pytest.raises(BenchmarkContractError, match="adjudication object"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["adjudication"] = {"status": "AGREE", "basis": "MODEL", "final_label": None}
    with pytest.raises(BenchmarkContractError, match="human-annotation based"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["model_outputs"] = "bad"
    with pytest.raises(BenchmarkContractError, match="model_outputs must be a list"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["model_outputs"] = ["bad"]
    with pytest.raises(BenchmarkContractError, match="must be an object"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["model_outputs"] = [{"authority": "UNTRUSTED_DRAFT_ONLY", "model_id": "", "prediction": "POSITIVE"}]
    with pytest.raises(BenchmarkContractError, match="requires model_id"):
        validate_synthetic_fixture(fixture)

    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["model_outputs"] = [{"authority": "UNTRUSTED_DRAFT_ONLY", "model_id": "M", "prediction": ""}]
    with pytest.raises(BenchmarkContractError, match="requires prediction"):
        validate_synthetic_fixture(fixture)


def test_synthetic_fixture_accepts_output_without_probability() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
    fixture["model_outputs"] = [
        {
            "model_id": "SYNTHETIC-MODEL-B",
            "prediction": "ABSTAIN",
            "authority": "UNTRUSTED_DRAFT_ONLY",
        }
    ]
    validate_synthetic_fixture(fixture)


def test_synthetic_fixture_accepts_empty_model_outputs() -> None:
    fixture = copy.deepcopy(load_synthetic_fixtures()[0])
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
                    "prediction": "NEGATIVE",
                    "metadata": {"nested": {"ground_truth": "POSITIVE"}},
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
