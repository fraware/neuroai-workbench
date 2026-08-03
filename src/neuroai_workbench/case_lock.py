from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .events import LOCK_PROFILE_LOCAL, _exclusive_lock
from .util import ensure_identifier


def case_mutation_lock_path(case_path: Path) -> Path:
    case_id = ensure_identifier(case_path.name, "case ID")
    return case_path.parent / ".case-locks" / f"{case_id}.lock"


@contextmanager
def case_mutation_lock(case_path: Path) -> Iterator[dict[str, Any]]:
    """Serialize cooperative writes that change one case or its event history."""
    with _exclusive_lock(case_mutation_lock_path(case_path), profile=LOCK_PROFILE_LOCAL) as owner:
        yield owner


__all__ = ["case_mutation_lock", "case_mutation_lock_path"]
