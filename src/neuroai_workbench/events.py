from __future__ import annotations

import ctypes
import json
import os
import socket
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from .util import atomic_write_bytes, canonical_json_bytes, fsync_directory, sha256_bytes, utc_now

GENESIS = "0" * 64
LOCK_PROFILE_LOCAL = "LOCAL_FILESYSTEM"
LOCK_PROFILE_SHARED = "SHARED_FILESYSTEM"

_LOCK_TIMEOUT_SECONDS = 10.0
_LOCK_POLL_SECONDS = 0.01
_LOCK_LEASE_SECONDS = 60.0
_TRAILER_VERSION = 1
_LOCK_VERSION = 1
# Windows defaults os.open to text mode and expands \n to \r\n; event-chain and lock
# bytes must stay exact so trailer size and hashes remain stable across platforms.
_O_BINARY = int(getattr(os, "O_BINARY", 0))


def _event_hash(event: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes({k: v for k, v in event.items() if k != "event_hash"}))


def _sidecar(path: Path, suffix: str) -> Path:
    return path.with_suffix(path.suffix + suffix)


def _event_line(event: dict[str, Any]) -> bytes:
    return json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"


def _decode_event(line: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: invalid UTF-8 JSON event") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}: event must be a JSON object")
    return value


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {line_number}: event must be a JSON object")
            row["_line"] = line_number
            rows.append(row)
    return rows


def _scan_chain(path: Path, *, limit: int | None = None) -> dict[str, Any]:
    previous = GENESIS
    errors: list[str] = []
    count = 0
    offset = 0
    last_offset: int | None = None
    last_length = 0
    if not path.exists():
        return {
            "valid": True,
            "event_count": 0,
            "head_hash": GENESIS,
            "errors": [],
            "log_size_bytes": 0,
            "last_event_offset": None,
            "last_event_length": 0,
        }
    with path.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            if limit is not None and offset + len(line) > limit:
                line = line[: limit - offset]
            current_offset = offset
            offset += len(line)
            if not line.strip():
                continue
            count += 1
            try:
                event = _decode_event(line, f"line {line_number}")
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if event.get("seq") != count:
                errors.append(f"line {line_number}: expected seq {count}, found {event.get('seq')}")
            if event.get("previous_hash") != previous:
                errors.append(f"line {line_number}: previous_hash mismatch")
            if event.get("event_hash") != _event_hash(event):
                errors.append(f"line {line_number}: event_hash mismatch")
            previous = str(event.get("event_hash") or "")
            last_offset = current_offset
            last_length = len(line)
            if limit is not None and offset >= limit:
                break
    return {
        "valid": not errors,
        "event_count": count,
        "head_hash": previous,
        "errors": errors,
        "log_size_bytes": min(path.stat().st_size, limit) if limit is not None else path.stat().st_size,
        "last_event_offset": last_offset,
        "last_event_length": last_length,
    }


def _trailer_hash(value: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes({k: v for k, v in value.items() if k != "trailer_hash"}))


def _make_trailer(
    path: Path,
    count: int,
    head_hash: str,
    size: int,
    offset: int | None,
    length: int,
) -> dict[str, Any]:
    stat = path.stat() if path.exists() else None
    trailer = {
        "version": _TRAILER_VERSION,
        "event_count": count,
        "head_hash": head_hash,
        "log_size_bytes": size,
        "last_event_offset": offset,
        "last_event_length": length,
        "log_mtime_ns": stat.st_mtime_ns if stat else None,
        "log_ctime_ns": stat.st_ctime_ns if stat else None,
        "log_inode": stat.st_ino if stat else None,
        "log_device": stat.st_dev if stat else None,
        "indexed_at": utc_now(),
        "verification_scope": "INDEXED_HEAD_ONLY",
    }
    trailer["trailer_hash"] = _trailer_hash(trailer)
    return trailer


def _write_trailer(path: Path, trailer: dict[str, Any]) -> None:
    atomic_write_bytes(
        _sidecar(path, ".trailer.json"),
        json.dumps(trailer, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n",
    )


def _load_trailer(path: Path) -> dict[str, Any]:
    trailer_path = _sidecar(path, ".trailer.json")
    value = json.loads(trailer_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("event-chain trailer must be a JSON object")
    if value.get("version") != _TRAILER_VERSION:
        raise ValueError("event-chain trailer version mismatch")
    if value.get("trailer_hash") != _trailer_hash(value):
        raise ValueError("event-chain trailer hash mismatch")
    return value


def _validate_trailer(path: Path, trailer: dict[str, Any], *, current_size: bool) -> None:
    actual = path.stat().st_size if path.exists() else 0
    indexed = int(trailer["log_size_bytes"])
    if actual < indexed or (current_size and actual != indexed):
        raise ValueError(f"event-chain trailer size mismatch: actual={actual}, indexed={indexed}")
    if actual == indexed and path.exists():
        stat = path.stat()
        expected = (
            trailer.get("log_mtime_ns"),
            trailer.get("log_ctime_ns"),
            trailer.get("log_inode"),
            trailer.get("log_device"),
        )
        observed = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, stat.st_dev)
        if expected != observed:
            raise ValueError("event-chain trailer file identity mismatch")
    count = int(trailer["event_count"])
    if count == 0:
        if indexed or trailer.get("head_hash") != GENESIS:
            raise ValueError("empty event-chain trailer is inconsistent")
        return
    offset = int(trailer["last_event_offset"])
    length = int(trailer["last_event_length"])
    if offset + length != indexed:
        raise ValueError("event-chain trailer extent mismatch")
    with path.open("rb") as handle:
        handle.seek(offset)
        line = handle.read(length)
    event = _decode_event(line, "indexed final event")
    if (
        not line.endswith(b"\n")
        or event.get("seq") != count
        or event.get("event_hash") != _event_hash(event)
        or event.get("event_hash") != trailer.get("head_hash")
    ):
        raise ValueError("event-chain trailer final event mismatch")


def verify_chain(path: Path, *, mode: str = "full") -> dict[str, Any]:
    if mode == "head":
        errors: list[str] = []
        try:
            trailer = _load_trailer(path)
            _validate_trailer(path, trailer, current_size=True)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            trailer = {"event_count": 0, "head_hash": GENESIS}
        return {
            "valid": not errors,
            "event_count": int(trailer["event_count"]),
            "head_hash": str(trailer["head_hash"]),
            "errors": errors,
            "verification_scope": "INDEXED_HEAD_ONLY",
            "boundary": "Head verification does not detect arbitrary historical alteration.",
        }
    if mode != "full":
        raise ValueError("mode must be 'full' or 'head'")
    report = _scan_chain(path)
    try:
        trailer = _load_trailer(path)
        _validate_trailer(path, trailer, current_size=True)
        report["trailer_valid"] = True
        report["trailer_errors"] = []
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        report["trailer_valid"] = False
        report["trailer_errors"] = [str(exc)]
    report["verification_scope"] = "FULL_CHAIN"
    report["boundary"] = (
        "Hash-chain validity detects log alteration; it does not prove recorded statements true or complete."
    )
    return report


def _rebuild_trailer_unlocked(path: Path) -> dict[str, Any]:
    report = verify_chain(path)
    if not report["valid"]:
        raise ValueError("Event chain is invalid; trailer rebuild refused.")
    trailer = _make_trailer(
        path,
        int(report["event_count"]),
        str(report["head_hash"]),
        int(report["log_size_bytes"]),
        report["last_event_offset"],
        int(report["last_event_length"]),
    )
    _write_trailer(path, trailer)
    return trailer


def rebuild_trailer(
    path: Path,
    *,
    lock_profile: str = LOCK_PROFILE_LOCAL,
) -> dict[str, Any]:
    with _exclusive_lock(_sidecar(path, ".lock"), profile=lock_profile):
        return _rebuild_trailer_unlocked(path)


def _process_start_token(pid: int) -> str | None:
    try:
        text = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        return None
    fields = text[text.rfind(")") + 1 :].strip().split()
    return fields[19] if len(fields) > 19 else None


def _windows_process_exists(pid: int) -> bool:
    """Return whether *pid* names a live Win32 process without sending console events.

    On Windows, ``os.kill(pid, 0)`` is ``CTRL_C_EVENT`` (value 0), so the Unix
    existence-check convention would interrupt the local process during lock
    polling. OpenProcess is coordination-only and is not identity proof.
    """
    if pid <= 0:
        return False
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return False
    # PROCESS_QUERY_LIMITED_INFORMATION — enough to prove the handle opened.
    handle = windll.kernel32.OpenProcess(0x1000, False, int(pid))
    if handle:
        windll.kernel32.CloseHandle(handle)
        return True
    # ERROR_ACCESS_DENIED (5): process exists but this caller cannot query it.
    get_last_error = getattr(ctypes, "GetLastError", None)
    if not callable(get_last_error):
        return False
    return int(get_last_error()) == 5


def _process_exists(pid: int) -> bool:
    """Return whether *pid* appears alive on this host (best-effort, local only)."""
    if os.name == "nt":
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - platform permission boundary
        return True
    except OSError:
        return False
    return True


def _pid_alive(pid: int, token: str | None) -> bool:
    if not _process_exists(pid):
        return False
    observed = _process_start_token(pid)
    return token is None or observed is None or observed == token


def _new_lock(profile: str) -> dict[str, Any]:
    if profile not in {LOCK_PROFILE_LOCAL, LOCK_PROFILE_SHARED}:
        raise ValueError(f"Unsupported event-chain lock profile: {profile}")
    now = time.time_ns()
    pid = os.getpid()
    return {
        "version": _LOCK_VERSION,
        "lock_id": f"ECL-{uuid4().hex}",
        "profile": profile,
        "host": socket.gethostname(),
        "pid": pid,
        "process_start_token": _process_start_token(pid),
        "acquired_at": utc_now(),
        "lease_expires_at_ns": now + int(_LOCK_LEASE_SECONDS * 1_000_000_000),
        "authority_profile": "FILESYSTEM_COORDINATION_ONLY",
    }


def _lock_bytes(record: dict[str, Any]) -> bytes:
    return json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"


def _create_lock(path: Path, record: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY | _O_BINARY, 0o600)
    except FileExistsError:
        return False
    except PermissionError:
        # Windows may deny create while another thread still holds the path open.
        return False
    try:
        data = _lock_bytes(record)
        if os.write(fd, data) != len(data):  # pragma: no cover - defensive partial regular-file write
            raise OSError("partial event-chain lock write")
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_directory(path.parent)
    return True


def _read_lock(path: Path) -> tuple[dict[str, Any] | None, bytes | None]:
    deadline = time.monotonic() + min(1.0, _LOCK_TIMEOUT_SECONDS)
    while True:
        try:
            raw = path.read_bytes()
            break
        except FileNotFoundError:
            return None, None
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_LOCK_POLL_SECONDS)
            continue
        except OSError as exc:  # pragma: no cover - platform-specific sharing codes
            winerror = getattr(exc, "winerror", None)
            if winerror != 32 or time.monotonic() >= deadline:
                raise
            time.sleep(_LOCK_POLL_SECONDS)
            continue
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, raw
    return (value if isinstance(value, dict) else None), raw


def _recovery_reason(path: Path, record: dict[str, Any] | None) -> str | None:
    if record is None:
        try:
            expired = time.time() - path.stat().st_mtime >= _LOCK_LEASE_SECONDS
        except FileNotFoundError:
            return "DISAPPEARED"
        return "MALFORMED_EXPIRED" if expired else None

    same_host = record.get("host") == socket.gethostname()
    pid = record.get("pid")
    if same_host and isinstance(pid, int):
        if not _pid_alive(pid, record.get("process_start_token")):
            return "DEAD_LOCAL_OWNER"
        return None

    if record.get("profile") != LOCK_PROFILE_SHARED:
        return None
    expiry = record.get("lease_expires_at_ns")
    return "LEASE_EXPIRED" if isinstance(expiry, int) and expiry <= time.time_ns() else None


def _recover_lock(path: Path, raw: bytes | None, reason: str) -> bool:
    try:
        current = path.read_bytes()
    except FileNotFoundError:
        return False
    if raw is not None and current != raw:
        return False
    archive = path.with_name(path.name + ".recovered")
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / f"{time.time_ns()}-{sha256_bytes(current)[:16]}.json"
    try:
        os.replace(path, target)
    except FileNotFoundError:
        return False
    fsync_directory(path.parent)
    fsync_directory(archive)
    atomic_write_bytes(
        target.with_suffix(".metadata.json"),
        json.dumps(
            {"recovered_at": utc_now(), "reason": reason, "lock_sha256": sha256_bytes(current)},
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        + b"\n",
    )
    return True


def _assert_owner(path: Path, owner: dict[str, Any]) -> None:
    current, _ = _read_lock(path)
    if current is None or current.get("lock_id") != owner["lock_id"]:
        raise RuntimeError("Event-chain lock ownership was lost during append")


@contextmanager
def _exclusive_lock(
    lock_path: Path,
    timeout: float = _LOCK_TIMEOUT_SECONDS,
    *,
    profile: str = LOCK_PROFILE_LOCAL,
) -> Iterator[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    owner = _new_lock(profile)
    while not _create_lock(lock_path, owner):
        record, raw = _read_lock(lock_path)
        reason = _recovery_reason(lock_path, record)
        if reason == "DISAPPEARED":
            continue
        if reason and _recover_lock(lock_path, raw, reason):
            continue
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Could not acquire event-chain lock at {lock_path} within {timeout}s") from None
        time.sleep(_LOCK_POLL_SECONDS)
    try:
        yield owner
    finally:
        current, _ = _read_lock(lock_path)
        if current is not None and current.get("lock_id") == owner["lock_id"]:
            _release_lock_file(lock_path)


def _release_lock_file(lock_path: Path) -> None:
    """Unlink an owned lock file, retrying Windows sharing violations briefly.

    Contending readers may briefly hold the lock path open during ``read_bytes``.
    Failing the owner unlink would leave a live-PID lock that never recovers.
    """
    deadline = time.monotonic() + min(1.0, _LOCK_TIMEOUT_SECONDS)
    while True:
        try:
            lock_path.unlink(missing_ok=True)
            fsync_directory(lock_path.parent)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_LOCK_POLL_SECONDS)
        except OSError as exc:  # pragma: no cover - platform-specific sharing codes
            winerror = getattr(exc, "winerror", None)
            if winerror != 32 or time.monotonic() >= deadline:
                raise
            time.sleep(_LOCK_POLL_SECONDS)


def _append_fsync(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    fd = os.open(str(path), os.O_CREAT | os.O_APPEND | os.O_WRONLY | _O_BINARY, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:  # pragma: no cover - defensive regular-file write failure
                raise OSError("event-chain append made no progress")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    if created:
        fsync_directory(path.parent)


def _record_recovery(path: Path, reason: str, original: int, recovered: int, discarded: bytes) -> None:
    record = {
        "recovery_id": f"ECR-{uuid4().hex}",
        "recorded_at": utc_now(),
        "reason": reason,
        "original_size_bytes": original,
        "recovered_size_bytes": recovered,
        "discarded_size_bytes": len(discarded),
        "discarded_sha256": sha256_bytes(discarded),
        "event_bytes_copied": False,
    }
    _append_fsync(_sidecar(path, ".recoveries.jsonl"), _event_line(record))


def _recover_suffix(path: Path, trailer: dict[str, Any]) -> dict[str, Any]:
    indexed = int(trailer["log_size_bytes"])
    prefix = _scan_chain(path, limit=indexed)
    if (
        not prefix["valid"]
        or prefix["event_count"] != trailer["event_count"]
        or prefix["head_hash"] != trailer["head_hash"]
        or prefix["log_size_bytes"] != indexed
    ):
        raise ValueError("Indexed event-chain prefix is invalid; tail recovery refused")
    original = path.stat().st_size
    with path.open("rb") as handle:
        handle.seek(indexed)
        suffix = handle.read()
    count = int(trailer["event_count"])
    previous = str(trailer["head_hash"])
    valid = 0
    offset = trailer.get("last_event_offset")
    length = int(trailer["last_event_length"])
    reason: str | None = None
    for number, line in enumerate(suffix.splitlines(keepends=True), 1):
        try:
            event = _decode_event(line, f"unindexed line {number}")
        except ValueError:
            reason = "INVALID_UNINDEXED_EVENT"
            break
        if not line.endswith(b"\n"):
            reason = "INCOMPLETE_UNINDEXED_TAIL"
            break
        if (
            event.get("seq") != count + 1
            or event.get("previous_hash") != previous
            or event.get("event_hash") != _event_hash(event)
        ):
            reason = "UNLINKED_UNINDEXED_EVENT"
            break
        offset = indexed + valid
        length = len(line)
        valid += len(line)
        count += 1
        previous = str(event["event_hash"])
    recovered = indexed + valid
    if reason:
        discarded = suffix[valid:]
        with path.open("r+b") as handle:
            handle.truncate(recovered)
            handle.flush()
            os.fsync(handle.fileno())
        _record_recovery(path, reason, original, recovered, discarded)
    trailer = _make_trailer(path, count, previous, recovered if reason else original, offset, length)
    _write_trailer(path, trailer)
    return trailer


def _append_state(path: Path) -> dict[str, Any]:
    try:
        trailer = _load_trailer(path)
        _validate_trailer(path, trailer, current_size=False)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return _rebuild_trailer_unlocked(path)
    actual = path.stat().st_size if path.exists() else 0
    return trailer if actual == int(trailer["log_size_bytes"]) else _recover_suffix(path, trailer)


def append_event(
    path: Path,
    action: str,
    actor: str,
    payload: dict[str, Any],
    *,
    lock_profile: str = LOCK_PROFILE_LOCAL,
) -> dict[str, Any]:
    lock_path = _sidecar(path, ".lock")
    with _exclusive_lock(lock_path, profile=lock_profile) as owner:
        state = _append_state(path)
        _assert_owner(lock_path, owner)
        event = {
            "seq": int(state["event_count"]) + 1,
            "timestamp": utc_now(),
            "actor": actor,
            "action": action,
            "payload": payload,
            "previous_hash": state["head_hash"],
        }
        event["event_hash"] = _event_hash(event)
        line = _event_line(event)
        offset = int(state["log_size_bytes"])
        _append_fsync(path, line)
        _assert_owner(lock_path, owner)
        _write_trailer(
            path,
            _make_trailer(path, event["seq"], event["event_hash"], offset + len(line), offset, len(line)),
        )
        _assert_owner(lock_path, owner)
        return event
