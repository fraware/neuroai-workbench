from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .events import LOCK_PROFILE_LOCAL, _exclusive_lock
from .util import ensure_identifier


def case_mutation_lock_path(case_path: Path) -> Path:
    """Return a stable lock path outside the mutable case directory."""
    case_id = ensure_identifier(case_path.name, "case ID")
    return case_path.parent / ".case-locks" / f"{case_id}.lock"


@contextmanager
def case_mutation_lock(case_path: Path) -> Iterator[dict[str, Any]]:
    """Serialize cooperative case writes, snapshots, registration, and deletion.

    The external lock remains present if the case directory is deleted, so an
    active owner cannot lose exclusion through deletion of the protected tree.
    This is a filesystem coordination boundary, not identity or custody proof.
    """
    with _exclusive_lock(case_mutation_lock_path(case_path), profile=LOCK_PROFILE_LOCAL) as owner:
        yield owner


__all__ = ["case_mutation_lock", "case_mutation_lock_path"]
