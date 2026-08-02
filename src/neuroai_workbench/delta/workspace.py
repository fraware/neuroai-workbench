from __future__ import annotations

from pathlib import Path
from typing import Any

from ..events import append_event
from ..util import atomic_write_json, load_json, safe_join
from .compiler import compile_adjudicated_delta


def _monitoring_root(workspace: Path) -> Path:
    return safe_join(workspace, "observatory", "monitoring")


def compile_delta_from_workspace(
    workspace: Path,
    refresh_version: str,
    predecessor_path: Path,
    *,
    predecessor_release_id: str,
    operation_specs_path: Path | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    """Compile an adjudicated delta from a stored refresh package and predecessor release."""
    package_path = safe_join(_monitoring_root(workspace) / "runs" / refresh_version, "refresh-candidate.json")
    if not package_path.is_file():
        raise ValueError(f"No refresh package found for version {refresh_version!r}")
    refresh_package = load_json(package_path)
    if not isinstance(refresh_package, dict):
        raise ValueError("Refresh package must be a JSON object")
    predecessor = load_json(predecessor_path)
    if not isinstance(predecessor, dict):
        raise ValueError("Predecessor release must be a JSON object")

    operation_specs: dict[str, list[dict[str, Any]]] | None = None
    if operation_specs_path is not None:
        raw_specs = load_json(operation_specs_path)
        if not isinstance(raw_specs, dict):
            raise ValueError("operation_specs must be a JSON object keyed by candidate_id")
        operation_specs = {key: value for key, value in raw_specs.items() if isinstance(value, list)}

    delta = compile_adjudicated_delta(
        refresh_package,
        predecessor,
        predecessor_release_id=predecessor_release_id,
        operation_specs=operation_specs,
        actor=actor,
    )
    run_root = safe_join(_monitoring_root(workspace) / "runs" / refresh_version)
    delta_path = safe_join(run_root, "adjudicated-delta.json")
    if delta_path.exists():
        raise ValueError("Refusing to overwrite an existing adjudicated delta package")
    atomic_write_json(delta_path, delta)
    append_event(
        safe_join(workspace, "events.jsonl"),
        "ADJUDICATED_DELTA_COMPILED",
        actor,
        {
            "delta_id": delta["metadata"]["delta_id"],
            "refresh_version": refresh_version,
            "operation_count": len(delta["operations"]),
            "status": delta["metadata"]["status"],
        },
    )
    return {"delta": delta, "path": str(delta_path.relative_to(workspace))}
