from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from neuroai_workbench import events


def _event(previous: str, seq: int, *, action: str = "TEST") -> dict:
    value = {
        "seq": seq,
        "timestamp": "2026-08-03T00:00:00Z",
        "actor": "tester",
        "action": action,
        "payload": {"seq": seq},
        "previous_hash": previous,
    }
    value["event_hash"] = events._event_hash(value)
    return value


def _write_lock(path: Path, **overrides) -> dict:
    record = events._new_lock(events.LOCK_PROFILE_LOCAL)
    record.update(overrides)
    path.write_bytes(events._lock_bytes(record))
    return record


def test_valid_chain_load_and_index(tmp_path):
    path = tmp_path / "events.jsonl"
    first = events.append_event(path, "ONE", "tester", {"value": 1})
    second = events.append_event(path, "TWO", "tester", {"value": 2})
    assert (first["seq"], second["seq"]) == (1, 2)
    assert [row["action"] for row in events.load_events(path)] == ["ONE", "TWO"]
    full = events.verify_chain(path)
    head = events.verify_chain(path, mode="head")
    assert full["valid"] and full["trailer_valid"]
    assert head["valid"] and head["verification_scope"] == "INDEXED_HEAD_ONLY"
    assert full["event_count"] == head["event_count"] == 2


def test_append_preserves_lf_newlines_on_windows(tmp_path):
    """Event bytes must not gain CRLF translation or trailer size drifts by one byte per event."""
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {"value": 1})
    events.append_event(path, "TWO", "tester", {"value": 2})
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    report = events.verify_chain(path)
    assert report["valid"] and report["trailer_valid"]
    assert report["log_size_bytes"] == len(raw)
    trailer = events._load_trailer(path)
    assert trailer["log_size_bytes"] == len(raw)


def test_append_fast_path_avoids_full_scan(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    monkeypatch.setattr(events, "_scan_chain", lambda *args, **kwargs: pytest.fail("full scan used"))
    assert events.append_event(path, "TWO", "tester", {})["seq"] == 2


def test_full_chain_detects_tamper_and_head_scope_is_explicit(tmp_path):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {"value": "A"})
    events.append_event(path, "TWO", "tester", {})
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["payload"]["value"] = "B"
    lines[0] = json.dumps(first, ensure_ascii=False, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not events.verify_chain(path)["valid"]
    head = events.verify_chain(path, mode="head")
    assert head["verification_scope"] == "INDEXED_HEAD_ONLY"


def test_chain_reports_sequence_link_hash_and_decode_errors(tmp_path):
    path = tmp_path / "events.jsonl"
    one = _event(events.GENESIS, 2)
    two = _event("wrong", 2)
    two["event_hash"] = "0" * 64
    path.write_bytes(events._event_line(one) + events._event_line(two) + b"\xff\n")
    report = events.verify_chain(path)
    assert not report["valid"]
    text = "\n".join(report["errors"])
    assert "expected seq" in text
    assert "previous_hash mismatch" in text
    assert "event_hash mismatch" in text
    assert "invalid UTF-8 JSON event" in text


def test_load_events_rejects_non_object(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        events.load_events(path)


def test_decode_event_rejects_invalid_json_and_non_object():
    with pytest.raises(ValueError, match="invalid UTF-8 JSON"):
        events._decode_event(b"{", "bad")
    with pytest.raises(ValueError, match="JSON object"):
        events._decode_event(b"[]\n", "bad")


def test_verify_modes_and_missing_trailer(tmp_path):
    path = tmp_path / "events.jsonl"
    assert events.verify_chain(path)["valid"]
    assert not events.verify_chain(path, mode="head")["valid"]
    with pytest.raises(ValueError, match="mode"):
        events.verify_chain(path, mode="other")


def test_rebuild_empty_and_missing_trailer(tmp_path):
    path = tmp_path / "events.jsonl"
    trailer = events.rebuild_trailer(path)
    assert trailer["event_count"] == 0
    assert events.verify_chain(path, mode="head")["valid"]
    events.append_event(path, "ONE", "tester", {})
    events._sidecar(path, ".trailer.json").unlink()
    rebuilt = events.rebuild_trailer(path)
    assert rebuilt["event_count"] == 1


def test_rebuild_refuses_invalid_chain(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid"):
        events.rebuild_trailer(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(version=99), "version mismatch"),
        (lambda value: value.update(trailer_hash="bad"), "hash mismatch"),
    ],
)
def test_trailer_validation_failures(tmp_path, mutation, message):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    trailer_path = events._sidecar(path, ".trailer.json")
    value = json.loads(trailer_path.read_text(encoding="utf-8"))
    mutation(value)
    trailer_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        events._load_trailer(path)
    report = events.verify_chain(path)
    assert report["valid"] and not report["trailer_valid"]


def test_trailer_non_object_and_unreadable(tmp_path):
    path = tmp_path / "events.jsonl"
    trailer = events._sidecar(path, ".trailer.json")
    trailer.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        events._load_trailer(path)
    trailer.write_text("{", encoding="utf-8")
    assert not events.verify_chain(path, mode="head")["valid"]


def test_trailer_extent_empty_and_final_event_failures(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b"")
    empty = events._make_trailer(path, 0, "bad", 1, None, 0)
    with pytest.raises(ValueError, match="size mismatch|inconsistent"):
        events._validate_trailer(path, empty, current_size=True)

    events.append_event(path, "ONE", "tester", {})
    trailer = events._load_trailer(path)
    trailer["last_event_length"] += 1
    with pytest.raises(ValueError, match="extent mismatch"):
        events._validate_trailer(path, trailer, current_size=True)

    trailer = events._load_trailer(path)
    trailer["head_hash"] = "f" * 64
    with pytest.raises(ValueError, match="final event mismatch"):
        events._validate_trailer(path, trailer, current_size=True)


def test_tampered_trailer_is_rebuilt_before_append(tmp_path):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    trailer_path = events._sidecar(path, ".trailer.json")
    value = json.loads(trailer_path.read_text(encoding="utf-8"))
    value["trailer_hash"] = "bad"
    trailer_path.write_text(json.dumps(value), encoding="utf-8")
    assert events.append_event(path, "TWO", "tester", {})["seq"] == 2
    assert events.verify_chain(path)["trailer_valid"]


def test_file_identity_change_forces_full_rebuild(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    calls = 0
    original = events._scan_chain

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(events, "_scan_chain", counted)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert events.append_event(path, "TWO", "tester", {})["seq"] == 2
    assert calls >= 1


def test_complete_unindexed_event_is_recovered(tmp_path):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    trailer = events._load_trailer(path)
    unindexed = _event(trailer["head_hash"], 2, action="UNINDEXED")
    events._append_fsync(path, events._event_line(unindexed))
    assert events.append_event(path, "THREE", "tester", {})["seq"] == 3
    assert events.verify_chain(path)["event_count"] == 3


@pytest.mark.parametrize(
    ("suffix", "reason"),
    [
        (b'{"partial"', "INVALID_UNINDEXED_EVENT"),
        (b"[]\n", "INVALID_UNINDEXED_EVENT"),
    ],
)
def test_invalid_unindexed_tail_is_truncated_and_recorded(tmp_path, suffix, reason):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    events._append_fsync(path, suffix)
    assert events.append_event(path, "TWO", "tester", {})["seq"] == 2
    recovery = events.load_events(events._sidecar(path, ".recoveries.jsonl"))[0]
    assert recovery["reason"] == reason
    assert recovery["event_bytes_copied"] is False
    assert events.verify_chain(path)["valid"]


def test_incomplete_valid_json_tail_has_specific_reason(tmp_path):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    events._append_fsync(path, b"{}")
    events.append_event(path, "TWO", "tester", {})
    recovery = events.load_events(events._sidecar(path, ".recoveries.jsonl"))[0]
    assert recovery["reason"] == "INCOMPLETE_UNINDEXED_TAIL"


def test_unlinked_unindexed_event_is_truncated(tmp_path):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {})
    bad = _event("bad", 2)
    events._append_fsync(path, events._event_line(bad))
    events.append_event(path, "TWO", "tester", {})
    recovery = events.load_events(events._sidecar(path, ".recoveries.jsonl"))[0]
    assert recovery["reason"] == "UNLINKED_UNINDEXED_EVENT"


def test_invalid_indexed_prefix_refuses_tail_recovery(tmp_path):
    path = tmp_path / "events.jsonl"
    events.append_event(path, "ONE", "tester", {"x": "A"})
    raw = path.read_bytes().replace(b'"A"', b'"B"')
    path.write_bytes(raw + b"{}")
    with pytest.raises(ValueError, match="invalid|refused"):
        events.append_event(path, "TWO", "tester", {})


def test_active_malformed_lock_times_out_then_releases(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "_LOCK_TIMEOUT_SECONDS", 0.03)
    monkeypatch.setattr(events, "_LOCK_POLL_SECONDS", 0.001)
    path = tmp_path / "events.jsonl"
    lock = events._sidecar(path, ".lock")
    lock.write_text("held", encoding="utf-8")
    with pytest.raises(TimeoutError, match="event-chain lock"):
        events.append_event(path, "BLOCKED", "tester", {})
    lock.unlink()
    with events._exclusive_lock(tmp_path / "other.lock"):
        assert (tmp_path / "other.lock").is_file()
    assert not (tmp_path / "other.lock").exists()


def test_dead_local_owner_is_recovered(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    lock = events._sidecar(path, ".lock")
    _write_lock(lock, pid=999999999, process_start_token="old")
    monkeypatch.setattr(events, "_pid_alive", lambda pid, token: False)
    assert events.append_event(path, "ONE", "tester", {})["seq"] == 1
    archive = lock.with_name(lock.name + ".recovered")
    assert list(archive.glob("*.json"))
    metadata = list(archive.glob("*.metadata.json"))[0]
    assert "DEAD_LOCAL_OWNER" in metadata.read_text(encoding="utf-8")


def test_expired_shared_and_malformed_locks_are_recovered(tmp_path):
    path = tmp_path / "events.jsonl"
    lock = events._sidecar(path, ".lock")
    _write_lock(
        lock,
        profile=events.LOCK_PROFILE_SHARED,
        host="other-host",
        lease_expires_at_ns=time.time_ns() - 1,
    )
    assert events.append_event(path, "ONE", "tester", {})["seq"] == 1

    second = tmp_path / "second.jsonl"
    malformed = events._sidecar(second, ".lock")
    malformed.write_text("bad", encoding="utf-8")
    old = time.time() - events._LOCK_LEASE_SECONDS - 1
    os.utime(malformed, (old, old))
    assert events.append_event(second, "ONE", "tester", {})["seq"] == 1


def test_expired_live_local_owner_is_not_recovered(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "_LOCK_TIMEOUT_SECONDS", 0.03)
    monkeypatch.setattr(events, "_LOCK_POLL_SECONDS", 0.001)
    path = tmp_path / "events.jsonl"
    lock = events._sidecar(path, ".lock")
    _write_lock(lock, lease_expires_at_ns=time.time_ns() - 1)
    monkeypatch.setattr(events, "_pid_alive", lambda pid, token: True)
    with pytest.raises(TimeoutError, match="event-chain lock"):
        events.append_event(path, "BLOCKED", "tester", {})
    assert lock.exists()


def test_expired_foreign_local_owner_is_not_recovered(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "_LOCK_TIMEOUT_SECONDS", 0.03)
    monkeypatch.setattr(events, "_LOCK_POLL_SECONDS", 0.001)
    path = tmp_path / "events.jsonl"
    lock = events._sidecar(path, ".lock")
    _write_lock(lock, host="other-host", lease_expires_at_ns=time.time_ns() - 1)
    with pytest.raises(TimeoutError, match="event-chain lock"):
        events.append_event(path, "BLOCKED", "tester", {})
    assert lock.exists()


def test_lock_release_never_deletes_replacement_owner(tmp_path):
    lock = tmp_path / "events.lock"
    replacement = events._new_lock(events.LOCK_PROFILE_LOCAL)
    with events._exclusive_lock(lock):
        lock.write_bytes(events._lock_bytes(replacement))
    assert lock.exists()
    assert json.loads(lock.read_text(encoding="utf-8"))["lock_id"] == replacement["lock_id"]


def test_lock_profile_and_owner_validation(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        events._new_lock("bad")
    with pytest.raises(RuntimeError, match="ownership was lost"):
        events._assert_owner(tmp_path / "missing.lock", {"lock_id": "x"})


def test_create_and_read_lock_edges(tmp_path):
    path = tmp_path / "lock"
    record = events._new_lock(events.LOCK_PROFILE_SHARED)
    assert events._create_lock(path, record)
    assert not events._create_lock(path, record)
    loaded, raw = events._read_lock(path)
    assert loaded is not None and loaded["lock_id"] == record["lock_id"] and raw
    path.write_text("[]", encoding="utf-8")
    assert events._read_lock(path)[0] is None
    path.unlink()
    assert events._read_lock(path) == (None, None)


def test_recovery_races_fail_closed(tmp_path):
    path = tmp_path / "lock"
    path.write_text("one", encoding="utf-8")
    assert not events._recover_lock(path, b"two", "TEST")
    path.unlink()
    assert not events._recover_lock(path, None, "TEST")


def test_process_token_and_pid_helpers(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: "1 (x) " + " ".join(str(i) for i in range(30)))
    assert events._process_start_token(1) == "19"
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: "short")
    assert events._process_start_token(1) is None

    def raise_os(self, **kwargs):
        raise OSError("no proc")

    monkeypatch.setattr(Path, "read_text", raise_os)
    assert events._process_start_token(1) is None

    monkeypatch.setattr(events, "_process_exists", lambda pid: False)
    assert not events._pid_alive(1, None)
    monkeypatch.setattr(events, "_process_exists", lambda pid: True)
    monkeypatch.setattr(events, "_process_start_token", lambda pid: "new")
    assert not events._pid_alive(1, "old")
    assert events._pid_alive(1, None)


def test_concurrent_writers_preserve_chain(tmp_path):
    path = tmp_path / "events.jsonl"

    def append(number: int) -> int:
        return events.append_event(path, "CONCURRENT", f"actor-{number}", {"number": number})["seq"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        sequences = list(pool.map(append, range(40)))
    assert sorted(sequences) == list(range(1, 41))
    report = events.verify_chain(path)
    assert report["valid"] and report["event_count"] == 40


def test_scan_limit_and_blank_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    one = _event(events.GENESIS, 1)
    data = b"\n" + events._event_line(one)
    path.write_bytes(data)
    report = events._scan_chain(path, limit=len(data))
    assert report["valid"] and report["event_count"] == 1


def test_recovery_reason_disappeared_and_live_owner(tmp_path, monkeypatch):
    path = tmp_path / "lock"
    assert events._recovery_reason(path, None) == "DISAPPEARED"
    record = _write_lock(path)
    monkeypatch.setattr(events, "_pid_alive", lambda pid, token: True)
    assert events._recovery_reason(path, record) is None


def test_pid_alive_self_does_not_send_console_interrupt():
    """Lock polling must not treat Unix kill(pid, 0) as Win32 CTRL_C_EVENT."""
    import signal
    import threading

    hits: list[int] = []

    def _handler(signum: int, frame) -> None:
        hits.append(signum)

    previous = signal.signal(signal.SIGINT, _handler)
    try:
        assert events._process_exists(os.getpid())
        assert events._pid_alive(os.getpid(), None)
        barrier = threading.Barrier(2)

        def _worker() -> None:
            barrier.wait(timeout=2)
            for _ in range(50):
                assert events._pid_alive(os.getpid(), None)

        worker = threading.Thread(target=_worker)
        worker.start()
        barrier.wait(timeout=2)
        for _ in range(50):
            assert events._pid_alive(os.getpid(), None)
        worker.join(timeout=5)
        assert not worker.is_alive()
    finally:
        signal.signal(signal.SIGINT, previous)
    assert hits == []


def test_exclusive_lock_contention_survives_repeated_threads(tmp_path):
    """Contended local locks must not interrupt the process across iterations."""
    import time
    from threading import Event, Thread

    for index in range(5):
        lock_path = tmp_path / f"case-{index}" / ".lock"
        attempted = Event()
        finished = Event()

        def worker(path: Path = lock_path, done: Event = finished, saw: Event = attempted) -> None:
            saw.set()
            with events._exclusive_lock(path, profile=events.LOCK_PROFILE_LOCAL):
                time.sleep(0.01)
            done.set()

        with events._exclusive_lock(lock_path, profile=events.LOCK_PROFILE_LOCAL):
            thread = Thread(target=worker)
            thread.start()
            assert attempted.wait(timeout=2)
            time.sleep(0.05)
            assert not finished.is_set()
        assert finished.wait(timeout=5)
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert not lock_path.exists()


def test_safe_join_tolerates_windows_extended_path_forms(tmp_path: Path) -> None:
    from neuroai_workbench.util import _comparable_path, safe_join

    root = tmp_path / "root"
    root.mkdir()
    target = safe_join(root, "child", "file.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")
    extended = Path("\\\\?\\" + str(target.resolve()))
    assert _comparable_path(extended) == _comparable_path(target.resolve())
    assert safe_join(root, "child", "file.json") == target.resolve()


def test_safe_join_concurrent_nested_writes(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from neuroai_workbench.util import safe_join

    run_root = tmp_path / "quarantine" / "run-ledgers" / "CRUN-x"
    run_root.mkdir(parents=True)

    def write_one(index: int) -> Path:
        path = safe_join(run_root, "targets", f"RTGT-{index:04d}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(write_one, range(80)))
    assert len(paths) == 80
    assert all(path.is_file() for path in paths)


def test_windows_and_posix_process_exists_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert events._windows_process_exists(0) is False
    assert events._windows_process_exists(-1) is False

    class _Kernel:
        def __init__(self) -> None:
            self.closed = 0

        def OpenProcess(self, access: int, inherit: bool, pid: int) -> int:
            return 0

        def CloseHandle(self, handle: int) -> None:
            self.closed += 1

        def GetLastError(self) -> int:
            return 5

    kernel = _Kernel()
    monkeypatch.setattr(events.ctypes, "windll", type("W", (), {"kernel32": kernel})(), raising=False)
    monkeypatch.setattr(events.ctypes, "GetLastError", kernel.GetLastError, raising=False)
    assert events._windows_process_exists(1234) is True

    monkeypatch.setattr(events.os, "name", "posix")
    monkeypatch.setattr(events.os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    assert events._process_exists(1) is False
    monkeypatch.setattr(events.os, "kill", lambda pid, sig: (_ for _ in ()).throw(PermissionError()))
    assert events._process_exists(1) is True
    monkeypatch.setattr(events.os, "kill", lambda pid, sig: (_ for _ in ()).throw(OSError("boom")))
    assert events._process_exists(1) is False
    monkeypatch.setattr(events.os, "kill", lambda pid, sig: None)
    assert events._process_exists(1) is True


def test_lock_helpers_retry_windows_sharing_violations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path = tmp_path / "events.jsonl.lock"
    owner = events._new_lock(events.LOCK_PROFILE_LOCAL)
    assert events._create_lock(lock_path, owner) is True

    calls = {"create": 0, "read": 0, "unlink": 0}
    real_open = events.os.open

    def flaky_open(*args, **kwargs):
        calls["create"] += 1
        if calls["create"] == 1:
            raise PermissionError("sharing")
        return real_open(*args, **kwargs)

    monkeypatch.setattr(events.os, "open", flaky_open)
    assert events._create_lock(tmp_path / "other.lock", events._new_lock(events.LOCK_PROFILE_LOCAL)) is False

    real_read = Path.read_bytes
    states = {"n": 0}

    def flaky_read(self: Path) -> bytes:
        if self == lock_path:
            states["n"] += 1
            if states["n"] == 1:
                raise PermissionError("sharing")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", flaky_read)
    record, raw = events._read_lock(lock_path)
    assert record is not None and raw is not None

    unlink_states = {"n": 0}
    real_unlink = Path.unlink

    def flaky_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == lock_path:
            unlink_states["n"] += 1
            if unlink_states["n"] == 1:
                raise PermissionError("sharing")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    events._release_lock_file(lock_path)
    assert not lock_path.exists()
