from __future__ import annotations

from typing import Any

GRAPH_BOUNDARY = (
    "Observatory-graph objects are schema-validated Workbench records. They do not establish "
    "substantive truth, canonical S2 publication, legal identity, or release authorization."
)

KIND_IDENTIFIER = "IDENTIFIER"
KIND_UNRESOLVED_LITERAL = "UNRESOLVED_LITERAL"
KIND_RESOLVED_ENTITY_REFERENCE = "RESOLVED_ENTITY_REFERENCE"
IDENTITY_KINDS = frozenset({KIND_IDENTIFIER, KIND_UNRESOLVED_LITERAL, KIND_RESOLVED_ENTITY_REFERENCE})


class IdentityError(ValueError):
    """Raised when an identity reference is malformed."""


class UnresolvedLiteralError(IdentityError):
    """Raised when an API that requires a resolved entity ID is given a literal or raw identifier."""


def parse_identity_ref(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IdentityError("Identity reference must be an object")
    kind = value.get("kind")
    if kind not in IDENTITY_KINDS:
        raise IdentityError(f"Unknown identity kind {kind!r}")
    extra = {key for key in value if key not in {"kind", "value", "entity_id", "scheme", "boundary"}}
    if extra:
        raise IdentityError(f"Identity reference contains unsupported fields: {sorted(extra)}")
    boundary = value.get("boundary")
    if not isinstance(boundary, str) or not boundary.strip():
        raise IdentityError("Identity reference requires a boundary string")

    if kind == KIND_UNRESOLVED_LITERAL:
        raw = value.get("value")
        if not isinstance(raw, str) or not raw.strip():
            raise IdentityError("UNRESOLVED_LITERAL requires a non-empty value string")
        if value.get("entity_id") is not None:
            raise IdentityError("UNRESOLVED_LITERAL must not carry entity_id")
        return {
            "kind": KIND_UNRESOLVED_LITERAL,
            "value": raw.strip(),
            "entity_id": None,
            "scheme": None,
            "boundary": boundary,
        }

    if kind == KIND_IDENTIFIER:
        raw = value.get("value")
        scheme = value.get("scheme")
        if not isinstance(raw, str) or not raw.strip():
            raise IdentityError("IDENTIFIER requires a non-empty value string")
        if not isinstance(scheme, str) or not scheme.strip():
            raise IdentityError("IDENTIFIER requires a scheme")
        if value.get("entity_id") is not None:
            raise IdentityError("IDENTIFIER is not a resolved entity reference and must not carry entity_id")
        return {
            "kind": KIND_IDENTIFIER,
            "value": raw.strip(),
            "entity_id": None,
            "scheme": scheme.strip(),
            "boundary": boundary,
        }

    entity_id = value.get("entity_id")
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise IdentityError("RESOLVED_ENTITY_REFERENCE requires entity_id")
    if value.get("value") not in {None, entity_id}:
        raise IdentityError("RESOLVED_ENTITY_REFERENCE value, if present, must equal entity_id")
    return {
        "kind": KIND_RESOLVED_ENTITY_REFERENCE,
        "value": None,
        "entity_id": entity_id.strip(),
        "scheme": value.get("scheme") if isinstance(value.get("scheme"), str) else None,
        "boundary": boundary,
    }


def dump_identity_ref(value: Any) -> dict[str, Any]:
    parsed = parse_identity_ref(value)
    dumped: dict[str, Any] = {"kind": parsed["kind"], "boundary": parsed["boundary"]}
    if parsed["kind"] == KIND_RESOLVED_ENTITY_REFERENCE:
        dumped["entity_id"] = parsed["entity_id"]
        if parsed["scheme"]:
            dumped["scheme"] = parsed["scheme"]
    elif parsed["kind"] == KIND_IDENTIFIER:
        dumped["value"] = parsed["value"]
        dumped["scheme"] = parsed["scheme"]
    else:
        dumped["value"] = parsed["value"]
    return dumped


def require_resolved_entity_id(value: Any, *, field: str) -> str:
    parsed = parse_identity_ref(value)
    if parsed["kind"] != KIND_RESOLVED_ENTITY_REFERENCE:
        raise UnresolvedLiteralError(
            f"{field} requires a RESOLVED_ENTITY_REFERENCE; "
            f"{parsed['kind']} cannot be consumed by APIs that require a resolved entity id"
        )
    entity_id = parsed["entity_id"]
    if not isinstance(entity_id, str):
        raise UnresolvedLiteralError(f"{field} resolved entity_id is missing")
    return entity_id
