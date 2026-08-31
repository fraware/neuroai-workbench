"""Derived (non-authoritative) loaders for observatory-graph release artifacts.

PostgreSQL, DuckDB, search indexes, and graph databases are projections only.
Deletion of a derived store must not destroy canonical release state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from ..util import load_json, sha256_bytes

LoaderKind = Literal["postgresql", "duckdb", "search", "graph"]

LOADER_BOUNDARY = (
    "Derived loaders materialize release artifacts into operational stores for query and UI. "
    "They are never authority. Website or database deletion must not destroy canonical release state."
)

SUPPORTED_LOADERS = frozenset({"postgresql", "duckdb", "search", "graph"})


def load_release_descriptor(release_dir: Path) -> dict[str, Any]:
    descriptor = load_json(release_dir / "descriptor.json")
    if not isinstance(descriptor, dict):
        raise ValueError("Release descriptor must be a JSON object")
    return descriptor


def load_release_manifest(release_dir: Path) -> dict[str, Any]:
    manifest = load_json(release_dir / "manifest.json")
    if not isinstance(manifest, dict):
        raise ValueError("Release manifest must be a JSON object")
    return manifest


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL record in {path} must be an object")
        records.append(value)
    return records


def materialize_derived_projection(
    release_dir: Path,
    *,
    loader: LoaderKind,
    target: str,
) -> dict[str, Any]:
    """Build a derived projection plan/result. Never marks the projection as authoritative."""
    if loader not in SUPPORTED_LOADERS:
        raise ValueError(f"Unsupported derived loader {loader!r}")
    descriptor = load_release_descriptor(release_dir)
    manifest = load_release_manifest(release_dir)
    if descriptor.get("release_authorized") is True or manifest.get("release_authorized") is True:
        # Surface the flag but do not treat this loader as publication authority.
        authorization_note = "Release descriptor claims release_authorized; derived loader still non-authoritative."
    else:
        authorization_note = "Release is not authorized; derived loader is a non-authoritative projection only."

    records_dir = release_dir / "records"
    class_counts: dict[str, int] = {}
    payload_digest_parts: list[str] = []
    for path in sorted(records_dir.glob("*.jsonl")) if records_dir.is_dir() else []:
        records = read_jsonl_records(path)
        class_counts[path.stem] = len(records)
        payload_digest_parts.append(f"{path.name}:{len(records)}")

    projection = {
        "loader": loader,
        "target": target,
        "candidate_id": descriptor.get("candidate_id"),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "class_counts": class_counts,
        "projection_fingerprint": sha256_bytes("|".join(payload_digest_parts).encode("utf-8")),
        "authoritative": False,
        "canonical_authority": False,
        "release_authorized": False,
        "authorization_note": authorization_note,
        "destruction_note": (
            "Deleting this derived store must not destroy the release directory or SHA256SUMS. "
            "Canonical state remains the immutable release artifact."
        ),
        "boundary": LOADER_BOUNDARY,
    }
    return projection


def assert_non_authoritative(projection: dict[str, Any]) -> None:
    if projection.get("authoritative") is True or projection.get("canonical_authority") is True:
        raise ValueError("Derived loaders must never claim authoritative or canonical authority")
    if projection.get("release_authorized") is True:
        raise ValueError("Derived loaders must not set release_authorized=true")
