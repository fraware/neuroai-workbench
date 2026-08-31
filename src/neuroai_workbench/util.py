from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fsync_directory(path: Path) -> None:
    """Persist directory metadata after create, replace, rename, or unlink on POSIX."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | int(getattr(os, "O_DIRECTORY", 0))
    fd = os.open(str(path), flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def ensure_identifier(value: str, field: str = "identifier") -> str:
    if not ID_RE.fullmatch(value):
        raise ValueError(
            f"Invalid {field} {value!r}; use 1-128 letters, digits, '.', '_' or '-' and start with an alphanumeric character."
        )
    return value


def _comparable_path(path: Path) -> Path:
    """Normalize Windows extended paths so containment checks stay stable.

    Concurrent ``Path.resolve()`` on Windows may return ``\\\\?\\C:\\...`` for one
    side and ``C:\\...`` for the other. Those forms are the same location but fail
    ``parents`` membership and break collector run-ledger writes under load.
    """
    text = os.fspath(path)
    if text.startswith("\\\\?\\"):
        text = text[4:]
    if os.name == "nt":
        text = os.path.normcase(text)
    return Path(text)


def safe_join(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    candidate_cmp = _comparable_path(candidate)
    root_cmp = _comparable_path(root_resolved)
    if candidate_cmp != root_cmp and root_cmp not in candidate_cmp.parents:
        raise ValueError("Path escapes controlled root")
    return candidate
