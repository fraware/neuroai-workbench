"""Deterministic assessment field-path helpers for controlled edits.

Paths use a workbench convention, not RFC 6901 JSON Pointer indexing:
collection members are addressed by their stable identifier field
(for example ``/requirement_findings/NK-01-R01/finding``).
"""

from __future__ import annotations

import copy
import re
from typing import Any

COLLECTION_ID_FIELDS: dict[str, str] = {
    "requirement_findings": "requirement_id",
    "claim_register": "claim_id",
    "decision_register": "decision_id",
    "gap_register": "gap_id",
    "evidence_register": "evidence_id",
}

_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def normalize_target_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("target_path must be a non-empty string")
    text = path.strip()
    if not text.startswith("/"):
        raise ValueError(f"target_path must start with '/': {path!r}")
    if ".." in text.split("/"):
        raise ValueError(f"target_path must not contain '..': {path!r}")
    segments = [part for part in text.split("/") if part != ""]
    if not segments:
        raise ValueError("target_path must address at least one field")
    for segment in segments:
        if not _SEGMENT_RE.fullmatch(segment):
            raise ValueError(f"Invalid target_path segment {segment!r} in {path!r}")
    return "/" + "/".join(segments)


def _locate_collection_item(collection: list[Any], id_field: str, item_id: str, path: str) -> dict[str, Any]:
    matches = [item for item in collection if isinstance(item, dict) and str(item.get(id_field)) == item_id]
    if not matches:
        raise ValueError(f"Unknown collection member {item_id!r} for path {path}")
    if len(matches) > 1:
        raise ValueError(f"Ambiguous collection member {item_id!r} for path {path}")
    return matches[0]


def get_at_path(assessment: dict[str, Any], path: str) -> Any:
    normalized = normalize_target_path(path)
    segments = normalized.strip("/").split("/")
    root_key = segments[0]
    if root_key in COLLECTION_ID_FIELDS:
        if len(segments) < 3:
            raise ValueError(f"Collection path must include member id and field: {path}")
        collection = assessment.get(root_key)
        if not isinstance(collection, list):
            raise ValueError(f"Assessment is missing collection {root_key!r}")
        item = _locate_collection_item(collection, COLLECTION_ID_FIELDS[root_key], segments[1], normalized)
        cursor: Any = item
        for segment in segments[2:]:
            if not isinstance(cursor, dict) or segment not in cursor:
                raise ValueError(f"Unknown field path {normalized}")
            cursor = cursor[segment]
        return cursor
    cursor = assessment
    for segment in segments:
        if not isinstance(cursor, dict) or segment not in cursor:
            raise ValueError(f"Unknown field path {normalized}")
        cursor = cursor[segment]
    return cursor


def apply_field_patches(assessment: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a deep-copied assessment with explicit field patches applied."""
    if not patches:
        raise ValueError("At least one explicit field patch is required")
    updated = copy.deepcopy(assessment)
    seen: set[str] = set()
    for index, patch in enumerate(patches):
        prefix = f"field_patches[{index}]"
        if not isinstance(patch, dict):
            raise ValueError(f"{prefix} must be an object")
        if "target_path" not in patch or "value" not in patch:
            raise ValueError(f"{prefix} requires target_path and value")
        path = normalize_target_path(str(patch["target_path"]))
        if path in seen:
            raise ValueError(f"Duplicate field patch for {path}")
        seen.add(path)
        value = patch["value"]
        segments = path.strip("/").split("/")
        root_key = segments[0]
        if root_key in COLLECTION_ID_FIELDS:
            if len(segments) < 3:
                raise ValueError(f"{prefix}: collection path must include member id and field")
            collection = updated.get(root_key)
            if not isinstance(collection, list):
                raise ValueError(f"{prefix}: assessment is missing collection {root_key!r}")
            item = _locate_collection_item(collection, COLLECTION_ID_FIELDS[root_key], segments[1], path)
            parent: Any = item
            for segment in segments[2:-1]:
                if not isinstance(parent, dict) or segment not in parent or not isinstance(parent[segment], dict):
                    raise ValueError(f"{prefix}: unknown parent path {path}")
                parent = parent[segment]
            leaf = segments[-1]
            if not isinstance(parent, dict) or leaf not in parent:
                raise ValueError(f"{prefix}: unknown field path {path}")
            if leaf == COLLECTION_ID_FIELDS[root_key]:
                raise ValueError(f"{prefix}: refusing to rewrite collection identity field {leaf}")
            parent[leaf] = value
            continue
        parent = updated
        for segment in segments[:-1]:
            if not isinstance(parent, dict) or segment not in parent or not isinstance(parent[segment], dict):
                raise ValueError(f"{prefix}: unknown parent path {path}")
            parent = parent[segment]
        leaf = segments[-1]
        if not isinstance(parent, dict) or leaf not in parent:
            raise ValueError(f"{prefix}: unknown field path {path}")
        parent[leaf] = value
    return updated


def path_within_review_target(path: str, target_type: str, target_id: str) -> bool:
    normalized = normalize_target_path(path)
    if target_type == "FINDING":
        return normalized.startswith(f"/requirement_findings/{target_id}/")
    if target_type == "CLAIM":
        return normalized.startswith(f"/claim_register/{target_id}/")
    if target_type == "DECISION":
        return normalized.startswith(f"/decision_register/{target_id}/")
    if target_type == "GAP":
        return normalized.startswith(f"/gap_register/{target_id}/")
    if target_type == "ASSESSMENT":
        return normalized.startswith("/assessment_metadata/")
    return False
