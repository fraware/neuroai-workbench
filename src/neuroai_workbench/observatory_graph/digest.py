from __future__ import annotations

from typing import Any

from ..util import canonical_json_bytes, sha256_bytes

DIGEST_FIELD = "canonical_sha256"


def object_digest(record: dict[str, Any]) -> str:
    controlled = {key: value for key, value in record.items() if key != DIGEST_FIELD}
    return sha256_bytes(canonical_json_bytes(controlled))


def attach_digest(record: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in record.items() if key != DIGEST_FIELD}
    digest = object_digest(payload)
    return {**payload, DIGEST_FIELD: digest}


def assert_digest(record: dict[str, Any]) -> str:
    expected = object_digest(record)
    observed = record.get(DIGEST_FIELD)
    if observed != expected:
        raise ValueError("Observatory-graph object digest does not match canonical JSON")
    return expected
