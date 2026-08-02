from __future__ import annotations

import os
from pathlib import Path

from .constants import OPS_WORKSPACE_ENV


def ops_workspace_root(env: dict[str, str] | None = None) -> Path | None:
    """Return NEUROAI_OPS_WORKSPACE when set to an existing directory."""
    source = env if env is not None else os.environ
    raw = source.get(OPS_WORKSPACE_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_dir():
        return None
    return path.resolve()


def resolve_ops_relpath(ops_relpath: str, *, env: dict[str, str] | None = None) -> Path | None:
    """Resolve a relative ops path; reject absolute or escaping paths."""
    if not ops_relpath or ops_relpath.startswith("/") or "\\" in ops_relpath or ":" in ops_relpath:
        return None
    if ".." in Path(ops_relpath).parts:
        return None
    root = ops_workspace_root(env)
    if root is None:
        return None
    candidate = (root / ops_relpath).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate
