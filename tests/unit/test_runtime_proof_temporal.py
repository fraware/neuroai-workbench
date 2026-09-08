from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.collector.runtime_proof_temporal import (
    RuntimeProofTemporalError,
    require_phase3_result_eligible_at_cutoff,
)
from neuroai_workbench.util import sha256_bytes

SOURCE_ID = "SRC-P3-CTGOV"
URL = "https://clinicaltrials.gov/api/v2/studies/NCT00000001"


def _seed_capture(
    root: Path,
    *,
    result_id: str = "CRES-P3-TEMPORAL",
    retrieved_at: str = "2026-09-05T12:00:00Z",
    source_id: str = SOURCE_ID,
) -> Path:
    body = b'{"protocolSection":{"identificationModule":{"nctId":"NCT00000001"}}}'
    digest = sha256_bytes(body)
    relative = f"incoming/{source_id}/{digest[:12]}/capture.json"
    capture = root / relative
    capture.parent.mkdir(parents=True, exist_ok=True)
    capture.write_bytes(body)
    record = {
        "result_id": result_id,
        "source_id": source_id,
        "monitor_id": "MON-P3-CTGOV",
        "requested_url": URL,
        "retrieved_at": retrieved_at,
        "sha256": digest,
        "quarantine_path": relative,
        "size_bytes": len(body),
        "media_type": "application/json",
        "original_filename": "capture.json",
    }
    results = root / "results"
    results.mkdir(parents=True, exist_ok=True)
    record_path = results / f"{result_id}.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    return capture


def test_exact_capture_is_eligible_at_same_day_cutoff(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root)

    reference = require_phase3_result_eligible_at_cutoff(
        root,
        result_id="CRES-P3-TEMPORAL",
        as_of="2026-09-05",
        expected_source_id=SOURCE_ID,
    )

    assert reference.result_id == "CRES-P3-TEMPORAL"
    assert reference.retrieved_at == "2026-09-05T12:00:00Z"


def test_capture_newer_than_replay_cutoff_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, retrieved_at="2026-09-05T12:00:00Z")

    with pytest.raises(RuntimeProofTemporalError, match="cutoff precedes the exact expected capture"):
        require_phase3_result_eligible_at_cutoff(
            root,
            result_id="CRES-P3-TEMPORAL",
            as_of="2026-09-04T23:59:59Z",
            expected_source_id=SOURCE_ID,
        )


def test_exact_timestamp_cutoff_is_inclusive(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root, retrieved_at="2026-09-05T12:00:00+00:00")

    reference = require_phase3_result_eligible_at_cutoff(
        root,
        result_id="CRES-P3-TEMPORAL",
        as_of="2026-09-05T12:00:00Z",
        expected_source_id=SOURCE_ID,
    )

    assert reference.result_id == "CRES-P3-TEMPORAL"


def test_invalid_or_naive_cutoff_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root)

    for as_of in ("not-a-date", "2026-09-05T12:00:00"):
        with pytest.raises(RuntimeProofTemporalError, match="cutoff is invalid"):
            require_phase3_result_eligible_at_cutoff(
                root,
                result_id="CRES-P3-TEMPORAL",
                as_of=as_of,
                expected_source_id=SOURCE_ID,
            )


def test_source_substitution_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    _seed_capture(root)

    with pytest.raises(RuntimeProofTemporalError, match="source_id"):
        require_phase3_result_eligible_at_cutoff(
            root,
            result_id="CRES-P3-TEMPORAL",
            as_of="2026-09-05",
            expected_source_id="SRC-SUBSTITUTED",
        )


def test_capture_integrity_tampering_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    capture = _seed_capture(root)
    capture.write_bytes(capture.read_bytes() + b" ")

    with pytest.raises(RuntimeProofTemporalError, match="integrity validation"):
        require_phase3_result_eligible_at_cutoff(
            root,
            result_id="CRES-P3-TEMPORAL",
            as_of="2026-09-05",
            expected_source_id=SOURCE_ID,
        )


def test_missing_and_invalid_result_identity_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "quarantine"
    with pytest.raises(RuntimeProofTemporalError, match="record is missing"):
        require_phase3_result_eligible_at_cutoff(
            root,
            result_id="CRES-P3-MISSING",
            as_of="2026-09-05",
        )

    with pytest.raises(RuntimeProofTemporalError, match="result_id is invalid"):
        require_phase3_result_eligible_at_cutoff(
            root,
            result_id="../escape",
            as_of="2026-09-05",
        )
