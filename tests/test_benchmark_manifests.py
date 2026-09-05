from __future__ import annotations

import copy

import pytest

from neuroai_workbench.benchmark_manifests import (
    APPROVED_G1_DISPOSITION_ID,
    APPROVED_G1_DISPOSITION_SHA256,
    HUMAN_REVIEW_REQUIRED_FIELDS,
    RIGHTS_CONTAINMENT_STATE,
    BenchmarkManifestError,
    manifest_identity_sha256,
    validate_freeze_manifest,
    validate_held_out_run_manifest,
)
from neuroai_workbench.benchmark_packaging import load_packaged_public_contract
from neuroai_workbench.evaluation_benchmarks import (
    APPROVED_D1_CANONICAL_SHA256,
    BINARY_PROJECTION_ID,
    REQUIRED_BOUNDARY_DISPOSITIONS,
)


def _public_contract(kind: str = "PATENT") -> dict[str, object]:
    contract = copy.deepcopy(load_packaged_public_contract(kind))
    contract["state"] = "FROZEN_COMMITMENTS_ONLY"
    contract["membership_commitment"] = "2" * 64
    contract["label_commitment"] = "3" * 64
    return contract


def _freeze(contract: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "0.2",
        "manifest_type": "BENCHMARK_FREEZE",
        "manifest_id": f"{contract['benchmark_kind']}-FREEZE-SYNTHETIC",
        "benchmark_kind": contract["benchmark_kind"],
        "benchmark_id": contract["benchmark_id"],
        "public_contract_schema_version": "0.2",
        "public_contract_sha256": manifest_identity_sha256(contract),
        "d1_canonical_json_sha256": APPROVED_D1_CANONICAL_SHA256,
        "binary_projection_id": BINARY_PROJECTION_ID,
        "g1_disposition_id": APPROVED_G1_DISPOSITION_ID,
        "g1_disposition_sha256": APPROVED_G1_DISPOSITION_SHA256,
        "membership_commitment": contract["membership_commitment"],
        "label_commitment": contract["label_commitment"],
        "commitment_scheme": "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1",
        "s3_custody": True,
        "required_boundary_dispositions": sorted(REQUIRED_BOUNDARY_DISPOSITIONS),
        "boundary_disposition_counts": {
            "INCLUDE": 2,
            "EXCLUDE": 1,
            "BORDERLINE": 1,
            "ABSTAIN": 1,
            "UNRESOLVED_ADJUDICATION": 0,
        },
        "boundary_coverage_report_sha256": "4" * 64,
        "required_strata": sorted(contract["required_strata"]),
        "strata_coverage_report_sha256": "5" * 64,
        "sampling_protocol_id": "SAMPLE-PROTOCOL-SYNTHETIC-v0.1",
        "sampling_protocol_sha256": "6" * 64,
        "human_review_required_fields": sorted(HUMAN_REVIEW_REQUIRED_FIELDS),
        "human_review_provenance_sha256": "7" * 64,
        "adjudication_protocol_id": "ADJUDICATION-SYNTHETIC-v0.1",
        "adjudication_protocol_sha256": "8" * 64,
        "adjudication_accounting_sha256": "9" * 64,
        "double_label_subset_count": 2,
        "rights_containment_status": RIGHTS_CONTAINMENT_STATE,
        "rights_review_ref": "S3-RIGHTS-REVIEW-SYNTHETIC",
        "frozen_at": "2026-09-05T14:00:00Z",
        "lineage_state": "ROOT",
        "predecessor_manifest_sha256": None,
        "contamination_status": "NO_KNOWN_CONTAMINATION_REVIEWED",
        "exposure_register_ref": "S3-EXPOSURE-REGISTER-SYNTHETIC",
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


def _run(freeze: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "0.2",
        "manifest_type": "HELD_OUT_EVALUATION_RUN",
        "run_id": "D3-RUN-SYNTHETIC",
        "benchmark_kind": freeze["benchmark_kind"],
        "freeze_manifest_id": freeze["manifest_id"],
        "freeze_manifest_sha256": manifest_identity_sha256(freeze),
        "public_contract_sha256": freeze["public_contract_sha256"],
        "workbench_commit_sha": "a" * 40,
        "pipeline_id": "BASELINE-A-SYNTHETIC",
        "pipeline_artifact_sha256": "b" * 64,
        "config_sha256": "c" * 64,
        "threshold_policy_id": "THRESHOLD-SYNTHETIC",
        "threshold_policy_sha256": "d" * 64,
        "abstention_policy_id": "ABSTENTION-SYNTHETIC",
        "abstention_policy_sha256": "e" * 64,
        "development_tuning_boundary": "HELD_OUT_NOT_USED_FOR_TUNING",
        "subgroup_plan_id": "SUBGROUP-SYNTHETIC",
        "subgroup_plan_sha256": "f" * 64,
        "metric_schema_version": "0.2",
        "binary_projection_id": BINARY_PROJECTION_ID,
        "observed_at": "2026-09-05T15:00:00+00:00",
        "operator_role_ref": "CONTROLLED_EVALUATION_OPERATOR",
        "contamination_status": "NO_KNOWN_CONTAMINATION_REVIEWED",
        "exposure_register_ref": "S3-EXPOSURE-REGISTER-SYNTHETIC",
        "prediction_artifact_sha256": "1" * 64,
        "aggregate_result_sha256": "a" * 64,
        "export_policy": "AGGREGATE_ONLY",
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


@pytest.mark.parametrize("kind", ["PATENT", "PRODUCT"])
def test_complete_current_freeze_and_run_are_structurally_valid(kind: str) -> None:
    contract = _public_contract(kind)
    freeze = _freeze(contract)
    run = _run(freeze)
    validate_freeze_manifest(freeze, public_contract=contract)
    validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)


def test_manifest_identity_is_deterministic_and_payload_bound() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    first = manifest_identity_sha256(freeze)
    assert first == manifest_identity_sha256(copy.deepcopy(freeze))
    changed = copy.deepcopy(freeze)
    changed["human_review_provenance_sha256"] = "c" * 64
    assert first != manifest_identity_sha256(changed)


def test_legacy_manifest_schema_is_not_silently_reinterpreted() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["schema_version"] = "0.1"
    with pytest.raises(BenchmarkManifestError, match="schema_version must be 0.2"):
        validate_freeze_manifest(freeze, public_contract=contract)


def test_freeze_requires_frozen_exact_public_contract_binding() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["public_contract_sha256"] = "0" * 64
    with pytest.raises(BenchmarkManifestError, match="public_contract_sha256"):
        validate_freeze_manifest(freeze, public_contract=contract)

    draft = copy.deepcopy(contract)
    draft["state"] = "DRAFT_UNFROZEN"
    draft["membership_commitment"] = None
    draft["label_commitment"] = None
    with pytest.raises(BenchmarkManifestError, match="FROZEN_COMMITMENTS_ONLY"):
        validate_freeze_manifest(freeze, public_contract=draft)


def test_freeze_rejects_wrong_d1_or_g1_identity() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["d1_canonical_json_sha256"] = "0" * 64
    with pytest.raises(BenchmarkManifestError, match="exact approved D1"):
        validate_freeze_manifest(freeze, public_contract=contract)

    fake_g1 = copy.deepcopy(contract)
    fake_g1["g1_disposition_id"] = "FAKE-G1"
    freeze = _freeze(fake_g1)
    freeze["g1_disposition_id"] = "FAKE-G1"
    with pytest.raises(BenchmarkManifestError, match="exact approved G1 disposition id"):
        validate_freeze_manifest(freeze, public_contract=fake_g1)


def test_freeze_commitments_must_match_public_contract() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["membership_commitment"] = "c" * 64
    with pytest.raises(BenchmarkManifestError, match="membership_commitment does not match"):
        validate_freeze_manifest(freeze, public_contract=contract)


def test_freeze_requires_exact_boundary_and_strata_contracts() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["required_boundary_dispositions"] = ["INCLUDE", "EXCLUDE"]
    with pytest.raises(BenchmarkManifestError, match="required_boundary_dispositions"):
        validate_freeze_manifest(freeze, public_contract=contract)

    freeze = _freeze(contract)
    strata = list(freeze["required_strata"])
    strata.pop()
    freeze["required_strata"] = strata
    with pytest.raises(BenchmarkManifestError, match="required_strata"):
        validate_freeze_manifest(freeze, public_contract=contract)


def test_required_g2_boundary_coverage_cannot_be_zero() -> None:
    contract = _public_contract()
    for disposition in sorted(REQUIRED_BOUNDARY_DISPOSITIONS):
        freeze = _freeze(contract)
        counts = dict(freeze["boundary_disposition_counts"])
        counts[disposition] = 0
        freeze["boundary_disposition_counts"] = counts
        with pytest.raises(BenchmarkManifestError, match=disposition):
            validate_freeze_manifest(freeze, public_contract=contract)


def test_human_review_provenance_and_double_label_evidence_are_required() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["human_review_required_fields"] = ["decision", "rationale"]
    with pytest.raises(BenchmarkManifestError, match="human_review_required_fields"):
        validate_freeze_manifest(freeze, public_contract=contract)

    freeze = _freeze(contract)
    freeze["human_review_provenance_sha256"] = None
    with pytest.raises(BenchmarkManifestError, match="human_review_provenance_sha256"):
        validate_freeze_manifest(freeze, public_contract=contract)

    freeze = _freeze(contract)
    freeze["double_label_subset_count"] = 6
    with pytest.raises(BenchmarkManifestError, match="cannot exceed"):
        validate_freeze_manifest(freeze, public_contract=contract)


def test_rights_containment_and_contamination_fail_closed() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["rights_containment_status"] = "PUBLIC_REDISTRIBUTION_AUTHORIZED"
    with pytest.raises(BenchmarkManifestError, match="rights_containment_status"):
        validate_freeze_manifest(freeze, public_contract=contract)

    freeze = _freeze(contract)
    freeze["contamination_status"] = "UNRESOLVED"
    with pytest.raises(BenchmarkManifestError, match="contamination"):
        validate_freeze_manifest(freeze, public_contract=contract)


def test_successor_freeze_requires_predecessor_digest() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["lineage_state"] = "SUCCESSOR"
    with pytest.raises(BenchmarkManifestError, match="predecessor_manifest_sha256"):
        validate_freeze_manifest(freeze, public_contract=contract)

    freeze["predecessor_manifest_sha256"] = "d" * 64
    validate_freeze_manifest(freeze, public_contract=contract)


def test_run_binds_exact_freeze_and_public_contract() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    run = _run(freeze)

    changed_freeze = copy.deepcopy(freeze)
    changed_freeze["adjudication_accounting_sha256"] = "e" * 64
    with pytest.raises(BenchmarkManifestError, match="freeze_manifest_sha256"):
        validate_held_out_run_manifest(run, freeze_manifest=changed_freeze, public_contract=contract)

    run = _run(freeze)
    run["public_contract_sha256"] = "0" * 64
    with pytest.raises(BenchmarkManifestError, match="public_contract_sha256"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)


def test_run_requires_current_metric_and_projection_identity() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    run = _run(freeze)
    run["metric_schema_version"] = "0.1"
    with pytest.raises(BenchmarkManifestError, match="metric_schema_version"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)

    run = _run(freeze)
    run["binary_projection_id"] = "LEGACY_BINARY"
    with pytest.raises(BenchmarkManifestError, match="binary_projection_id"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)


def test_run_rejects_held_out_tuning_contamination_authority_and_item_export() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)

    run = _run(freeze)
    run["development_tuning_boundary"] = "HELD_OUT_USED_FOR_TUNING"
    with pytest.raises(BenchmarkManifestError, match="held-out data was not used"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)

    run = _run(freeze)
    run["contamination_status"] = "KNOWN_EXPOSURE"
    with pytest.raises(BenchmarkManifestError, match="contamination"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)

    run = _run(freeze)
    run["g2_passed"] = True
    with pytest.raises(BenchmarkManifestError, match="g2_passed"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)

    run = _run(freeze)
    run["export_policy"] = "ITEM_LEVEL"
    with pytest.raises(BenchmarkManifestError, match="AGGREGATE_ONLY"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze, public_contract=contract)


def test_timestamps_require_utc() -> None:
    contract = _public_contract()
    freeze = _freeze(contract)
    freeze["frozen_at"] = "2026-09-05T16:00:00+02:00"
    with pytest.raises(BenchmarkManifestError, match="expressed in UTC"):
        validate_freeze_manifest(freeze, public_contract=contract)
