from __future__ import annotations

import copy

import pytest

from neuroai_workbench.evaluation_benchmarks import (
    ADJUDICATION_STATES,
    REQUIRED_STRATA,
    BenchmarkContractError,
    keyed_commitment,
    score_predictions,
    validate_prediction_rows,
    validate_public_benchmark_contract,
)


def _contract(kind: str = "PATENT") -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "benchmark_id": f"PRE_G2_{kind}_V0_1",
        "benchmark_kind": kind,
        "state": "DRAFT_UNFROZEN",
        "g1_gate_state": "NOT_APPROVED",
        "g1_disposition_id": None,
        "g1_disposition_sha256": None,
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
        "private_membership_location": "S3_CONTROLLED",
        "private_labels_location": "S3_CONTROLLED",
        "commitment_scheme": "HMAC_SHA256_CANONICAL_JSON_V1",
        "membership_commitment": None,
        "label_commitment": None,
        "required_strata": sorted(REQUIRED_STRATA[kind]),
        "double_label_subset_required": True,
        "adjudication_states": sorted(ADJUDICATION_STATES),
    }


def test_public_contract_accepts_complete_patent_and_product_scaffolds() -> None:
    validate_public_benchmark_contract(_contract("PATENT"))
    validate_public_benchmark_contract(_contract("PRODUCT"))


def test_public_contract_rejects_missing_required_stratum() -> None:
    contract = _contract("PATENT")
    strata = contract["required_strata"]
    assert isinstance(strata, list)
    strata.remove("MULTILINGUAL")
    with pytest.raises(BenchmarkContractError, match="MULTILINGUAL"):
        validate_public_benchmark_contract(contract)


def test_public_contract_rejects_authority_escalation_and_private_payload_fields() -> None:
    contract = _contract()
    contract["g2_passed"] = True
    with pytest.raises(BenchmarkContractError, match="g2_passed"):
        validate_public_benchmark_contract(contract)

    contract = _contract()
    contract["items"] = [{"item_id": "PRIVATE"}]
    with pytest.raises(BenchmarkContractError, match="unsupported fields"):
        validate_public_benchmark_contract(contract)


def test_frozen_contract_requires_approved_g1_reference_and_opaque_commitments() -> None:
    contract = _contract()
    contract["state"] = "FROZEN_COMMITMENTS_ONLY"
    contract["membership_commitment"] = "a" * 64
    contract["label_commitment"] = "b" * 64
    with pytest.raises(BenchmarkContractError, match="approved G1 disposition reference"):
        validate_public_benchmark_contract(contract)

    contract["g1_gate_state"] = "APPROVED_REFERENCE_PROVIDED"
    contract["g1_disposition_id"] = "G1-DISPOSITION-SYNTHETIC"
    contract["g1_disposition_sha256"] = "c" * 64
    validate_public_benchmark_contract(contract)


def test_approved_g1_reference_requires_exact_disposition_binding() -> None:
    contract = _contract()
    contract["g1_gate_state"] = "APPROVED_REFERENCE_PROVIDED"
    with pytest.raises(BenchmarkContractError, match="g1_disposition_id"):
        validate_public_benchmark_contract(contract)

    contract["g1_disposition_id"] = "G1-DISPOSITION-SYNTHETIC"
    contract["g1_disposition_sha256"] = "not-a-digest"
    with pytest.raises(BenchmarkContractError, match="g1_disposition_sha256"):
        validate_public_benchmark_contract(contract)


def test_keyed_commitment_is_deterministic_keyed_and_payload_bound() -> None:
    payload = {"items": ["S3-002", "S3-001"], "labels": {"S3-001": "POSITIVE"}}
    key = b"k" * 32
    first = keyed_commitment(payload, key)
    assert first == keyed_commitment(copy.deepcopy(payload), key)
    assert first != keyed_commitment(payload, b"z" * 32)

    changed = copy.deepcopy(payload)
    changed["items"].append("S3-003")
    assert first != keyed_commitment(changed, key)
    with pytest.raises(BenchmarkContractError, match="at least 32 bytes"):
        keyed_commitment(payload, b"short")


def test_prediction_leakage_guard_is_recursive() -> None:
    rows = [
        {
            "item_id": "SYN-1",
            "prediction": "POSITIVE",
            "metadata": {"nested": {"ground_truth": "POSITIVE"}},
        }
    ]
    with pytest.raises(BenchmarkContractError, match="prohibited oracle field"):
        validate_prediction_rows(rows)


def test_unresolved_disagreement_is_preserved_and_not_scored() -> None:
    gold = [
        {
            "item_id": "SYN-U",
            "gold_label": "UNRESOLVED",
            "adjudication_state": "DISAGREE_UNADJUDICATED",
            "strata": ["BORDERLINE"],
        }
    ]
    result = score_predictions([], gold)
    assert result["unresolved_gold_count"] == 1
    assert result["overall"]["scoreable_count"] == 0


def test_scoring_counts_abstention_and_missing_positive_as_effective_false_negative() -> None:
    gold = [
        {
            "item_id": "SYN-P1",
            "gold_label": "POSITIVE",
            "adjudication_state": "AGREE",
            "strata": ["POSITIVE"],
            "language": "en",
            "jurisdiction": "US",
            "text_availability": "FULL",
        },
        {
            "item_id": "SYN-P2",
            "gold_label": "POSITIVE",
            "adjudication_state": "ADJUDICATED",
            "strata": ["BORDERLINE"],
            "language": "fr",
            "jurisdiction": "FR",
            "text_availability": "SHORT",
        },
        {
            "item_id": "SYN-P3",
            "gold_label": "POSITIVE",
            "adjudication_state": "AGREE",
            "strata": ["GRAY_CAPABILITY"],
            "language": "de",
            "jurisdiction": "DE",
            "text_availability": "FULL",
        },
        {
            "item_id": "SYN-N1",
            "gold_label": "NEGATIVE",
            "adjudication_state": "AGREE",
            "strata": ["NEGATIVE"],
            "language": "en",
            "jurisdiction": "US",
            "text_availability": "FULL",
        },
    ]
    predictions = [
        {"item_id": "SYN-P1", "prediction": "POSITIVE", "probability_positive": 0.9},
        {"item_id": "SYN-P2", "prediction": "ABSTAIN", "probability_positive": 0.5},
        {"item_id": "SYN-N1", "prediction": "NEGATIVE", "probability_positive": 0.1},
    ]

    result = score_predictions(predictions, gold)
    overall = result["overall"]
    assert overall["coverage"] == 0.5
    assert overall["precision"] == 1.0
    assert overall["recall"] == pytest.approx(1 / 3)
    assert overall["false_negative_rate"] == pytest.approx(2 / 3)
    assert overall["explicit_abstention_count"] == 1
    assert overall["missing_prediction_count"] == 1
    assert overall["probability_coverage"] == 0.75
    assert result["subgroups"]["language"]["fr"]["false_negative_rate"] == 1.0


def test_unresolved_state_cannot_be_silently_coerced_to_binary_gold() -> None:
    gold = [
        {
            "item_id": "SYN-X",
            "gold_label": "POSITIVE",
            "adjudication_state": "DISAGREE_UNADJUDICATED",
        }
    ]
    with pytest.raises(BenchmarkContractError, match="cannot carry a binary gold label"):
        score_predictions([], gold)


def test_predictions_outside_controlled_benchmark_are_rejected() -> None:
    gold = [{"item_id": "SYN-X", "gold_label": "NEGATIVE", "adjudication_state": "AGREE"}]
    predictions = [{"item_id": "SYN-Y", "prediction": "NEGATIVE"}]
    with pytest.raises(BenchmarkContractError, match="outside the controlled benchmark"):
        score_predictions(predictions, gold)
