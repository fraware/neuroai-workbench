from __future__ import annotations

import copy
import json
from importlib.resources import files

import pytest

from neuroai_workbench.benchmark_contracts import (
    BenchmarkContractError,
    canonical_json_bytes,
    create_commitment,
    validate_public_manifest,
    validate_synthetic_fixture,
)


def _resource_json(name: str):
    resource = files("neuroai_workbench.resources.benchmarks").joinpath(name)
    return json.loads(resource.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name",
    ["D3_PATENT_PRE_G2.manifest.json", "D4_PRODUCT_PRE_G2.manifest.json"],
)
def test_public_pre_g2_manifests_validate(name: str) -> None:
    validate_public_manifest(_resource_json(name))


def test_canonical_json_is_order_independent_and_utf8() -> None:
    assert canonical_json_bytes({"b": 2, "a": "é"}) == canonical_json_bytes({"a": "é", "b": 2})
    assert canonical_json_bytes({"a": "é"}) == b'{"a":"\xc3\xa9"}'


def test_commitment_is_deterministic_and_domain_nonce_separated() -> None:
    payload = {"synthetic_member_ids": ["A", "B"]}
    nonce = b"a" * 32
    first = create_commitment(payload, nonce=nonce, domain_separator="NEUROAI:D3:TEST", split="heldout")
    second = create_commitment(payload, nonce=nonce, domain_separator="NEUROAI:D3:TEST", split="heldout")
    assert first == second
    assert "nonce" not in first
    assert first["nonce_disposition"] == "S3_CONTROLLED_NOT_PUBLIC"
    assert first["digest"] != create_commitment(
        payload,
        nonce=b"b" * 32,
        domain_separator="NEUROAI:D3:TEST",
        split="heldout",
    )["digest"]
    assert first["digest"] != create_commitment(
        payload,
        nonce=nonce,
        domain_separator="NEUROAI:D4:TEST",
        split="heldout",
    )["digest"]


def test_commitment_rejects_short_nonce_and_nonfinite_payload() -> None:
    with pytest.raises(BenchmarkContractError, match="at least 32 bytes"):
        create_commitment({}, nonce=b"short", domain_separator="NEUROAI:D3:TEST", split="heldout")
    with pytest.raises(BenchmarkContractError, match="Non-finite"):
        canonical_json_bytes({"score": float("nan")})


def test_public_manifest_rejects_recursive_s3_leakage() -> None:
    manifest = _resource_json("D3_PATENT_PRE_G2.manifest.json")
    manifest["subgroup_contract"]["raw_text"] = "forbidden"
    with pytest.raises(BenchmarkContractError, match="Forbidden S3/held-out field"):
        validate_public_manifest(manifest)


@pytest.mark.parametrize("field", ["g1_approved", "g2_frozen", "contains_real_heldout_labels"])
def test_public_manifest_cannot_claim_governance_or_real_labels(field: str) -> None:
    manifest = _resource_json("D4_PRODUCT_PRE_G2.manifest.json")
    manifest[field] = True
    with pytest.raises(BenchmarkContractError):
        validate_public_manifest(manifest)


def test_created_commitment_descriptor_can_be_validated_without_nonce_disclosure() -> None:
    manifest = _resource_json("D3_PATENT_PRE_G2.manifest.json")
    descriptor = create_commitment(
        {"synthetic": True, "member_ids_digest_input": ["A", "B"]},
        nonce=b"z" * 32,
        domain_separator="NEUROAI:D3:SPLIT:HELDOUT:V1",
        split="heldout",
    )
    manifest["split_commitment_state"] = "CREATED"
    manifest["split_commitments"] = [descriptor]
    validate_public_manifest(manifest)


def test_precommitment_state_rejects_commitment_descriptor() -> None:
    manifest = _resource_json("D3_PATENT_PRE_G2.manifest.json")
    manifest["split_commitments"] = [
        create_commitment(
            {"synthetic": True},
            nonce=b"z" * 32,
            domain_separator="NEUROAI:D3:SPLIT:HELDOUT:V1",
            split="heldout",
        )
    ]
    with pytest.raises(BenchmarkContractError, match="Pre-commitment state"):
        validate_public_manifest(manifest)


def test_synthetic_fixtures_preserve_human_model_boundary() -> None:
    fixtures = _resource_json("SYNTHETIC_FIXTURES.json")
    assert {fixture["benchmark_kind"] for fixture in fixtures} == {"patent", "product"}
    for fixture in fixtures:
        validate_synthetic_fixture(fixture)
        assert fixture["synthetic"] is True
        assert fixture["benchmark_status"] == "SYNTHETIC_TEST_ONLY"
        assert fixture["adjudication"]["basis"] == "HUMAN_SYNTHETIC_ANNOTATIONS"
        assert all(output["authority"] == "UNTRUSTED_DRAFT_ONLY" for output in fixture["model_outputs"])


def test_synthetic_fixture_rejects_model_authority_and_freeze_claim() -> None:
    fixture = _resource_json("SYNTHETIC_FIXTURES.json")[0]
    elevated = copy.deepcopy(fixture)
    elevated["model_outputs"][0]["authority"] = "GOLD_LABEL_AUTHORITY"
    with pytest.raises(BenchmarkContractError, match="untrusted drafts"):
        validate_synthetic_fixture(elevated)

    frozen = copy.deepcopy(fixture)
    frozen["benchmark_status"] = "FROZEN"
    with pytest.raises(BenchmarkContractError, match="cannot claim frozen"):
        validate_synthetic_fixture(frozen)
