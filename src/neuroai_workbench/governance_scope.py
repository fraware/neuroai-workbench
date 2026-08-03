from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .events import append_event, load_events, verify_chain
from .util import (
    atomic_write_json,
    canonical_json_bytes,
    ensure_identifier,
    load_json,
    safe_join,
    sha256_bytes,
    sha256_file,
    utc_now,
)
from .workspace import Workspace

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
SCOPE_SCHEMA = "GOVERNANCE_SCOPE_MANIFEST.schema.json"
SCHEMA_VERSION = "1"

ROLE_OBJECT_TYPES = {
    "PREDECESSOR_RELEASE": "RELEASE",
    "SUCCESSOR_CANDIDATE": "SUCCESSOR_CANDIDATE",
    "DELTA": "DELTA",
    "REOPENING_REGISTER": "REOPENING_REGISTER",
    "PRODUCT_MANIFEST": "PRODUCT_MANIFEST",
    "WITHHELD_CLAIMS": "CLAIM_SET",
    "CORE_CYCLE_EXECUTION": "CORE_CYCLE_EXECUTION",
}
REQUIRED_ROLES = frozenset(
    {
        "PREDECESSOR_RELEASE",
        "SUCCESSOR_CANDIDATE",
        "DELTA",
        "REOPENING_REGISTER",
        "PRODUCT_MANIFEST",
        "WITHHELD_CLAIMS",
    }
)
STORAGE_BOUNDARIES = frozenset({"PUBLIC_GIT", "GENERATED_OUTPUT", "PROTECTED_WORKSPACE", "ARCHIVE"})
PROTECTED_PREFIX = "protected-ref:"
RUNTIME_PRIVATE_KEYS = frozenset({"_path"})

GOVERNANCE_SCOPE_BOUNDARY = (
    "Governance scope manifests bind byte identities and storage boundaries only. "
    "Digest validity does not authenticate a source, validate substantive claims, identify a reviewer, "
    "or authorize a successor release."
)


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(OPERATIONS_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any, schema_name: str) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_schema(schema_name))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _hash_record(value: dict[str, Any]) -> str:
    controlled = {
        key: item for key, item in value.items() if key != "manifest_sha256" and key not in RUNTIME_PRIVATE_KEYS
    }
    return sha256_bytes(canonical_json_bytes(controlled))


def _scopes_root(workspace: Workspace) -> Path:
    root = workspace.root / "governance" / "scopes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a 64-character lowercase hexadecimal digest")
    return value


def _validate_role_object_type(role: str, object_type: str) -> None:
    expected = ROLE_OBJECT_TYPES.get(role)
    if expected is None:
        raise ValueError(f"Unsupported governance scope role {role!r}")
    if object_type != expected:
        raise ValueError(f"Role {role!r} requires object_type {expected!r}")


def _relative_locator(path: Path, root: Path) -> str:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError("Governance scope path escapes its declared storage boundary root")
    locator = resolved_path.relative_to(resolved_root).as_posix()
    if not locator or locator == ".":
        raise ValueError("Governance scope locator must identify a file below the boundary root")
    return locator


def _validate_locator(storage_boundary: str, locator: str) -> None:
    if storage_boundary not in STORAGE_BOUNDARIES:
        raise ValueError(f"Unsupported storage boundary {storage_boundary!r}")
    if not locator:
        raise ValueError("Governance scope locator must not be empty")
    if storage_boundary == "PROTECTED_WORKSPACE":
        if not locator.startswith(PROTECTED_PREFIX):
            raise ValueError("Protected governance objects require an opaque protected-ref locator")
        ensure_identifier(locator.removeprefix(PROTECTED_PREFIX), "protected reference")
        return
    if locator.startswith(PROTECTED_PREFIX):
        raise ValueError("Opaque protected-ref locators are reserved for PROTECTED_WORKSPACE objects")
    if "\\" in locator:
        raise ValueError("Governance scope locators must use POSIX separators")
    pure = PurePosixPath(locator)
    if pure.is_absolute() or pure.as_posix() != locator or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Governance scope locator must be a normalized relative POSIX path")


def scope_object_for_path(
    *,
    role: str,
    label: str,
    object_type: str,
    path: Path,
    storage_boundary: str,
    boundary_root: Path | None = None,
    protected_ref: str | None = None,
    media_type: str | None = None,
) -> dict[str, Any]:
    """Build one content-addressed governance-scope object reference."""
    _validate_role_object_type(role, object_type)
    if not path.is_file():
        raise ValueError(f"Governance scope object does not exist: {path}")
    if not label.strip():
        raise ValueError("Governance scope object label must not be empty")
    if storage_boundary == "PROTECTED_WORKSPACE":
        if not protected_ref:
            raise ValueError("Protected governance objects require protected_ref")
        ensure_identifier(protected_ref, "protected reference")
        locator = f"{PROTECTED_PREFIX}{protected_ref}"
    else:
        if boundary_root is None:
            raise ValueError(f"{storage_boundary} objects require boundary_root")
        if protected_ref is not None:
            raise ValueError("protected_ref is valid only for PROTECTED_WORKSPACE objects")
        locator = _relative_locator(path, boundary_root)
    _validate_locator(storage_boundary, locator)
    reference: dict[str, Any] = {
        "role": role,
        "label": label.strip(),
        "object_type": object_type,
        "sha256": sha256_file(path),
        "storage_boundary": storage_boundary,
        "locator": locator,
    }
    if media_type:
        reference["media_type"] = media_type.strip()
    return reference


def _resolve_reference_path(
    reference: dict[str, Any],
    *,
    boundary_roots: Mapping[str, Path],
    protected_bindings: Mapping[str, Path],
) -> Path:
    boundary = str(reference.get("storage_boundary"))
    locator = str(reference.get("locator"))
    _validate_locator(boundary, locator)
    if boundary == "PROTECTED_WORKSPACE":
        path = protected_bindings.get(locator)
        if path is None:
            raise ValueError(f"No protected binding supplied for {locator}")
        return path
    root = boundary_roots.get(boundary)
    if root is None:
        raise ValueError(f"No verification root supplied for storage boundary {boundary}")
    return safe_join(root, *PurePosixPath(locator).parts)


def verify_governance_scope_manifest(
    manifest: dict[str, Any],
    *,
    boundary_roots: Mapping[str, Path],
    protected_bindings: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Verify schema, canonical hash, role integrity, locators, and referenced bytes."""
    protected_bindings = protected_bindings or {}
    unsupported_private_keys = sorted(
        key for key in manifest if key.startswith("_") and key not in RUNTIME_PRIVATE_KEYS
    )
    controlled = {key: value for key, value in manifest.items() if key not in RUNTIME_PRIVATE_KEYS}
    errors = list(_schema_errors(controlled, SCOPE_SCHEMA))
    if unsupported_private_keys:
        errors.append(
            {
                "code": "UNSUPPORTED_PRIVATE_FIELDS",
                "path": "",
                "fields": unsupported_private_keys,
            }
        )
    warnings: list[str] = []
    roles: list[str] = []

    if controlled.get("manifest_sha256") != _hash_record(controlled):
        errors.append({"code": "MANIFEST_SHA256_MISMATCH", "path": "manifest_sha256"})
    if controlled.get("boundary") != GOVERNANCE_SCOPE_BOUNDARY:
        errors.append({"code": "AUTHORITY_BOUNDARY_MISMATCH", "path": "boundary"})

    objects = controlled.get("objects")
    if not isinstance(objects, list):
        objects = []
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            errors.append({"code": "OBJECT_REFERENCE_INVALID", "path": f"objects.{index}"})
            continue
        role = str(item.get("role"))
        object_type = str(item.get("object_type"))
        roles.append(role)
        expected_type = ROLE_OBJECT_TYPES.get(role)
        if expected_type is None:
            errors.append({"code": "UNSUPPORTED_OBJECT_ROLE", "path": f"objects.{index}.role", "role": role})
        elif object_type != expected_type:
            errors.append(
                {
                    "code": "ROLE_OBJECT_TYPE_MISMATCH",
                    "path": f"objects.{index}.object_type",
                    "role": role,
                    "expected": expected_type,
                    "observed": object_type,
                }
            )
        try:
            _validate_sha256(item.get("sha256"), f"objects.{index}.sha256")
            path = _resolve_reference_path(
                item,
                boundary_roots=boundary_roots,
                protected_bindings=protected_bindings,
            )
        except ValueError as exc:
            errors.append({"code": "OBJECT_REFERENCE_INVALID", "path": f"objects.{index}", "message": str(exc)})
            continue
        if not path.is_file():
            errors.append(
                {
                    "code": "REFERENCED_OBJECT_MISSING",
                    "path": f"objects.{index}.locator",
                    "role": role,
                    "locator": item.get("locator"),
                }
            )
            continue
        observed = sha256_file(path)
        if observed != item.get("sha256"):
            errors.append(
                {
                    "code": "REFERENCED_OBJECT_SHA256_MISMATCH",
                    "path": f"objects.{index}.sha256",
                    "role": role,
                    "expected": item.get("sha256"),
                    "observed": observed,
                }
            )

    duplicate_roles = sorted({role for role in roles if roles.count(role) > 1})
    if duplicate_roles:
        errors.append({"code": "DUPLICATE_LOGICAL_ROLES", "path": "objects", "roles": duplicate_roles})
    if roles != sorted(roles):
        errors.append({"code": "OBJECT_ORDER_NONCANONICAL", "path": "objects"})
    digests = [
        str(item.get("sha256")) for item in objects if isinstance(item, dict) and isinstance(item.get("sha256"), str)
    ]
    duplicate_digests = sorted({digest for digest in digests if digests.count(digest) > 1})
    if duplicate_digests:
        errors.append(
            {
                "code": "DUPLICATE_OBJECT_DIGESTS",
                "path": "objects",
                "digests": duplicate_digests,
            }
        )
    missing_roles = sorted(REQUIRED_ROLES - set(roles))
    if missing_roles:
        errors.append({"code": "REQUIRED_ROLES_MISSING", "path": "objects", "roles": missing_roles})
    if controlled.get("release_authorization_performed") is not False:
        errors.append({"code": "RELEASE_AUTHORIZATION_PROHIBITED", "path": "release_authorization_performed"})
    if not any(
        str(item.get("storage_boundary")) == "PROTECTED_WORKSPACE" for item in objects if isinstance(item, dict)
    ):
        warnings.append("No protected object is bound in this governance scope.")

    return {
        "valid": not errors,
        "scope_id": controlled.get("scope_id"),
        "manifest_sha256": controlled.get("manifest_sha256"),
        "counts": {
            "objects": len(objects),
            "roles": len(set(roles)),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
        "release_authorization_performed": False,
        "boundary": GOVERNANCE_SCOPE_BOUNDARY,
    }


def record_governance_scope_manifest(
    workspace: Workspace,
    *,
    scope_label: str,
    objects: list[dict[str, Any]],
    boundary_roots: Mapping[str, Path],
    protected_bindings: Mapping[str, Path] | None = None,
    recorded_by: str = "local-user",
    actor: str | None = None,
) -> dict[str, Any]:
    """Persist one append-only, non-authorizing governance scope manifest."""
    ensure_identifier(recorded_by, "recorded_by")
    actor = actor or recorded_by
    ensure_identifier(actor, "actor")
    if not scope_label.strip():
        raise ValueError("Governance scope label must not be empty")
    scope_id = f"GOVSCOPE-{uuid4().hex}"
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope_id": scope_id,
        "scope_label": scope_label.strip(),
        "created_at": utc_now(),
        "created_by": recorded_by,
        "objects": sorted((dict(item) for item in objects), key=lambda item: str(item.get("role"))),
        "release_authorization_performed": False,
        "authority_profile": "SCOPE_INTEGRITY_ONLY",
        "boundary": GOVERNANCE_SCOPE_BOUNDARY,
    }
    manifest["manifest_sha256"] = _hash_record(manifest)
    verification = verify_governance_scope_manifest(
        manifest,
        boundary_roots=boundary_roots,
        protected_bindings=protected_bindings,
    )
    if not verification["valid"]:
        raise ValueError(
            f"Governance scope manifest failed verification: {json.dumps(verification['errors'], ensure_ascii=False)}"
        )

    output = _scopes_root(workspace) / f"{scope_id}.json"
    if output.exists():
        raise ValueError(f"A governance scope manifest already exists: {scope_id}")
    atomic_write_json(output, manifest)
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_SCOPE_RECORDED",
        actor,
        {
            "scope_id": scope_id,
            "manifest_sha256": manifest["manifest_sha256"],
            "object_count": len(objects),
            "release_authorization_performed": False,
        },
    )
    return {"manifest": manifest, "path": str(output), "verification": verification}


def load_governance_scope_manifests(workspace: Workspace) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(_scopes_root(workspace).glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict):
            record = cast(dict[str, Any], value)
            record["_path"] = str(path)
            records.append(record)
    return records


def verify_governance_scope_records(
    workspace: Workspace,
    *,
    boundary_roots: Mapping[str, Path],
    protected_bindings: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Verify every persisted scope plus its append-only event binding."""
    records = load_governance_scope_manifests(workspace)
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    reports: list[dict[str, Any]] = []

    try:
        events = load_events(workspace.root / "events.jsonl")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        events = []
        errors.append(f"event log load failed: {exc}")
    scope_events = {
        (
            str(event.get("payload", {}).get("scope_id")),
            str(event.get("payload", {}).get("manifest_sha256")),
        )
        for event in events
        if event.get("action") == "GOVERNANCE_SCOPE_RECORDED" and isinstance(event.get("payload"), dict)
    }

    for record in records:
        scope_id = str(record.get("scope_id"))
        if scope_id in seen_ids:
            errors.append(f"scope {scope_id}: duplicate scope_id")
        seen_ids.add(scope_id)
        report = verify_governance_scope_manifest(
            record,
            boundary_roots=boundary_roots,
            protected_bindings=protected_bindings,
        )
        reports.append(report)
        if not report["valid"]:
            errors.append(f"scope {scope_id}: manifest verification failed")
        event_key = (scope_id, str(record.get("manifest_sha256")))
        if event_key not in scope_events:
            errors.append(f"scope {scope_id}: matching GOVERNANCE_SCOPE_RECORDED event is missing")
        warnings.extend(f"scope {scope_id}: {warning}" for warning in report["warnings"])

    chain = verify_chain(workspace.root / "events.jsonl")
    if not chain["valid"] or not chain.get("trailer_valid", False):
        errors.extend(f"event chain: {error}" for error in chain["errors"])
        errors.extend(f"event chain trailer: {error}" for error in chain.get("trailer_errors", []))

    return {
        "valid": not errors,
        "counts": {
            "scope_manifests": len(records),
            "verified_scope_manifests": sum(1 for report in reports if report["valid"]),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "scopes": reports,
        "errors": errors,
        "warnings": warnings,
        "event_chain_valid": chain["valid"] and chain.get("trailer_valid", False),
        "release_authorization_performed": False,
        "boundary": GOVERNANCE_SCOPE_BOUNDARY,
    }
