from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from ..events import append_event, verify_chain
from ..util import atomic_write_json, canonical_json_bytes, ensure_identifier, load_json, safe_join, sha256_bytes, utc_now
from .errors import AmbiguousResolutionError, EntityRegistryError, FuzzyMergeRefusedError, OverwriteRefusedError
from .schemas import (
    validate_alias,
    validate_entity,
    validate_entity_event,
    validate_identifier,
    validate_registry_container,
)

ENTITY_BOUNDARY = (
    "Entity registry records identify likely record correspondence only. They do not establish technical capability, "
    "ownership control beyond cited evidence, regulatory status, clinical benefit, or system conformance."
)

ENTITY_TYPES = frozenset({"ORGANIZATION", "SYSTEM", "MODEL", "PRODUCT", "TRIAL", "REGULATORY_RECORD", "SOURCE"})
ALIAS_KINDS = frozenset({"LEGAL_NAME", "TRADE_NAME", "HISTORICAL_NAME", "ABBREVIATION", "NORMALIZED_MENTION"})
IDENTIFIER_SCHEMES = frozenset({"DOMAIN", "LEI", "ORCID", "TRIAL_ID", "PATENT", "REGISTRY_ID", "CUSTOM"})
RESOLUTION_STATES = frozenset({"EXISTING_ENTITY", "NEW_ENTITY", "AMBIGUOUS", "DUPLICATE_CANDIDATE", "UNRESOLVED"})
EXACT_MATCH_MODES = frozenset({"ENTITY_ID", "ALIAS_ID", "IDENTIFIER"})


def _entities_root(workspace: Path) -> Path:
    return workspace / "observatory" / "entities"


def _registry_path(workspace: Path) -> Path:
    return _entities_root(workspace) / "registry.json"


def _state_path(workspace: Path) -> Path:
    return _entities_root(workspace) / "state.json"


def _events_path(workspace: Path) -> Path:
    return _entities_root(workspace) / "events.jsonl"


def _entity_path(workspace: Path, entity_id: str) -> Path:
    ensure_identifier(entity_id, "entity_id")
    return safe_join(_entities_root(workspace) / "records", entity_id + ".json")


def _alias_path(workspace: Path, alias_id: str) -> Path:
    ensure_identifier(alias_id, "alias_id")
    return safe_join(_entities_root(workspace) / "aliases", alias_id + ".json")


def _identifier_path(workspace: Path, identifier_id: str) -> Path:
    ensure_identifier(identifier_id, "identifier_id")
    return safe_join(_entities_root(workspace) / "identifiers", identifier_id + ".json")


def _require_valid(result: list[dict[str, Any]] | dict[str, Any], label: str) -> None:
    if isinstance(result, dict):
        if result.get("valid") is False or result.get("errors"):
            raise ValueError(f"{label} failed validation: {json.dumps(result, ensure_ascii=False)}")
        return
    if result:
        raise ValueError(f"{label} failed validation: {json.dumps(result, ensure_ascii=False)}")


def _append_registry_event(
    workspace: Path, event_type: str, entity_id: str, actor: str, payload: dict[str, Any]
) -> dict[str, Any]:
    event_record = {
        "event_id": f"ENTEVT-{uuid4().hex}",
        "event_type": event_type,
        "entity_id": entity_id,
        "timestamp": utc_now(),
        "actor": actor,
        "payload": payload,
        "boundary": ENTITY_BOUNDARY,
    }
    _require_valid(validate_entity_event(event_record), "Entity event")
    chain_event = append_event(_events_path(workspace), event_type, actor, {"entity_id": entity_id, **payload})
    return {"event": event_record, "chain_event": chain_event}


def load_registry(workspace: Path) -> dict[str, Any]:
    path = _registry_path(workspace)
    if not path.is_file():
        raise ValueError("Entity registry is not initialized")
    return cast(dict[str, Any], load_json(path))


def registry_status(workspace: Path) -> dict[str, Any]:
    registry = load_registry(workspace)
    state = cast(dict[str, Any], load_json(_state_path(workspace)))
    calculated = sha256_bytes(canonical_json_bytes(registry))
    if state.get("registry_sha256") != calculated:
        raise ValueError("Entity registry hash mismatch; registry may have been altered outside controlled writes")
    chain = verify_chain(_events_path(workspace))
    if not chain["valid"]:
        raise ValueError(f"Entity event chain is invalid: {chain['errors']}")
    entities = registry.get("entities", [])
    return {
        "initialized": True,
        "entity_count": len(entities) if isinstance(entities, list) else 0,
        "registry_sha256": calculated,
        "event_count": chain["event_count"],
        "boundary": ENTITY_BOUNDARY,
    }


def validate_registry(value: Any) -> dict[str, Any]:
    errors = validate_registry_container(value)
    warnings: list[dict[str, Any]] = []
    entities = value.get("entities") if isinstance(value, dict) else None
    if not isinstance(entities, list):
        return {"valid": False, "errors": errors, "warnings": warnings, "counts": {}}

    entity_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    type_counts: dict[str, int] = {}
    for index, record in enumerate(entities):
        path = f"entities[{index}]"
        if not isinstance(record, dict):
            continue
        for item in validate_entity(record):
            errors.append({**item, "path": f"{path}.{item['path']}" if item.get("path") else path})
        entity_id = record.get("entity_id")
        if isinstance(entity_id, str):
            try:
                ensure_identifier(entity_id, "entity_id")
            except ValueError as exc:
                errors.append({"code": "INVALID_IDENTIFIER", "path": f"{path}.entity_id", "message": str(exc)})
            if entity_id in entity_ids:
                duplicate_ids.add(entity_id)
            entity_ids.add(entity_id)
        entity_type = record.get("entity_type")
        if isinstance(entity_type, str):
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
            if entity_type not in ENTITY_TYPES:
                errors.append({"code": "UNSUPPORTED_ENTITY_TYPE", "path": f"{path}.entity_type", "value": entity_type})
    if duplicate_ids:
        errors.append({"code": "DUPLICATE_ENTITY_ID", "path": "entities", "identifiers": sorted(duplicate_ids)})
    declared = value.get("metadata", {}).get("record_count") if isinstance(value, dict) else None
    if isinstance(declared, int) and declared != len(entities):
        errors.append({"code": "RECORD_COUNT_MISMATCH", "path": "metadata.record_count", "declared": declared, "observed": len(entities)})
    return {"valid": not errors, "errors": errors, "warnings": warnings, "counts": {"entities": len(entities), "entity_types": type_counts}, "boundary": ENTITY_BOUNDARY}


def initialize_registry(workspace: Path, seed: dict[str, Any] | None = None, actor: str = "local-user") -> dict[str, Any]:
    root = _entities_root(workspace)
    for relative in ("records", "aliases", "identifiers"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    registry = seed or {
        "metadata": {"title": "NeuroAI entity registry", "version": "1.0", "status": "CONTROLLED_OPERATIONAL_INPUT", "record_count": 0, "boundary": ENTITY_BOUNDARY},
        "entities": [],
    }
    validation = validate_registry(registry)
    if not validation["valid"]:
        raise ValueError(f"Entity registry seed is invalid: {json.dumps(validation, ensure_ascii=False)}")
    registry_path = _registry_path(workspace)
    registry_hash = sha256_bytes(canonical_json_bytes(registry))
    if registry_path.exists():
        existing = cast(dict[str, Any], load_json(registry_path))
        if sha256_bytes(canonical_json_bytes(existing)) != registry_hash:
            raise OverwriteRefusedError("Entity registry already exists with different canonical content")
    else:
        atomic_write_json(registry_path, registry)
    state_path = _state_path(workspace)
    if not state_path.exists():
        atomic_write_json(state_path, {"version": "1", "registry_sha256": registry_hash, "boundary": ENTITY_BOUNDARY})
    events_path = _events_path(workspace)
    if not events_path.exists():
        append_event(events_path, "ENTITY_REGISTRY_INITIALIZED", actor, {"registry_sha256": registry_hash})
    return registry_status(workspace)


def load_entity(workspace: Path, entity_id: str) -> dict[str, Any]:
    path = _entity_path(workspace, entity_id)
    if not path.is_file():
        raise ValueError(f"Unknown entity {entity_id!r}")
    entity = cast(dict[str, Any], load_json(path))
    _require_valid(validate_entity(entity), "Entity record")
    if entity.get("entity_id") != entity_id:
        raise ValueError("Entity record identifier mismatch")
    return entity


def register_entity(
    workspace: Path, entity_type: str, display_name: str, *, entity_id: str | None = None, jurisdiction: str | None = None, actor: str = "local-user"
) -> dict[str, Any]:
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unsupported entity_type {entity_type!r}")
    clean_name = display_name.strip()
    if not clean_name:
        raise ValueError("display_name must not be empty")
    assigned_id = ensure_identifier(entity_id or f"ENT-{uuid4().hex[:12].upper()}", "entity_id")
    path = _entity_path(workspace, assigned_id)
    if path.exists():
        raise OverwriteRefusedError(f"Entity {assigned_id!r} already exists; use successor registration instead")
    entity = {
        "entity_id": assigned_id, "entity_type": entity_type, "display_name": clean_name, "status": "ACTIVE", "created_at": utc_now(),
        "predecessor_entity_id": None, "successor_entity_id": None, "jurisdiction": jurisdiction, "boundary": ENTITY_BOUNDARY,
    }
    _require_valid(validate_entity(entity), "Entity record")
    atomic_write_json(path, entity)
    registry = load_registry(workspace)
    entities = registry.setdefault("entities", [])
    if not isinstance(entities, list):
        raise EntityRegistryError("Registry entities container is invalid")
    if any(item.get("entity_id") == assigned_id for item in entities if isinstance(item, dict)):
        raise OverwriteRefusedError(f"Entity index already contains {assigned_id!r}")
    entities.append({"entity_id": assigned_id, "entity_type": entity_type, "display_name": clean_name, "status": "ACTIVE", "created_at": entity["created_at"], "boundary": ENTITY_BOUNDARY})
    registry["metadata"]["record_count"] = len(entities)
    _require_valid(validate_registry(registry), "Entity registry")
    atomic_write_json(_registry_path(workspace), registry)
    atomic_write_json(_state_path(workspace), {"version": "1", "registry_sha256": sha256_bytes(canonical_json_bytes(registry)), "boundary": ENTITY_BOUNDARY})
    event = _append_registry_event(workspace, "ENTITY_REGISTERED", assigned_id, actor, {"entity_type": entity_type, "display_name": clean_name})
    return {"entity": entity, "event": event}


def register_alias(
    workspace: Path, entity_id: str, alias_text: str, alias_kind: str, *, alias_id: str | None = None, jurisdiction: str | None = None, evidence_ref: str | None = None, actor: str = "local-user"
) -> dict[str, Any]:
    load_entity(workspace, entity_id)
    if alias_kind not in ALIAS_KINDS:
        raise ValueError(f"Unsupported alias_kind {alias_kind!r}")
    clean_text = alias_text.strip()
    if not clean_text:
        raise ValueError("alias_text must not be empty")
    assigned_id = ensure_identifier(alias_id or f"ALIAS-{uuid4().hex[:12].upper()}", "alias_id")
    path = _alias_path(workspace, assigned_id)
    if path.exists():
        raise OverwriteRefusedError(f"Alias {assigned_id!r} already exists; append a successor alias instead")
    alias = {
        "alias_id": assigned_id, "entity_id": entity_id, "alias_text": clean_text, "alias_kind": alias_kind, "status": "ACTIVE", "registered_at": utc_now(),
        "jurisdiction": jurisdiction, "evidence_ref": evidence_ref, "effective_from": None, "effective_to": None, "predecessor_alias_id": None, "boundary": ENTITY_BOUNDARY,
    }
    _require_valid(validate_alias(alias), "Alias record")
    atomic_write_json(path, alias)
    event = _append_registry_event(workspace, "ALIAS_REGISTERED", entity_id, actor, {"alias_id": assigned_id, "alias_kind": alias_kind})
    return {"alias": alias, "event": event}


def register_identifier(
    workspace: Path, entity_id: str, scheme: str, value: str, *, identifier_id: str | None = None, jurisdiction: str | None = None, evidence_ref: str | None = None, actor: str = "local-user"
) -> dict[str, Any]:
    load_entity(workspace, entity_id)
    if scheme not in IDENTIFIER_SCHEMES:
        raise ValueError(f"Unsupported scheme {scheme!r}")
    clean_value = value.strip()
    if not clean_value:
        raise ValueError("value must not be empty")
    assigned_id = ensure_identifier(identifier_id or f"ID-{uuid4().hex[:12].upper()}", "identifier_id")
    path = _identifier_path(workspace, assigned_id)
    if path.exists():
        raise OverwriteRefusedError(f"Identifier {assigned_id!r} already exists; append a successor identifier instead")
    for existing_path in (_entities_root(workspace) / "identifiers").glob("*.json"):
        existing = cast(dict[str, Any], load_json(existing_path))
        if existing.get("scheme") == scheme and existing.get("value") == clean_value and existing.get("status") == "ACTIVE" and existing.get("entity_id") != entity_id:
            raise AmbiguousResolutionError(f"Active identifier {scheme}={clean_value!r} already maps to entity {existing.get('entity_id')!r}")
    identifier = {
        "identifier_id": assigned_id, "entity_id": entity_id, "scheme": scheme, "value": clean_value, "status": "ACTIVE", "registered_at": utc_now(),
        "jurisdiction": jurisdiction, "evidence_ref": evidence_ref, "predecessor_identifier_id": None, "boundary": ENTITY_BOUNDARY,
    }
    _require_valid(validate_identifier(identifier), "Identifier record")
    atomic_write_json(path, identifier)
    event = _append_registry_event(workspace, "IDENTIFIER_REGISTERED", entity_id, actor, {"identifier_id": assigned_id, "scheme": scheme, "value": clean_value})
    return {"identifier": identifier, "event": event}


def refuse_fuzzy_merge(workspace: Path, *, reason: str, actor: str = "local-user", entity_id: str = "UNRESOLVED", context: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_identifier(entity_id, "entity_id")
    payload = {"reason": reason.strip(), "context": context or {}}
    if not payload["reason"]:
        raise ValueError("reason must not be empty")
    _append_registry_event(workspace, "FUZZY_MERGE_REFUSED", entity_id, actor, payload)
    raise FuzzyMergeRefusedError(reason) from None


def resolve_exact(
    workspace: Path, *, entity_id: str | None = None, alias_id: str | None = None, identifier_scheme: str | None = None, identifier_value: str | None = None,
    match_mode: str | None = None, normalized_name: str | None = None, similarity_threshold: float | None = None, actor: str = "local-user",
) -> dict[str, Any]:
    if normalized_name is not None:
        refuse_fuzzy_merge(workspace, reason="Normalized-name matching is not supported; use exact alias_id or identifier", actor=actor, context={"normalized_name": normalized_name})
    if similarity_threshold is not None:
        refuse_fuzzy_merge(workspace, reason="Similarity thresholds are not supported; exact identifier match required", actor=actor, context={"similarity_threshold": similarity_threshold})
    if match_mode is not None and match_mode not in EXACT_MATCH_MODES:
        refuse_fuzzy_merge(workspace, reason=f"Unsupported or non-exact match_mode {match_mode!r}", actor=actor, context={"match_mode": match_mode})
    provided = [entity_id, alias_id, (identifier_scheme, identifier_value)]
    if sum(1 for item in provided if item not in (None, (None, None))) != 1:
        raise ValueError("Provide exactly one of entity_id, alias_id, or identifier_scheme+identifier_value")
    if entity_id is not None:
        entity = load_entity(workspace, entity_id)
        _append_registry_event(workspace, "RESOLUTION_ATTEMPTED", entity_id, actor, {"state": "EXISTING_ENTITY", "match_mode": "ENTITY_ID"})
        return {"state": "EXISTING_ENTITY", "match_mode": "ENTITY_ID", "entity_id": entity_id, "entity": entity, "boundary": ENTITY_BOUNDARY}
    if alias_id is not None:
        path = _alias_path(workspace, alias_id)
        if not path.is_file():
            _append_registry_event(workspace, "RESOLUTION_ATTEMPTED", "UNRESOLVED", actor, {"state": "UNRESOLVED", "match_mode": "ALIAS_ID", "alias_id": alias_id})
            return {"state": "UNRESOLVED", "match_mode": "ALIAS_ID", "entity_id": None, "boundary": ENTITY_BOUNDARY}
        alias = cast(dict[str, Any], load_json(path))
        _require_valid(validate_alias(alias), "Alias record")
        if alias.get("alias_id") != alias_id:
            raise ValueError("Alias record identifier mismatch")
        resolved_entity_id = str(alias["entity_id"])
        entity = load_entity(workspace, resolved_entity_id)
        _append_registry_event(workspace, "RESOLUTION_ATTEMPTED", resolved_entity_id, actor, {"state": "EXISTING_ENTITY", "match_mode": "ALIAS_ID", "alias_id": alias_id})
        return {"state": "EXISTING_ENTITY", "match_mode": "ALIAS_ID", "entity_id": resolved_entity_id, "alias": alias, "entity": entity, "boundary": ENTITY_BOUNDARY}
    if identifier_scheme is None or identifier_value is None:
        raise ValueError("identifier_scheme and identifier_value must be supplied together")
    if identifier_scheme not in IDENTIFIER_SCHEMES:
        raise ValueError(f"Unsupported identifier_scheme {identifier_scheme!r}")
    matches: list[dict[str, Any]] = []
    for existing_path in (_entities_root(workspace) / "identifiers").glob("*.json"):
        existing = cast(dict[str, Any], load_json(existing_path))
        if (
            existing.get("scheme") == identifier_scheme
            and existing.get("value") == identifier_value.strip()
            and existing.get("status") == "ACTIVE"
        ):
            matches.append(existing)
    if not matches:
        _append_registry_event(workspace, "RESOLUTION_ATTEMPTED", "UNRESOLVED", actor, {"state": "UNRESOLVED", "match_mode": "IDENTIFIER", "scheme": identifier_scheme, "value": identifier_value.strip()})
        return {"state": "UNRESOLVED", "match_mode": "IDENTIFIER", "entity_id": None, "boundary": ENTITY_BOUNDARY}
    entity_ids = {str(item["entity_id"]) for item in matches}
    if len(entity_ids) > 1:
        raise AmbiguousResolutionError(f"Identifier {identifier_scheme}={identifier_value.strip()!r} maps to multiple entities")
    resolved_entity_id = next(iter(entity_ids))
    entity = load_entity(workspace, resolved_entity_id)
    _append_registry_event(workspace, "RESOLUTION_ATTEMPTED", resolved_entity_id, actor, {"state": "EXISTING_ENTITY", "match_mode": "IDENTIFIER", "scheme": identifier_scheme, "value": identifier_value.strip()})
    return {"state": "EXISTING_ENTITY", "match_mode": "IDENTIFIER", "entity_id": resolved_entity_id, "identifier": matches[0], "entity": entity, "boundary": ENTITY_BOUNDARY}


def assert_record_immutable(path: Path, expected: dict[str, Any]) -> None:
    if not path.is_file():
        raise OverwriteRefusedError(f"Missing canonical record at {path}")
    current = load_json(path)
    if sha256_bytes(canonical_json_bytes(current)) != sha256_bytes(canonical_json_bytes(expected)):
        raise OverwriteRefusedError(f"Canonical record at {path} was altered")
