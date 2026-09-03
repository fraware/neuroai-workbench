from __future__ import annotations

import copy

import pytest

from neuroai_workbench.benchmark_manifests import (
    BenchmarkManifestError,
    manifest_identity_sha256,
    validate_freeze_manifest,
    validate_held_out_run_manifest,
)


def _freeze() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "manifest_type": "BENCHMARK_FREEZE",
        "manifest_id": "D3-PATENT-FREEZE-SYNTHETIC",
        "benchmark_kind": "PATENT",
        "benchmark_id": "D3-PATENT-SYNTHETIC",
        "g1_disposition_id": "G1-DISPOSITION-SYNTHETIC",
        "g1_disposition_sha256": "1" * 64,
        "membership_commitment": "2" * 64,
        "label_commitment": "3" * 64,
        "commitment_scheme": "HMAC_SHA256_CANONICAL_JSON_V1",
        "s3_custody": True,
        "strata_contract_version": "D3-v0.1",
        "adjudication_protocol_version": "ADJ-v0.1",
        "frozen_at": "2026-09-03T09:00:00Z",
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
        "schema_version": "0.1",
        "manifest_type": "HELD_OUT_EVALUATION_RUN",
        "run_id": "D3-RUN-SYNTHETIC",
        "benchmark_kind": "PATENT",
        "freeze_manifest_id": freeze["manifest_id"],
        "freeze_manifest_sha256": manifest_identity_sha256(freeze),
        "workbench_commit_sha": "a" * 40,
        "pipeline_id": "BASELINE-A-SYNTHETIC",
        "pipeline_artifact_sha256": "4" * 64,
        "config_sha256": "5" * 64,
        "threshold_policy_id": "THRESHOLD-SYNTHETIC",
        "threshold_policy_sha256": "6" * 64,
        "abstention_policy_id": "ABSTENTION-SYNTHETIC",
        "abstention_policy_sha256": "7" * 64,
        "development_tuning_boundary": "HELD_OUT_NOT_USED_FOR_TUNING",
        "subgroup_plan_id": "SUBGROUP-SYNTHETIC",
        "subgroup_plan_sha256": "8" * 64,
        "metric_schema_version": "METRICS-v0.1",
        "observed_at": "2026-09-03T10:00:00+00:00",
        "operator_role_ref": "CONTROLLED_EVALUATION_OPERATOR",
        "contamination_status": "NO_KNOWN_CONTAMINATION_REVIEWED",
        "exposure_register_ref": "S3-EXPOSURE-REGISTER-SYNTHETIC",
        "prediction_artifact_sha256": "9" * 64,
        "aggregate_result_sha256": "b" * 64,
        "export_policy": "AGGREGATE_ONLY",
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


def test_complete_synthetic_freeze_and_run_are_structurally_valid() -> None:
    freeze = _freeze()
    run = _run(freeze)
    validate_freeze_manifest(freeze)
    validate_held_out_run_manifest(run, freeze_manifest=freeze)


def test_manifest_identity_is_deterministic_and_payload_bound() -> None:
    freeze = _freeze()
    first = manifest_identity_sha256(freeze)
    assert first == manifest_identity_sha256(copy.deepcopy(freeze))
    changed = copy.deepcopy(freeze)
    changed["label_commitment"] = "c" * 64
    assert first != manifest_identity_sha256(changed)


def test_freeze_requires_exact_g1_and_private_commitment_bindings() -> None:
    freeze = _freeze()
    freeze["g1_disposition_sha256"] = None
    with pytest.raises(BenchmarkManifestError, match="g1_disposition_sha256"):
        validate_freeze_manifest(freeze)

    freeze = _freeze()
    freeze["membership_commitment"] = None
    with pytest.raises(BenchmarkManifestError, match="membership_commitment"):
        validate_freeze_manifest(freeze)

    freeze = _freeze()
    freeze["s3_custody"] = False
    with pytest.raises(BenchmarkManifestError, match="s3_custody"):
        validate_freeze_manifest(freeze)


def test_successor_freeze_requires_predecessor_digest() -> None:
    freeze = _freeze()
    freeze["lineage_state"] = "SUCCESSOR"
    with pytest.raises(BenchmarkManifestError, match="predecessor_manifest_sha256"):
        validate_freeze_manifest(freeze)

    freeze["predecessor_manifest_sha256"] = "d" * 64
    validate_freeze_manifest(freeze)


def test_freeze_rejects_known_or_unresolved_contamination() -> None:
    freeze = _freeze()
    freeze["contamination_status"] = "KNOWN_EXPOSURE"
    with pytest.raises(BenchmarkManifestError, match="contamination"):
        validate_freeze_manifest(freeze)


def test_run_binds_exact_freeze_payload() -> None:
    freeze = _freeze()
    run = _run(freeze)
    changed_freeze = copy.deepcopy(freeze)
    changed_freeze["label_commitment"] = "e" * 64
    with pytest.raises(BenchmarkManifestError, match="freeze_manifest_sha256"):
        validate_held_out_run_manifest(run, freeze_manifest=changed_freeze)


def test_run_rejects_missing_pipeline_threshold_and_abstention_identity() -> None:
    freeze = _freeze()
    for field in (
        "pipeline_artifact_sha256",
        "config_sha256",
        "threshold_policy_sha256",
        "abstention_policy_sha256",
    ):
        run = _run(freeze)
        run[field] = None
        with pytest.raises(BenchmarkManifestError, match=field):
            validate_held_out_run_manifest(run, freeze_manifest=freeze)


def test_run_rejects_held_out_tuning_or_contamination() -> None:
    freeze = _freeze()
    run = _run(freeze)
    run["development_tuning_boundary"] = "HELD_OUT_USED_FOR_TUNING"
    with pytest.raises(BenchmarkManifestError, match="held-out data was not used"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze)

    run = _run(freeze)
    run["contamination_status"] = "UNRESOLVED"
    with pytest.raises(BenchmarkManifestError, match="contamination"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze)


def test_run_rejects_authority_escalation_and_item_level_export() -> None:
    freeze = _freeze()
    run = _run(freeze)
    run["g2_passed"] = True
    with pytest.raises(BenchmarkManifestError, match="g2_passed"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze)

    run = _run(freeze)
    run["export_policy"] = "ITEM_LEVEL"
    with pytest.raises(BenchmarkManifestError, match="AGGREGATE_ONLY"):
        validate_held_out_run_manifest(run, freeze_manifest=freeze)


def test_timestamps_require_utc() -> None:
    freeze = _freeze()
    freeze["frozen_at"] = "2026-09-03T11:00:00+02:00"
    with pytest.raises(BenchmarkManifestError, match="expressed in UTC"):
        validate_freeze_manifest(freeze)
