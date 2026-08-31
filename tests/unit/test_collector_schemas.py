from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

import pytest
from jsonschema import Draft202012Validator

COLLECTOR_RESOURCE_PACKAGE = "neuroai_workbench.resources.collector"

COLLECTOR_BOUNDARY = (
    "Collector records retrieval provenance and quarantined bytes only. They do not establish source "
    "authenticity, claim truth, regulatory status, assessment effect, or monitoring adjudication outcomes."
)

REQUEST_SCHEMA = "collection-request.schema.json"
RESULT_SCHEMA = "collection-result.schema.json"
FAILURE_SCHEMA = "collection-failure.schema.json"
QUARANTINE_SCHEMA = "quarantine-record.schema.json"
STRUCTURED_ADAPTER_CONTRACT_SCHEMA = "structured-adapter-contract.schema.json"
NORMALIZED_STUDY_SCHEMA = "normalized-study-record.schema.json"

REGISTRY_SHA256 = "a" * 64
CONFIG_HASH = "b" * 64
CONTENT_SHA256 = "c" * 64
REQUEST_ID = "CREQ-" + "0" * 32
RESULT_ID = "CRES-" + "1" * 32
FAILURE_ID = "CFAIL-" + "2" * 32
QUARANTINE_ID = "QRN-" + "3" * 32


def _schema(name: str) -> dict[str, Any]:
    return json.loads(files(COLLECTOR_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8"))


def _validate(name: str, value: Any) -> list[str]:
    validator = Draft202012Validator(_schema(name))
    return sorted(
        f"{'.'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in validator.iter_errors(value)
    )


def valid_collection_request() -> dict[str, Any]:
    return {
        "request_id": REQUEST_ID,
        "source_id": "SRC-0001",
        "monitor_id": "MON-SRC-0001",
        "requested_url": "https://example.org/source",
        "requested_at": "2026-08-02T08:00:00Z",
        "registry_sha256": REGISTRY_SHA256,
        "collector_version": "0.0.0-contract",
        "configuration_hash": CONFIG_HASH,
        "boundary": COLLECTOR_BOUNDARY,
    }


def valid_collection_result() -> dict[str, Any]:
    return {
        "result_id": RESULT_ID,
        "request_id": REQUEST_ID,
        "source_id": "SRC-0001",
        "monitor_id": "MON-SRC-0001",
        "requested_url": "https://example.org/source",
        "final_url": "https://example.org/source/final",
        "redirect_chain": ["https://example.org/source"],
        "retrieved_at": "2026-08-02T08:00:01Z",
        "http_status": 200,
        "media_type": "text/html",
        "size_bytes": 128,
        "sha256": CONTENT_SHA256,
        "original_filename": "source.html",
        "quarantine_path": "incoming/2026/08/02/source.html",
        "dns_resolution": {
            "resolved_at": "2026-08-02T08:00:00Z",
            "addresses": ["93.184.216.34"],
            "rebinding_check": "PASSED",
        },
        "collector_version": "0.0.0-contract",
        "configuration_hash": CONFIG_HASH,
        "evidence_state": "RETRIEVED_BYTES_NOT_SUBSTANTIVELY_ADJUDICATED",
        "boundary": COLLECTOR_BOUNDARY,
    }


def valid_collection_failure() -> dict[str, Any]:
    return {
        "failure_id": FAILURE_ID,
        "request_id": REQUEST_ID,
        "source_id": "SRC-0001",
        "monitor_id": "MON-SRC-0001",
        "requested_url": "https://example.org/source",
        "failed_at": "2026-08-02T08:00:02Z",
        "failure_class": "SSRF_BLOCKED",
        "failure_message": "Redirect target resolved to a private address.",
        "retry_state": {
            "attempt_count": 1,
            "max_attempts": 3,
            "next_retry_at": "2026-08-02T08:05:00Z",
            "exhausted": False,
        },
        "collector_version": "0.0.0-contract",
        "configuration_hash": CONFIG_HASH,
        "boundary": COLLECTOR_BOUNDARY,
    }


def valid_quarantine_record() -> dict[str, Any]:
    return {
        "quarantine_id": QUARANTINE_ID,
        "result_id": RESULT_ID,
        "source_id": "SRC-0001",
        "monitor_id": "MON-SRC-0001",
        "captured_at": "2026-08-02T08:00:01Z",
        "sha256": CONTENT_SHA256,
        "size_bytes": 128,
        "original_filename": "source.html",
        "quarantine_path": "incoming/2026/08/02/source.html",
        "approval_state": "PENDING_HUMAN_APPROVAL",
        "approved_at": None,
        "approved_by": None,
        "rejection_reason": None,
        "collector_version": "0.0.0-contract",
        "configuration_hash": CONFIG_HASH,
        "boundary": COLLECTOR_BOUNDARY,
    }


@pytest.mark.parametrize(
    ("schema_name", "payload"),
    [
        (REQUEST_SCHEMA, valid_collection_request()),
        (RESULT_SCHEMA, valid_collection_result()),
        (FAILURE_SCHEMA, valid_collection_failure()),
        (QUARANTINE_SCHEMA, valid_quarantine_record()),
    ],
)
def test_collector_schemas_accept_valid_fixtures(schema_name: str, payload: dict[str, Any]) -> None:
    assert _validate(schema_name, payload) == []


@pytest.mark.parametrize(
    ("schema_name", "payload"),
    [
        (REQUEST_SCHEMA, valid_collection_request()),
        (RESULT_SCHEMA, valid_collection_result()),
        (FAILURE_SCHEMA, valid_collection_failure()),
        (QUARANTINE_SCHEMA, valid_quarantine_record()),
    ],
)
def test_collector_schemas_reject_extra_properties(schema_name: str, payload: dict[str, Any]) -> None:
    tampered = {**payload, "unexpected_field": True}
    errors = _validate(schema_name, tampered)
    assert errors
    assert any("Additional properties are not allowed" in error for error in errors)


@pytest.mark.parametrize(
    ("schema_name", "builder"),
    [
        (REQUEST_SCHEMA, valid_collection_request),
        (RESULT_SCHEMA, valid_collection_result),
        (FAILURE_SCHEMA, valid_collection_failure),
        (QUARANTINE_SCHEMA, valid_quarantine_record),
    ],
)
def test_collector_schemas_reject_missing_required_fields(schema_name: str, builder: Any) -> None:
    payload = builder()
    del payload["boundary"]
    errors = _validate(schema_name, payload)
    assert errors
    assert any("boundary" in error for error in errors)


def test_collection_request_rejects_private_ip_and_credentials() -> None:
    private_ip = valid_collection_request()
    private_ip["requested_url"] = "http://192.168.1.10/internal"
    assert _validate(REQUEST_SCHEMA, private_ip)

    credentialed = valid_collection_request()
    credentialed["requested_url"] = "https://user:secret@example.org/source"
    assert _validate(REQUEST_SCHEMA, credentialed)


def test_collection_result_rejects_path_traversal_and_private_redirects() -> None:
    traversal = valid_collection_result()
    traversal["original_filename"] = "../escape.html"
    assert _validate(RESULT_SCHEMA, traversal)

    unsafe_path = valid_collection_result()
    unsafe_path["quarantine_path"] = "../incoming/escape.html"
    assert _validate(RESULT_SCHEMA, unsafe_path)

    private_redirect = valid_collection_result()
    private_redirect["redirect_chain"] = ["http://127.0.0.1/admin"]
    assert _validate(RESULT_SCHEMA, private_redirect)


def test_collection_result_rejects_timezone_less_timestamp() -> None:
    payload = valid_collection_result()
    payload["retrieved_at"] = "2026-08-02T08:00:01"
    assert _validate(RESULT_SCHEMA, payload)


def test_quarantine_record_rejects_unapproved_handoff_shape() -> None:
    approved = valid_quarantine_record()
    approved["approval_state"] = "APPROVED_FOR_HANDOFF"
    approved["approved_at"] = "2026-08-02T09:00:00Z"
    approved["approved_by"] = "operator-local"
    assert _validate(QUARANTINE_SCHEMA, approved) == []

    rejected = valid_quarantine_record()
    rejected["original_filename"] = "..\\windows.exe"
    assert _validate(QUARANTINE_SCHEMA, rejected)


def test_collection_failure_requires_closed_retry_state() -> None:
    payload = valid_collection_failure()
    payload["retry_state"]["unexpected"] = True
    assert _validate(FAILURE_SCHEMA, payload)


def valid_structured_adapter_contract() -> dict[str, Any]:
    return {
        "adapter_id": "clinicaltrials_gov",
        "completeness": "PARTIAL",
        "capabilities": ["single_record_fetch", "normalized_record"],
        "allowed_hosts": ["clinicaltrials.gov"],
        "source_classes": ["CLINICAL_TRIAL_REGISTRY"],
        "boundary": "Test contract boundary; page capture is not registry completeness.",
    }


def valid_normalized_study_record() -> dict[str, Any]:
    digest = "d" * 64
    return {
        "record_kind": "NORMALIZED_CTGOV_STUDY",
        "nct_id": "NCT01234567",
        "brief_title": "Synthetic",
        "overall_status": "RECRUITING",
        "study_type": "INTERVENTIONAL",
        "last_update_post_date": "2026-01-15",
        "primary_completion_date": "2027-06",
        "enrollment_count": 42,
        "phase": "PHASE2",
        "field_digests": {
            "nct_id": digest,
            "brief_title": digest,
            "overall_status": digest,
            "study_type": digest,
            "last_update_post_date": digest,
            "primary_completion_date": digest,
            "enrollment_count": digest,
            "phase": digest,
        },
        "aggregate_digest": digest,
        "boundary": "Synthetic normalized study for schema tests only.",
    }


def test_structured_adapter_and_normalized_study_schemas_accept_valid() -> None:
    assert _validate(STRUCTURED_ADAPTER_CONTRACT_SCHEMA, valid_structured_adapter_contract()) == []
    assert _validate(NORMALIZED_STUDY_SCHEMA, valid_normalized_study_record()) == []


def test_structured_adapter_contract_rejects_unknown_completeness() -> None:
    payload = valid_structured_adapter_contract()
    payload["completeness"] = "COMPLETE_UNIVERSE"
    assert _validate(STRUCTURED_ADAPTER_CONTRACT_SCHEMA, payload)
