from __future__ import annotations

import copy

import pytest

from neuroai_workbench.evaluation_benchmarks import (
    ADJUDICATION_STATES,
    APPROVED_D1_CANONICAL_SHA256,
    BINARY_PROJECTION_ID,
    BOUNDARY_DISPOSITIONS,
    REQUIRED_BOUNDARY_DISPOSITIONS,
    REQUIRED_STRATA,
    BenchmarkContractError,
    keyed_commitment,
    score_predictions,
    validate_controlled_gold_rows,
    validate_prediction_rows,
    validate_public_benchmark_contract,
)


def _boundary_semantics() -> dict[str, object]:
    return {
        "source_d1_canonical_json_sha256": APPROVED_D1_CANONICAL_SHA256,
        "allowed_dispositions": sorted(BOUNDARY_DISPOSITIONS),
        "required_g2_coverage_dispositions": sorted(REQUIRED_BOUNDARY_DISPOSITIONS),
        "resolved_adjudication_states": ["ADJUDICATED", "AGREE"],
        "unresolved_adjudication_state": "DISAGREE_UNADJUDICATED",
        "rationale_required": True,
        "binary_projection": {
            "projection_id": BINARY_PROJECTION_ID,
            "positive_disposition": "INCLUDE",
            "negative_disposition": "EXCLUDE",
            "excluded_human_dispositions": ["ABSTAIN", "BORDERLINE"],
            "model_prediction_domain": sorted(BOUNDARY_DISPOSITIONS),
            "unresolved_adjudication_excluded_from_binary_metrics": True,
            "model_borderline_on_human_include_counts_as_effective_false_negative": True,
            "model_abstain_on_human_include_counts_as_effective_false_negative": True,
            "missing_prediction_on_human_include_counts_as_effective_false_negative": True,
            "probability_field": "probability_include",
        },
    }


def _contract(kind: str = "PATENT") -> dict[str, object]:
    return {
        "schema_version": "0.2",
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
        "commitment_scheme": "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1",
        "membership_commitment": None,
        "label_commitment": None,
        "boundary_semantics": _boundary_semantics(),
        "required_strata": sorted(REQUIRED_STRATA[kind]),
        "double_label_subset_required": True,
        "adjudication_states": sorted(ADJUDICATION_STATES),
    }


def _gold(
    item_id: str,
    disposition: str | None,
    *,
    state: str = "AGREE",
    language: str = "en",
    strata: list[str] | None = None,
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "boundary_disposition": disposition,
        "adjudication_state": state,
        "rationale": f"synthetic rationale for {item_id}",
        "strata": strata or ["SYNTHETIC"],
        "language": language,
        "jurisdiction": "SYN",
        "text_availability": "FULL",
    }


def test_public_contract_accepts_complete_patent_and_product_scaffolds() -> None:
    validate_public_benchmark_contract(_contract("PATENT"))
    validate_public_benchmark_contract(_contract("PRODUCT"))


def test_public_contract_requires_exact_boundary_semantics_and_separate_strata() -> None:
    contract = _contract("PATENT")
    assert set(contract["required_strata"]) == REQUIRED_STRATA["PATENT"]
    assert not {"POSITIVE", "NEGATIVE", "BORDERLINE"} & set(contract["required_strata"])

    bad = copy.deepcopy(contract)
    bad["boundary_semantics"]["allowed_dispositions"] = ["INCLUDE", "EXCLUDE"]
    with pytest.raises(BenchmarkContractError, match="four-way"):
        validate_public_benchmark_contract(bad)

    bad = copy.deepcopy(contract)
    bad["boundary_semantics"]["required_g2_coverage_dispositions"] = ["INCLUDE", "EXCLUDE"]
    with pytest.raises(BenchmarkContractError, match="INCLUDE, EXCLUDE, and BORDERLINE"):
        validate_public_benchmark_contract(bad)

    bad = copy.deepcopy(contract)
    bad["required_strata"].append("BORDERLINE")
    with pytest.raises(BenchmarkContractError, match="unexpected BORDERLINE"):
        validate_public_benchmark_contract(bad)


def test_public_contract_rejects_boundary_projection_semantic_drift() -> None:
    fields_and_values = {
        "projection_id": "OTHER",
        "positive_disposition": "EXCLUDE",
        "negative_disposition": "INCLUDE",
        "excluded_human_dispositions": ["BORDERLINE"],
        "model_prediction_domain": ["INCLUDE", "EXCLUDE"],
        "unresolved_adjudication_excluded_from_binary_metrics": False,
        "model_borderline_on_human_include_counts_as_effective_false_negative": False,
        "model_abstain_on_human_include_counts_as_effective_false_negative": False,
        "missing_prediction_on_human_include_counts_as_effective_false_negative": False,
        "probability_field": "probability_positive",
    }
    for field, value in fields_and_values.items():
        contract = copy.deepcopy(_contract())
        contract["boundary_semantics"]["binary_projection"][field] = value
        with pytest.raises(BenchmarkContractError, match="binary_projection"):
            validate_public_benchmark_contract(contract)


def test_public_contract_rejects_bad_d1_binding_rationale_and_adjudication_semantics() -> None:
    contract = copy.deepcopy(_contract())
    contract["boundary_semantics"]["source_d1_canonical_json_sha256"] = "0" * 64
    with pytest.raises(BenchmarkContractError, match="approved D1"):
        validate_public_benchmark_contract(contract)

    contract = copy.deepcopy(_contract())
    contract["boundary_semantics"]["rationale_required"] = False
    with pytest.raises(BenchmarkContractError, match="rationale"):
        validate_public_benchmark_contract(contract)

    contract = copy.deepcopy(_contract())
    contract["adjudication_states"] = ["AGREE", "ADJUDICATED", "ABSTAIN_UNRESOLVED"]
    with pytest.raises(BenchmarkContractError, match="unresolved disagreement"):
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


def test_approved_g1_reference_requires_exact_disposition_binding_shape() -> None:
    contract = _contract()
    contract["g1_gate_state"] = "APPROVED_REFERENCE_PROVIDED"
    with pytest.raises(BenchmarkContractError, match="g1_disposition_id"):
        validate_public_benchmark_contract(contract)

    contract["g1_disposition_id"] = "G1-DISPOSITION-SYNTHETIC"
    contract["g1_disposition_sha256"] = "not-a-digest"
    with pytest.raises(BenchmarkContractError, match="g1_disposition_sha256"):
        validate_public_benchmark_contract(contract)


def test_keyed_commitment_is_deterministic_keyed_domain_and_payload_bound() -> None:
    payload = {"items": ["S3-002", "S3-001"], "dispositions": {"S3-001": "INCLUDE"}}
    key = b"k" * 32
    domain = "NEUROAI:PRE_G2:MEMBERSHIP:V1"
    first = keyed_commitment(payload, key, domain_separator=domain)
    assert first == keyed_commitment(copy.deepcopy(payload), key, domain_separator=domain)
    assert first != keyed_commitment(payload, b"z" * 32, domain_separator=domain)
    assert first != keyed_commitment(payload, key, domain_separator="NEUROAI:PRE_G2:LABEL:V1")

    changed = copy.deepcopy(payload)
    changed["items"].append("S3-003")
    assert first != keyed_commitment(changed, key, domain_separator=domain)
    with pytest.raises(BenchmarkContractError, match="at least 32 bytes"):
        keyed_commitment(payload, b"short", domain_separator=domain)
    with pytest.raises(BenchmarkContractError, match="domain_separator"):
        keyed_commitment(payload, key, domain_separator="")
    with pytest.raises(BenchmarkContractError, match="ASCII"):
        keyed_commitment(payload, key, domain_separator="NEUROAI:é")


def test_prediction_contract_is_four_way_and_legacy_fields_fail_closed() -> None:
    validate_prediction_rows(
        [
            {"item_id": "I", "boundary_prediction": "INCLUDE", "probability_include": 0.9},
            {"item_id": "E", "boundary_prediction": "EXCLUDE"},
            {"item_id": "B", "boundary_prediction": "BORDERLINE"},
            {"item_id": "A", "boundary_prediction": "ABSTAIN"},
        ]
    )
    with pytest.raises(BenchmarkContractError, match="Legacy prediction"):
        validate_prediction_rows([{"item_id": "X", "prediction": "POSITIVE"}])
    with pytest.raises(BenchmarkContractError, match="Legacy probability_positive"):
        validate_prediction_rows([{"item_id": "X", "boundary_prediction": "INCLUDE", "probability_positive": 0.9}])
    with pytest.raises(BenchmarkContractError, match="boundary_prediction"):
        validate_prediction_rows([{"item_id": "X", "boundary_prediction": "POSITIVE"}])


def test_prediction_leakage_guard_rejects_human_boundary_oracle_fields_recursively() -> None:
    rows = [
        {
            "item_id": "SYN-2",
            "boundary_prediction": "EXCLUDE",
            "metadata": {"nested": {"boundary_disposition": "INCLUDE"}},
        }
    ]
    with pytest.raises(BenchmarkContractError, match="prohibited oracle field"):
        validate_prediction_rows(rows)


def test_prediction_probability_validation_and_duplicate_ids_fail_closed() -> None:
    with pytest.raises(BenchmarkContractError, match="numeric"):
        validate_prediction_rows([{"item_id": "X", "boundary_prediction": "INCLUDE", "probability_include": True}])
    with pytest.raises(BenchmarkContractError, match="between 0 and 1"):
        validate_prediction_rows([{"item_id": "X", "boundary_prediction": "INCLUDE", "probability_include": 1.1}])
    with pytest.raises(BenchmarkContractError, match="Duplicate prediction"):
        validate_prediction_rows(
            [
                {"item_id": "X", "boundary_prediction": "INCLUDE"},
                {"item_id": "X", "boundary_prediction": "EXCLUDE"},
            ]
        )


def test_controlled_gold_preserves_human_borderline_abstain_and_unresolved_disagreement() -> None:
    validate_controlled_gold_rows(
        [
            _gold("B", "BORDERLINE"),
            _gold("A", "ABSTAIN", state="ADJUDICATED"),
            _gold("U", None, state="DISAGREE_UNADJUDICATED"),
        ]
    )
    with pytest.raises(BenchmarkContractError, match="cannot carry a governed boundary disposition"):
        validate_controlled_gold_rows([_gold("U", "BORDERLINE", state="DISAGREE_UNADJUDICATED")])
    with pytest.raises(BenchmarkContractError, match="requires one of"):
        validate_controlled_gold_rows([_gold("X", None)])
    with pytest.raises(BenchmarkContractError, match="recorded rationale"):
        row = _gold("X", "INCLUDE")
        row["rationale"] = ""
        validate_controlled_gold_rows([row])
    with pytest.raises(BenchmarkContractError, match="Legacy binary gold fields"):
        row = _gold("X", "INCLUDE")
        row["gold_label"] = "POSITIVE"
        validate_controlled_gold_rows([row])


def test_four_way_scoring_keeps_binary_denominator_separate_from_human_routing() -> None:
    gold = [
        _gold("I1", "INCLUDE", language="en"),
        _gold("I2", "INCLUDE", language="fr"),
        _gold("I3", "INCLUDE", language="de"),
        _gold("I4", "INCLUDE", language="es"),
        _gold("E1", "EXCLUDE", language="en"),
        _gold("E2", "EXCLUDE", language="fr"),
        _gold("B1", "BORDERLINE", language="fr", strata=["GRAY_CAPABILITY"]),
        _gold("A1", "ABSTAIN", state="ADJUDICATED", language="de"),
        _gold("U1", None, state="DISAGREE_UNADJUDICATED", language="en"),
    ]
    predictions = [
        {"item_id": "I1", "boundary_prediction": "INCLUDE", "probability_include": 0.9},
        {"item_id": "I2", "boundary_prediction": "BORDERLINE", "probability_include": 0.55},
        {"item_id": "I3", "boundary_prediction": "ABSTAIN"},
        # I4 deliberately missing
        {"item_id": "E1", "boundary_prediction": "EXCLUDE", "probability_include": 0.1},
        {"item_id": "E2", "boundary_prediction": "INCLUDE", "probability_include": 0.8},
        {"item_id": "B1", "boundary_prediction": "BORDERLINE"},
        {"item_id": "A1", "boundary_prediction": "ABSTAIN"},
        {"item_id": "U1", "boundary_prediction": "INCLUDE"},
    ]

    result = score_predictions(predictions, gold)
    overall = result["overall"]
    binary = overall["binary"]
    assert result["binary_projection"]["projection_id"] == BINARY_PROJECTION_ID
    assert binary["eligible_count"] == 6
    assert binary["include_count"] == 4
    assert binary["exclude_count"] == 2
    assert binary["answered_count"] == 3
    assert binary["coverage"] == 0.5
    assert binary["precision"] == 0.5
    assert binary["recall"] == 0.25
    assert binary["false_negative_rate"] == 0.75
    assert binary["model_borderline_route_count"] == 1
    assert binary["model_abstain_route_count"] == 1
    assert binary["missing_prediction_count"] == 1
    assert binary["confusion"] == {
        "true_positive": 1,
        "true_negative": 1,
        "false_positive": 1,
        "false_negative_answered": 0,
        "include_routed_borderline": 1,
        "include_routed_abstain": 1,
        "include_missing": 1,
    }
    assert binary["probability_include_coverage"] == pytest.approx(4 / 6)
    assert binary["brier_score"] == pytest.approx((0.1**2 + 0.45**2 + 0.1**2 + 0.8**2) / 4)

    assert overall["human_disposition_counts"] == {
        "ABSTAIN": 1,
        "BORDERLINE": 1,
        "EXCLUDE": 2,
        "INCLUDE": 4,
    }
    assert overall["unresolved_adjudication_count"] == 1
    assert overall["routing"]["human_borderline"]["exact_route_rate"] == 1.0
    assert overall["routing"]["human_abstain"]["exact_route_rate"] == 1.0
    assert overall["routing"]["unresolved_adjudication_prediction_counts"]["INCLUDE"] == 1


def test_subgroup_reporting_preserves_binary_and_boundary_routing_semantics() -> None:
    gold = [
        _gold("I", "INCLUDE", language="fr"),
        _gold("B", "BORDERLINE", language="fr", strata=["GRAY_CAPABILITY", "MULTILINGUAL"]),
        _gold("A", "ABSTAIN", state="AGREE", language="de"),
    ]
    predictions = [
        {"item_id": "I", "boundary_prediction": "BORDERLINE"},
        {"item_id": "B", "boundary_prediction": "BORDERLINE"},
        {"item_id": "A", "boundary_prediction": "ABSTAIN"},
    ]
    result = score_predictions(predictions, gold)
    fr = result["subgroups"]["language"]["fr"]
    assert fr["binary"]["eligible_count"] == 1
    assert fr["binary"]["recall"] == 0.0
    assert fr["binary"]["false_negative_rate"] == 1.0
    assert fr["routing"]["human_borderline"]["exact_route_rate"] == 1.0
    assert result["subgroups"]["language"]["de"]["routing"]["human_abstain"]["exact_route_rate"] == 1.0
    assert result["subgroups"]["strata"]["MULTILINGUAL"]["human_disposition_counts"]["BORDERLINE"] == 1


def test_predictions_outside_controlled_benchmark_are_rejected() -> None:
    gold = [_gold("X", "EXCLUDE")]
    predictions = [{"item_id": "Y", "boundary_prediction": "EXCLUDE"}]
    with pytest.raises(BenchmarkContractError, match="outside the controlled benchmark"):
        score_predictions(predictions, gold)


def test_subgroup_values_fail_closed_when_malformed_and_normalize_empty_values() -> None:
    gold = [_gold("X", "INCLUDE")]
    gold[0]["language"] = {"bad": "shape"}
    with pytest.raises(BenchmarkContractError, match="Subgroup values"):
        score_predictions([], gold)

    gold = [_gold("X", "INCLUDE", strata=[])]
    gold[0]["language"] = ""
    result = score_predictions([], gold)
    assert "UNKNOWN" in result["subgroups"]["language"]
