from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.extraction import (
    ExtractionProviderConfig,
    ProviderExecutionRefusedError,
    build_extraction_request_from_capture,
    compare_provider_configs,
    default_offline_evaluation_configs,
    dispose_extraction_response,
    load_benchmark_manifest,
    load_fixture_stub,
    record_extraction_request,
    record_extraction_response,
    resolve_provider,
    run_bounded_offline_evaluation,
    run_config_against_benchmark,
    score_fixture_response,
    verify_extraction_records,
)


def test_default_offline_evaluation_compares_two_configs() -> None:
    report = run_bounded_offline_evaluation()
    assert len(report["config_results"]) == 2
    assert report["selection_refused"] is True
    assert report["recommended_config_id"] is None
    assert "aggregate score" in report["selection_refused_reason"]


def test_baseline_and_conservative_profiles_differ_on_contradictory_fixture() -> None:
    manifest = load_benchmark_manifest()
    baseline = run_config_against_benchmark(default_offline_evaluation_configs()[0], manifest=manifest)
    conservative = run_config_against_benchmark(default_offline_evaluation_configs()[1], manifest=manifest)
    baseline_scores = {item["fixture_id"]: item["metrics"]["field_recall"] for item in baseline["fixture_results"]}
    conservative_scores = {
        item["fixture_id"]: item["metrics"]["abstention_rate"] for item in conservative["fixture_results"]
    }
    assert baseline_scores != conservative_scores or baseline["aggregate_metrics"] != conservative["aggregate_metrics"]


def test_disabled_provider_is_refused() -> None:
    config = ExtractionProviderConfig(
        config_id="CFG-DISABLED",
        provider_id="fake-offline",
        model_id="fake-offline-disabled",
        enabled=False,
    )
    with pytest.raises(ProviderExecutionRefusedError, match="disabled by default"):
        resolve_provider(config)


def test_compare_requires_at_least_two_configs() -> None:
    config = default_offline_evaluation_configs()[0]
    with pytest.raises(ValueError, match="At least two provider configurations"):
        compare_provider_configs([config])


def test_build_request_from_capture_and_score_fixture() -> None:
    manifest = load_benchmark_manifest()
    fixture = manifest["fixtures"][0]
    capture = load_fixture_stub(str(fixture["capture_stub"]))
    annotation = load_fixture_stub(str(fixture["annotation_stub"]))
    request = build_extraction_request_from_capture(capture)
    provider = resolve_provider(default_offline_evaluation_configs()[0])
    response = provider.extract(request, annotation=annotation)
    metrics = score_fixture_response(response, annotation, request)
    assert metrics["field_recall"] == 1.0
    assert metrics["citation_accuracy"] == 1.0


def test_extraction_disposition_records_are_immutable(tmp_path: Path) -> None:
    manifest = load_benchmark_manifest()
    fixture = manifest["fixtures"][0]
    capture = load_fixture_stub(str(fixture["capture_stub"]))
    annotation = load_fixture_stub(str(fixture["annotation_stub"]))
    request = build_extraction_request_from_capture(capture)
    provider = resolve_provider(default_offline_evaluation_configs()[0])
    response = provider.extract(request, annotation=annotation)

    record_extraction_request(tmp_path, request)
    record_extraction_response(
        tmp_path,
        request,
        response,
        provider=provider.config.provider_id,
        model=provider.config.model_id,
    )
    dispose_extraction_response(
        tmp_path,
        str(request["request_id"]),
        "REJECTED",
        "Synthetic benchmark output rejected for controlled evaluation.",
    )
    assert verify_extraction_records(tmp_path, str(request["request_id"]))["valid"] is True

    with pytest.raises(ValueError, match="already recorded"):
        dispose_extraction_response(
            tmp_path,
            str(request["request_id"]),
            "ACCEPTED_AS_DRAFT",
            "Second disposition is forbidden.",
        )


def test_record_extraction_response_rejects_uncited_field(tmp_path: Path) -> None:
    manifest = load_benchmark_manifest()
    fixture = manifest["fixtures"][0]
    capture = load_fixture_stub(str(fixture["capture_stub"]))
    request = build_extraction_request_from_capture(capture)
    record_extraction_request(tmp_path, request)
    bad_response = {
        "schema_version": "1",
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "task_type": request["task_type"],
        "summary": "Invalid output.",
        "proposed_fields": [
            {
                "field_path": "mentioned_entities[0].name",
                "field_type": "ENTITY_MENTION",
                "value": "NeuroDevice Corp",
                "confidence": "HIGH",
                "limitations": [],
            }
        ],
        "abstentions": [],
        "warnings": [],
        "boundary": "Invalid.",
    }
    with pytest.raises(ValueError, match="contract validation"):
        record_extraction_response(
            tmp_path,
            request,
            bad_response,
            provider="fake-offline",
            model="fake-offline-baseline-v1",
        )
