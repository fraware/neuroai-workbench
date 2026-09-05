from __future__ import annotations

import json
from importlib.resources import files

from neuroai_workbench.benchmark_packaging import load_all_packaged_public_contracts
from neuroai_workbench.evaluation_benchmarks import REQUIRED_STRATA, validate_public_benchmark_contract

RESOURCE_PACKAGE = "neuroai_workbench.resources.benchmarks"
REFERENCE_NAME = "G1_D1_D2_DISPOSITION_REFERENCE.json"
EXPECTED_DISPOSITION_ID = "HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1"
EXPECTED_DISPOSITION_CANONICAL_SHA256 = "ed6489fe1085b5aec1b594970dd1c574b57bd6bbd25a659643e9bd1b7b72d8ef"
EXPECTED_OBSERVATORY_MAIN_SHA = "e12b0fdffcaa2c73c723574f8718241b9cd0cd89"
EXPECTED_OBSERVATORY_BLOB_SHA = "ed42dc5b77cf011562db8c8c39bc9e71968fdb37"
EXPECTED_D1_SHA256 = "7d270002094dcdecb703d5b70ef2268e4869005c284ffd98db3eb936641a78cb"
EXPECTED_D2_SHA256 = "bd9451a5084485ef7a36251b0bc39d486fe0c2174636171a29ec03d7010cbf1d"


def _load_reference() -> dict[str, object]:
    payload = files(RESOURCE_PACKAGE).joinpath(REFERENCE_NAME).read_text(encoding="utf-8")
    value = json.loads(payload)
    assert isinstance(value, dict)
    return value


def test_cross_repository_g1_reference_binds_exact_observatory_record() -> None:
    reference = _load_reference()
    assert reference["reference_type"] == "EXTERNAL_G1_DISPOSITION_REFERENCE"
    assert reference["disposition_id"] == EXPECTED_DISPOSITION_ID
    assert reference["decision"] == "APPROVE"
    assert reference["source_repository"] == "fraware/neuroai-observatory-data"
    assert reference["source_main_sha"] == EXPECTED_OBSERVATORY_MAIN_SHA
    assert reference["source_path"] == "curation/HUMAN_G1_DISPOSITION_2026-09-05_D1_D2_v0.1.json"
    assert reference["source_git_blob_sha"] == EXPECTED_OBSERVATORY_BLOB_SHA
    assert reference["source_canonical_json_sha256"] == EXPECTED_DISPOSITION_CANONICAL_SHA256
    assert reference["d1_canonical_json_sha256"] == EXPECTED_D1_SHA256
    assert reference["d2_canonical_json_sha256"] == EXPECTED_D2_SHA256

    authority = reference["authority"]
    assert isinstance(authority, dict)
    assert authority["creates_g1_approval"] is False
    assert authority["g2_passed"] is False
    assert authority["canonical_s2_authority"] is False
    assert authority["publication_authority"] is False
    assert authority["assessment_effect"] == "NONE"


def test_d3_d4_packaged_drafts_bind_approved_g1_without_freezing_g2() -> None:
    contracts = load_all_packaged_public_contracts()
    assert set(contracts) == {"PATENT", "PRODUCT"}

    for kind, contract in contracts.items():
        validate_public_benchmark_contract(contract)
        assert contract["state"] == "DRAFT_UNFROZEN"
        assert contract["g1_gate_state"] == "APPROVED_REFERENCE_PROVIDED"
        assert contract["g1_disposition_id"] == EXPECTED_DISPOSITION_ID
        assert contract["g1_disposition_sha256"] == EXPECTED_DISPOSITION_CANONICAL_SHA256
        assert contract["membership_commitment"] is None
        assert contract["label_commitment"] is None
        assert contract["g2_passed"] is False
        assert contract["canonical_s2_authority"] is False
        assert contract["publication_authority"] is False
        assert contract["assessment_effect"] == "NONE"
        assert contract["private_membership_location"] == "S3_CONTROLLED"
        assert contract["private_labels_location"] == "S3_CONTROLLED"
        assert set(contract["required_strata"]) == REQUIRED_STRATA[kind]
        assert contract["double_label_subset_required"] is True


def test_g1_reference_does_not_disclose_or_fabricate_s3_benchmark_payloads() -> None:
    reference = _load_reference()
    prohibited = {
        "membership",
        "labels",
        "gold_labels",
        "reviewer_labels",
        "adjudication_packets",
        "commitment_secret",
        "nonce",
        "raw_text",
        "licensed_bytes",
    }
    assert prohibited.isdisjoint(reference)
