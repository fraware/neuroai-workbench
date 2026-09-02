from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from neuroai_workbench.collector.authorization import (
    LIVE_AUTHORIZATION_ENV,
    LIVE_COLLECTION_ENV,
    build_authorization_packet,
)
from neuroai_workbench.collector.scan import (
    SCAN_BOUNDARY,
    ScanResult,
    ensure_content_safety_scan,
    ensure_quarantine_result_scans,
)
from neuroai_workbench.shadow_refresh import live
from neuroai_workbench.util import atomic_write_json
from tests.unit.test_collector_schemas import (
    QUARANTINE_ID,
    RESULT_ID,
    valid_collection_result,
    valid_quarantine_record,
)


class _RecordingScanner:
    scanner_id = "test.recording"

    def __init__(self, *, state: str = "NOT_EXECUTED_FAIL_CLOSED") -> None:
        self.state = state
        self.calls: list[tuple[str, str, int]] = []

    def scan(self, *, sha256: str, media_type: str, size_bytes: int) -> ScanResult:
        self.calls.append((sha256, media_type, size_bytes))
        return ScanResult(
            state=self.state,
            scanner_id=self.scanner_id,
            detail="Synthetic content-safety test result.",
        )


class _RaisingScanner:
    def scan(self, *, sha256: str, media_type: str, size_bytes: int) -> ScanResult:
        del sha256, media_type, size_bytes
        raise RuntimeError("injected scanner failure")


class _PersistThenIncompleteScheduler:
    def __init__(self, **kwargs: Any) -> None:
        self.quarantine_root = Path(kwargs["quarantine_root"])

    def run_plan(
        self,
        plan: dict[str, Any],
        *,
        registry_sha256: str,
        source_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        del plan, source_index
        assert registry_sha256 == "a" * 64
        _persist_capture(self.quarantine_root)
        return {
            "run_id": "CRUN-scan-crash-window",
            "status": "INCOMPLETE",
            "execution_status": "INCOMPLETE_INTERNAL_ERROR",
            "counts": {
                "total": 1,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "incomplete": 1,
            },
            "outcomes": [
                {
                    "source_id": "SRC-0001",
                    "adapter_id": "json_api",
                    "status": "INCOMPLETE",
                    "reason": "internal_execution_error",
                }
            ],
        }


def _persist_capture(root: Path) -> None:
    atomic_write_json(root / "results" / f"{RESULT_ID}.json", valid_collection_result())
    atomic_write_json(root / "records" / f"{QUARANTINE_ID}.json", valid_quarantine_record())


def _authorize_live(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    packet = build_authorization_packet(
        authorization_id="AUTH-SCAN-TEST",
        authorized_by="test-operator",
        purpose="Controlled test of the live quarantine content-safety boundary.",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
        authorized_at="2026-09-02T12:00:00Z",
    )
    monkeypatch.setenv(LIVE_COLLECTION_ENV, "1")
    monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, json.dumps(packet))
    return packet


def _run_live_with_stub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    scanner: Any,
) -> dict[str, Any]:
    _authorize_live(monkeypatch)
    monkeypatch.setattr(live, "CollectionScheduler", _PersistThenIncompleteScheduler)
    return live.run_live_cohort_collection(
        plan={"due": [], "manual": [], "not_due": []},
        registry={"sources": []},
        registry_sha256="a" * 64,
        quarantine_root=tmp_path,
        content_safety_scanner=scanner,
    )


def test_durable_result_scan_is_persisted_and_resume_is_idempotent(tmp_path: Path) -> None:
    _persist_capture(tmp_path)
    scanner = _RecordingScanner()

    first = ensure_quarantine_result_scans(tmp_path, scanner=scanner)
    second = ensure_quarantine_result_scans(tmp_path, scanner=scanner)

    assert len(scanner.calls) == 1
    assert first == [
        {
            "result_id": RESULT_ID,
            "quarantine_id": QUARANTINE_ID,
            "state": "NOT_EXECUTED_FAIL_CLOSED",
            "scanner_id": scanner.scanner_id,
            "existing_scan_verified": False,
            "boundary": SCAN_BOUNDARY,
        }
    ]
    assert second[0]["existing_scan_verified"] is True
    persisted = json.loads((tmp_path / "scans" / f"{QUARANTINE_ID}.json").read_text(encoding="utf-8"))
    assert persisted["state"] == "NOT_EXECUTED_FAIL_CLOSED"
    assert persisted["boundary"] == SCAN_BOUNDARY


def test_empty_quarantine_has_no_scan_work(tmp_path: Path) -> None:
    scanner = _RecordingScanner()
    assert ensure_quarantine_result_scans(tmp_path, scanner=scanner) == []
    assert scanner.calls == []


def test_scanner_exception_fails_closed_without_scan_record(tmp_path: Path) -> None:
    _persist_capture(tmp_path)
    with pytest.raises(RuntimeError, match="injected scanner failure"):
        ensure_quarantine_result_scans(tmp_path, scanner=_RaisingScanner())
    assert not (tmp_path / "scans" / f"{QUARANTINE_ID}.json").exists()


@pytest.mark.parametrize(
    "payload, expected",
    [
        ([], "must be an object"),
        (
            {"state": "UNKNOWN", "scanner_id": "x", "detail": "x", "boundary": SCAN_BOUNDARY},
            "unknown state",
        ),
        (
            {"state": "NOT_EXECUTED_FAIL_CLOSED", "scanner_id": "", "detail": "x", "boundary": SCAN_BOUNDARY},
            "scanner_id",
        ),
        (
            {
                "state": "NOT_EXECUTED_FAIL_CLOSED",
                "scanner_id": "x",
                "detail": 1,
                "boundary": SCAN_BOUNDARY,
            },
            "detail",
        ),
        (
            {
                "state": "NOT_EXECUTED_FAIL_CLOSED",
                "scanner_id": "x",
                "detail": "x",
                "boundary": "wrong",
            },
            "boundary",
        ),
    ],
)
def test_tampered_persisted_scan_metadata_fails_closed(
    tmp_path: Path,
    payload: Any,
    expected: str,
) -> None:
    _persist_capture(tmp_path)
    atomic_write_json(tmp_path / "scans" / f"{QUARANTINE_ID}.json", payload)
    scanner = _RecordingScanner()
    with pytest.raises(ValueError, match=expected):
        ensure_quarantine_result_scans(tmp_path, scanner=scanner)
    assert scanner.calls == []


def test_missing_root_quarantine_record_fails_closed(tmp_path: Path) -> None:
    atomic_write_json(tmp_path / "results" / f"{RESULT_ID}.json", valid_collection_result())
    with pytest.raises(ValueError, match="exactly one root quarantine record"):
        ensure_quarantine_result_scans(tmp_path, scanner=_RecordingScanner())


def test_result_quarantine_binding_mismatch_fails_closed(tmp_path: Path) -> None:
    result = valid_collection_result()
    quarantine = valid_quarantine_record()
    quarantine["sha256"] = "d" * 64
    atomic_write_json(tmp_path / "results" / f"{RESULT_ID}.json", result)
    atomic_write_json(tmp_path / "records" / f"{QUARANTINE_ID}.json", quarantine)
    with pytest.raises(ValueError, match="sha256"):
        ensure_quarantine_result_scans(tmp_path, scanner=_RecordingScanner())


def test_duplicate_root_quarantine_binding_fails_closed(tmp_path: Path) -> None:
    _persist_capture(tmp_path)
    duplicate = valid_quarantine_record()
    duplicate["quarantine_id"] = "QRN-" + "4" * 32
    atomic_write_json(tmp_path / "records" / f"{duplicate['quarantine_id']}.json", duplicate)
    with pytest.raises(ValueError, match="found 2"):
        ensure_quarantine_result_scans(tmp_path, scanner=_RecordingScanner())


def test_successor_record_is_not_mistaken_for_root_capture(tmp_path: Path) -> None:
    _persist_capture(tmp_path)
    successor = valid_quarantine_record()
    successor["quarantine_id"] = "QRN-" + "5" * 32
    successor["predecessor_quarantine_id"] = QUARANTINE_ID
    successor["root_quarantine_id"] = QUARANTINE_ID
    atomic_write_json(tmp_path / "records" / f"{successor['quarantine_id']}.json", successor)
    scanner = _RecordingScanner()

    records = ensure_quarantine_result_scans(tmp_path, scanner=scanner)

    assert len(records) == 1
    assert records[0]["quarantine_id"] == QUARANTINE_ID
    assert len(scanner.calls) == 1


def test_explicit_successor_quarantine_argument_is_rejected(tmp_path: Path) -> None:
    result = valid_collection_result()
    successor = valid_quarantine_record()
    successor["quarantine_id"] = "QRN-" + "6" * 32
    successor["predecessor_quarantine_id"] = QUARANTINE_ID
    successor["root_quarantine_id"] = QUARANTINE_ID
    with pytest.raises(ValueError, match="root quarantine capture"):
        ensure_content_safety_scan(
            tmp_path,
            result,
            scanner=_RecordingScanner(),
            quarantine_record=successor,
        )


def test_non_object_durable_result_fails_closed(tmp_path: Path) -> None:
    atomic_write_json(tmp_path / "results" / f"{RESULT_ID}.json", [])
    with pytest.raises(ValueError, match="is not an object"):
        ensure_quarantine_result_scans(tmp_path, scanner=_RecordingScanner())


def test_live_path_scans_post_persist_crash_window_before_returning_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scanner = _RecordingScanner()

    package = _run_live_with_stub(monkeypatch, tmp_path, scanner=scanner)

    assert len(scanner.calls) == 1
    assert package["collection_run"]["status"] == "INCOMPLETE"
    assert package["content_safety"] == {
        "scope": "ALL_DURABLE_RESULTS_IN_QUARANTINE_ROOT",
        "durable_result_records_checked": 1,
        "scans_created": 1,
        "existing_scans_verified": 0,
        "state_counts": {"NOT_EXECUTED_FAIL_CLOSED": 1},
        "scanner_ids": [scanner.scanner_id],
        "detail_exposed": False,
        "boundary": SCAN_BOUNDARY,
    }
    assert package["collector"]["handoff_enabled"] is False
    assert "Synthetic content-safety test result" not in json.dumps(package)


def test_live_path_scanner_exception_prevents_package_return(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _authorize_live(monkeypatch)
    monkeypatch.setattr(live, "CollectionScheduler", _PersistThenIncompleteScheduler)

    with pytest.raises(RuntimeError, match="injected scanner failure"):
        live.run_live_cohort_collection(
            plan={"due": [], "manual": [], "not_due": []},
            registry={"sources": []},
            registry_sha256="a" * 64,
            quarantine_root=tmp_path,
            content_safety_scanner=_RaisingScanner(),
        )
