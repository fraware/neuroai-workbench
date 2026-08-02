from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.extraction import (
    ExtractionProviderConfig,
    ProviderExecutionRefusedError,
    build_extraction_request_from_capture,
    default_offline_evaluation_configs,
    dispose_extraction_response,
    load_benchmark_manifest,
    load_fixture_stub,
    record_extraction_request,
    record_extraction_response,
    resolve_provider,
    run_bounded_offline_evaluation,
    validate_provider_config,
    verify_extraction_records,
)


def test_unregistered_provider_is_refused() -> None:
    config = ExtractionProviderConfig(
        config_id="CFG-REMOTE",
        provider_id="remote-openai",
        model_id="gpt-remote",
        enabled=True,
        endpoint_class="NOT_EXECUTED",
    )
    errors = validate_provider_config(config)
    assert any(error["code"] == "PROVIDER_UNREGISTERED" for error in errors)
    with pytest.raises(ProviderExecutionRefusedError):
        resolve_provider(config)


def test_network_endpoint_class_is_refused() -> None:
    config = ExtractionProviderConfig(
        config_id="CFG-NETWORK",
        provider_id="fake-offline",
        model_id="fake-offline-baseline-v1",
        enabled=True,
        endpoint_class="REMOTE_API",
    )
    errors = validate_provider_config(config)
    assert any(error["code"] == "NETWORK_REFUSED" for error in errors)


def test_tampered_disposition_is_detected(tmp_path: Path) -> None:
    manifest = load_benchmark_manifest()
    fixture = manifest["fixtures"][0]
    capture = load_fixture_stub(str(fixture["capture_stub"]))
    annotation = load_fixture_stub(str(fixture["annotation_stub"]))
    request = build_extraction_request_from_capture(capture)
    provider = resolve_provider(
        next(item for item in default_offline_evaluation_configs() if item.provider_id == "fake-offline")
    )
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
        "PARTIALLY_USED",
        "Partial use allowed only after human review.",
    )

    disposition_path = tmp_path / "extraction_eval" / "dispositions" / f"{request['request_id']}.json"
    tampered = json.loads(disposition_path.read_text(encoding="utf-8"))
    tampered["disposition"] = "ACCEPTED_AS_DRAFT"
    disposition_path.write_text(json.dumps(tampered), encoding="utf-8")

    report = verify_extraction_records(tmp_path, str(request["request_id"]))
    assert report["valid"] is False
    assert "disposition hash mismatch" in report["errors"]


def test_response_without_request_is_refused(tmp_path: Path) -> None:
    manifest = load_benchmark_manifest()
    fixture = manifest["fixtures"][0]
    capture = load_fixture_stub(str(fixture["capture_stub"]))
    annotation = load_fixture_stub(str(fixture["annotation_stub"]))
    request = build_extraction_request_from_capture(capture)
    provider = resolve_provider(
        next(item for item in default_offline_evaluation_configs() if item.provider_id == "fake-offline")
    )
    response = provider.extract(request, annotation=annotation)

    with pytest.raises(ValueError, match="No extraction request recorded"):
        record_extraction_response(
            tmp_path,
            request,
            response,
            provider=provider.config.provider_id,
            model=provider.config.model_id,
        )


def test_bounded_evaluation_never_recommends_aggregate_winner() -> None:
    report = run_bounded_offline_evaluation()
    assert report["recommended_config_id"] is None
    assert report["selection_refused"] is True
    assert len(report["aggregate_scores"]) >= 2
