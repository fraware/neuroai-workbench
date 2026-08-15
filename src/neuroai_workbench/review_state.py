"""Deterministic, integrity-addressed read model for stored review state."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from .events import verify_chain
from .review_queue import PROJECTION_VERSION, QUEUE_ROOT_REL, rebuild_queue_projection, verify_review_queue
from .util import canonical_json_bytes, load_json, sha256_bytes

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
SNAPSHOT_SCHEMA = "REVIEW_STATE_SNAPSHOT.schema.json"
REVIEW_STATE_SNAPSHOT_VERSION = "1"
REVIEW_STATE_AUTHORITY_PROFILE = "LOCAL_READ_MODEL_NO_AUTHORITY"
REVIEW_STATE_SNAPSHOT_BOUNDARY = (
    "This snapshot is a deterministic read model over stored local review records. "
    "Its digest establishes canonical content identity only; it does not authenticate a reviewer, "
    "authorize a decision, prove institutional provenance, or establish scientific, regulatory, clinical, "
    "conformance, or release conclusions."
)

_RECORD_SPECS: dict[str, tuple[str, str, str | None]] = {
    "profiles": ("profile_id", "REVIEW_PROFILE.schema.json", "profile_sha256"),
    "queue_items": ("item_id", "REVIEW_QUEUE_ITEM.schema.json", None),
    "leases": ("lease_id", "REVIEW_LEASE.schema.json", "lease_sha256"),
    "lease_releases": ("release_id", "REVIEW_LEASE_RELEASE.schema.json", "release_sha256"),
    "opinions": ("opinion_id", "REVIEW_OPINION.schema.json", "opinion_sha256"),
}


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(OPERATIONS_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any, schema_name: str) -> list[str]:
    validator = Draft202012Validator(_schema(schema_name))
    errors: list[str] = []
    for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{path}: {error.message}")
    return errors


def _sanitize(value: Any, *, path: str = "<root>") -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key in sorted(value):
            if key == "_path":
                continue
            if key.startswith("_"):
                raise ValueError(f"Internal field {path}.{key} is not allowed in review-state snapshots")
            clean[key] = _sanitize(value[key], path=f"{path}.{key}")
        return clean
    if isinstance(value, list):
        return [_sanitize(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def _stored_records(workspace: Path, directory: str) -> list[dict[str, Any]]:
    root = workspace / QUEUE_ROOT_REL / directory
    if not root.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        value = load_json(path)
        if not isinstance(value, dict):
            raise ValueError(f"Stored review record must be a JSON object: {path.name}")
        clean = _sanitize(value)
        if not isinstance(clean, dict):
            raise ValueError(f"Stored review record could not be normalized: {path.name}")
        records.append(clean)
    return records


def _ordered_records(records: list[dict[str, Any]], id_field: str) -> list[dict[str, Any]]:
    for record in records:
        identifier = record.get(id_field)
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"Review record is missing required identifier {id_field!r}")
    return sorted(records, key=lambda item: str(item[id_field]))


def _record_digest(record: dict[str, Any], digest_field: str) -> str:
    controlled = {key: value for key, value in record.items() if key != digest_field and not key.startswith("_")}
    return sha256_bytes(canonical_json_bytes(controlled))


def _snapshot_digest(snapshot: dict[str, Any]) -> str:
    controlled = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    return sha256_bytes(canonical_json_bytes(controlled))


def _internal_fields(value: Any, *, path: str = "<root>") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}"
            if key.startswith("_"):
                found.append(current)
            found.extend(_internal_fields(item, path=current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_internal_fields(item, path=f"{path}[{index}]"))
    return found


def build_review_state_snapshot(workspace: Path) -> dict[str, Any]:
    source_verification = verify_review_queue(workspace)
    if not source_verification.get("valid"):
        errors = source_verification.get("errors") or ["unknown review-state integrity failure"]
        raise ValueError(f"Review queue integrity verification failed: {'; '.join(str(error) for error in errors)}")

    event_report = verify_chain(workspace / QUEUE_ROOT_REL / "events.jsonl")
    if not event_report.get("valid"):
        errors = event_report.get("errors") or ["unknown event-chain integrity failure"]
        raise ValueError(f"Review event-chain verification failed: {'; '.join(str(error) for error in errors)}")

    records = {
        "profiles": _ordered_records(_stored_records(workspace, "profiles"), "profile_id"),
        "queue_items": _ordered_records(
            [cast(dict[str, Any], _sanitize(item)) for item in rebuild_queue_projection(workspace)],
            "item_id",
        ),
        "leases": _ordered_records(_stored_records(workspace, "leases"), "lease_id"),
        "lease_releases": _ordered_records(_stored_records(workspace, "lease_releases"), "release_id"),
        "opinions": _ordered_records(_stored_records(workspace, "opinions"), "opinion_id"),
    }
    counts = {key: len(value) for key, value in records.items()}
    snapshot: dict[str, Any] = {
        "snapshot_version": REVIEW_STATE_SNAPSHOT_VERSION,
        "projection_version": PROJECTION_VERSION,
        "source_integrity": "VERIFIED",
        "authority_profile": REVIEW_STATE_AUTHORITY_PROFILE,
        "event_chain": {
            "event_count": int(event_report["event_count"]),
            "head_hash": str(event_report["head_hash"]),
        },
        "counts": counts,
        "records": records,
        "boundary": REVIEW_STATE_SNAPSHOT_BOUNDARY,
    }
    snapshot["snapshot_sha256"] = _snapshot_digest(snapshot)

    verification = verify_review_state_snapshot(snapshot)
    if not verification["valid"]:
        raise ValueError(f"Generated review-state snapshot is invalid: {'; '.join(verification['errors'])}")
    return snapshot


def verify_review_state_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {
            "valid": False,
            "errors": ["snapshot must be a JSON object"],
            "snapshot_sha256": None,
            "boundary": REVIEW_STATE_SNAPSHOT_BOUNDARY,
        }

    errors = [f"schema: {error}" for error in _schema_errors(snapshot, SNAPSHOT_SCHEMA)]
    internal = _internal_fields(snapshot.get("records"))
    errors.extend(f"internal field is forbidden: {path}" for path in internal)

    observed_digest = snapshot.get("snapshot_sha256")
    if isinstance(observed_digest, str) and observed_digest != _snapshot_digest(snapshot):
        errors.append("snapshot_sha256 mismatch")

    counts = snapshot.get("counts")
    records = snapshot.get("records")
    if isinstance(counts, dict) and isinstance(records, dict):
        for category, (id_field, schema_name, digest_field) in _RECORD_SPECS.items():
            category_records = records.get(category)
            if not isinstance(category_records, list):
                continue
            if counts.get(category) != len(category_records):
                errors.append(f"counts.{category} does not match records.{category}")

            identifiers: list[str] = []
            for index, record in enumerate(category_records):
                if not isinstance(record, dict):
                    continue
                errors.extend(
                    f"records.{category}[{index}] schema: {error}" for error in _schema_errors(record, schema_name)
                )
                identifier = record.get(id_field)
                if isinstance(identifier, str):
                    identifiers.append(identifier)
                if digest_field is not None:
                    record_digest = record.get(digest_field)
                    if isinstance(record_digest, str) and record_digest != _record_digest(record, digest_field):
                        errors.append(f"records.{category}[{index}].{digest_field} mismatch")

            if identifiers != sorted(identifiers):
                errors.append(f"records.{category} is not ordered by {id_field}")
            if len(identifiers) != len(set(identifiers)):
                errors.append(f"records.{category} contains duplicate {id_field} values")

    return {
        "valid": not errors,
        "errors": errors,
        "snapshot_sha256": observed_digest if isinstance(observed_digest, str) else None,
        "boundary": REVIEW_STATE_SNAPSHOT_BOUNDARY,
    }
