from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .util import atomic_write_bytes, canonical_json_bytes, sha256_bytes, utc_now

GENESIS = "0" * 64
_LOCK_TIMEOUT_SECONDS = 10.0
_LOCK_POLL_SECONDS = 0.01


def _event_hash(event: dict[str, Any]) -> str:
    controlled = {key: value for key, value in event.items() if key != "event_hash"}
    return sha256_bytes(canonical_json_bytes(controlled))


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                row = json.loads(line)
                row["_line"] = line_number
                rows.append(row)
    return rows


def verify_chain(path: Path) -> dict[str, Any]:
    previous = GENESIS
    errors: list[str] = []
    events = load_events(path)
    for expected_seq, raw in enumerate(events, 1):
        event = {key: value for key, value in raw.items() if key != "_line"}
        if event.get("seq") != expected_seq:
            errors.append(f"line {raw['_line']}: expected seq {expected_seq}, found {event.get('seq')}")
        if event.get("previous_hash") != previous:
            errors.append(f"line {raw['_line']}: previous_hash mismatch")
        calculated = _event_hash(event)
        if event.get("event_hash") != calculated:
            errors.append(f"line {raw['_line']}: event_hash mismatch")
        previous = event.get("event_hash", "")
    return {
        "valid": not errors,
        "event_count": len(events),
        "head_hash": previous,
        "errors": errors,
        "boundary": "Hash-chain validity detects log alteration; it does not prove that recorded statements are true or complete.",
    }


@contextmanager
def _exclusive_lock(lock_path: Path, timeout: float = _LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Best-effort exclusive lock for the single-writer local profile (see ADR 0006)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()}\n".encode())
                yield
            finally:
                os.close(fd)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Could not acquire event-chain lock at {lock_path} within {timeout}s") from None
            time.sleep(_LOCK_POLL_SECONDS)


def append_event(path: Path, action: str, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    with _exclusive_lock(lock_path):
        report = verify_chain(path)
        if not report["valid"]:
            raise ValueError("Event chain is invalid; repair or preserve it before appending.")
        events = load_events(path)
        event = {
            "seq": len(events) + 1,
            "timestamp": utc_now(),
            "actor": actor,
            "action": action,
            "payload": payload,
            "previous_hash": report["head_hash"],
        }
        event["event_hash"] = _event_hash(event)
        existing = path.read_bytes() if path.exists() else b""
        new_line = json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        atomic_write_bytes(path, existing + new_line)
        return event
