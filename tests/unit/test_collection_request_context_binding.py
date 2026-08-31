from __future__ import annotations

from tests.unit.test_collector_schemas import REQUEST_SCHEMA, _validate, valid_collection_request


def test_existing_registry_bound_request_remains_valid() -> None:
    request = valid_collection_request()
    assert "registry_sha256" in request
    assert "onboarding_manifest_sha256" not in request
    assert _validate(REQUEST_SCHEMA, request) == []


def test_pre_registry_onboarding_bound_request_is_valid() -> None:
    request = valid_collection_request()
    del request["registry_sha256"]
    request["monitor_id"] = "DMON-" + "1" * 32
    request["onboarding_manifest_sha256"] = "d" * 64
    assert _validate(REQUEST_SCHEMA, request) == []


def test_collection_request_rejects_both_context_bindings() -> None:
    request = valid_collection_request()
    request["onboarding_manifest_sha256"] = "d" * 64
    assert _validate(REQUEST_SCHEMA, request)


def test_collection_request_rejects_missing_context_binding() -> None:
    request = valid_collection_request()
    del request["registry_sha256"]
    assert _validate(REQUEST_SCHEMA, request)
