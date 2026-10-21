"""Offline R1.7 literature pilot exercises exact capture bindings with synthetic bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from neuroai_workbench.product_discovery_frames import ProductDiscoveryError
from neuroai_workbench.release_a_r1_literature_pilot import (
    BUNDLE_ID,
    UNRESOLVED,
    WITH_LEADS,
    ZERO,
    combine_bundles,
    import_snapshot,
    literature_worklist,
    select_distinct_pilots,
)
from neuroai_workbench.release_a_r1_route_execution_ledger import derive_ledger_state

ROOT = Path(__file__).resolve().parents[2]


def _decision(
    capture: dict[str, str],
    snapshot: bytes,
    *,
    completion: str = UNRESOLVED,
    keys: list[str] | None = None,
) -> dict[str, object]:
    locator = capture["suggested_public_locator"]
    return {
        "capture_id": capture["capture_id"],
        "source_locator": locator,
        "knowledge_observed_at": "2026-10-01T00:00:00Z",
        "retrieval_request": {
            "method": "GET",
            "locator": locator,
            "request_context": {"query_or_seed_id": capture["query_or_seed_id"]},
        },
        "response_context": {
            "retrieval_status": "RETRIEVED",
            "content_type": "text/html",
            "encoding": "utf-8",
            "final_locator": locator,
            "response_metadata": {"status_code": 200, "raw_sha256": hashlib.sha256(snapshot).hexdigest()},
        },
        "completion_state": completion,
        "extracted_candidate_keys": [] if keys is None else keys,
    }


def test_frozen_population_and_pilot_selection() -> None:
    rows = literature_worklist()
    assert len(rows) == 21
    assert len({row["capture_id"] for row in rows}) == 21
    assert len({row["work_item_id"] for row in rows}) == 21
    assert {row["pmid"] for row in rows} == {"42505450", "42645991", "42022893", "41939223"}
    assert all(row["frame_id"] == "F6" for row in rows)
    assert all(row["execution_status"] == "PENDING_NEW_SOURCE_EVIDENCE" for row in rows)
    selected = select_distinct_pilots()
    assert len(selected) == 3
    assert len({row["pmid"] for row in selected}) == 3
    assert selected == select_distinct_pilots()
    assert len(select_distinct_pilots(4)) == 4
    with pytest.raises(ValueError, match="positive"):
        select_distinct_pilots(0)
    with pytest.raises(ValueError, match="exceeds"):
        select_distinct_pilots(5)


def test_unresolved_snapshot_stays_pending_and_exactly_bound() -> None:
    item = select_distinct_pilots(1)[0]
    snapshot = b"<html>SYNTHETIC MOCK RECORD; NO REAL PUBLICATION</html>"
    bundle = import_snapshot(snapshot, _decision(item, snapshot))
    assert bundle["bundle_id"] == BUNDLE_ID
    assert bundle["pmid"] == item["pmid"]
    assert bundle["raw_snapshot_sha256"] == hashlib.sha256(snapshot).hexdigest()
    assert bundle["derived_state"]["completed_work_item_count"] == 0
    assert bundle["derived_state"]["pending_work_item_count"] == 192
    assert bundle["derived_state"]["unresolved_barrier_work_item_count"] == 1
    entry = bundle["ledger_entry"]
    assert entry["route_execution_record"]["work_item_completion_claimed"] is False
    assert entry["route_execution_record"]["covered_capture_ids"] == [item["capture_id"]]
    artifact = next(iter(bundle["evidence_archive"].values()))
    assert artifact["content_representation"] == "BASE64_BYTES"
    assert artifact["capture_id"] == item["capture_id"]
    assert derive_ledger_state([entry], evidence_archive=bundle["evidence_archive"]) == bundle["derived_state"]


def test_explicit_zero_lead_decision_does_not_create_product_identity() -> None:
    item = select_distinct_pilots(1)[0]
    snapshot = b"TEST ONLY; independent researcher reviewed complete synthetic record."
    bundle = import_snapshot(snapshot, _decision(item, snapshot, completion=ZERO))
    state = bundle["derived_state"]
    assert state["completed_work_item_count"] == 1
    assert state["pending_work_item_count"] == 191
    assert state["extracted_lead_count"] == 0
    assert bundle["ledger_entry"]["route_execution_record"]["completion_state"] == ZERO


def test_explicit_lead_state_uses_noncanonical_identity() -> None:
    item = select_distinct_pilots(1)[0]
    snapshot = b"SYNTHETIC RECORD: device name Example EEG Headset."
    bundle = import_snapshot(
        snapshot, _decision(item, snapshot, completion=WITH_LEADS, keys=["Example EEG Headset"])
    )
    record = bundle["ledger_entry"]["route_execution_record"]
    assert record["work_item_completion_claimed"] is True
    assert len(record["extracted_leads"]) == 1
    assert record["extracted_leads"][0]["canonical_offering_id"] is None
    assert bundle["derived_state"]["active_extracted_lead_count"] == 1


def test_two_distinct_capture_bundles_aggregate_without_deduplication() -> None:
    first, second = select_distinct_pilots(2)
    a = b"synthetic distinct record A"
    b = b"synthetic distinct record B"
    records = [
        import_snapshot(a, _decision(first, a, completion=ZERO)),
        import_snapshot(b, _decision(second, b)),
    ]
    combined = combine_bundles(records)
    assert len(combined["ledger_entries"]) == 2
    assert combined["derived_state"]["completed_work_item_count"] == 1
    assert combined["derived_state"]["unresolved_barrier_work_item_count"] == 1
    assert combined["derived_state"]["pending_work_item_count"] == 191
    with pytest.raises(ProductDiscoveryError, match="Duplicate literature evidence reference"):
        combine_bundles([records[0], records[0]])
    with pytest.raises(ProductDiscoveryError, match="At least one"):
        combine_bundles([])
    with pytest.raises(ProductDiscoveryError, match="not a literature"):
        combine_bundles([{"bundle_id": "unknown"}])
    with pytest.raises(ProductDiscoveryError, match="invalid record"):
        combine_bundles([{"bundle_id": BUNDLE_ID, "ledger_entry": None, "evidence_archive": {}}])


def test_offline_import_rejects_unsubstantiated_or_mismatched_claims() -> None:
    item = select_distinct_pilots(1)[0]
    snapshot = b"SYNTHETIC DATA ONLY"
    decision = _decision(item, snapshot)
    variants = [
        ({"capture_id": "PDC-false"}, "outside the frozen"),
        ({"completion_state": ZERO, "extracted_candidate_keys": ["unsupported"]}, "Lead-bearing"),
        ({"completion_state": WITH_LEADS}, "Lead-bearing"),
        ({"completion_state": "INCLUDE"}, "allowed completion"),
        ({"knowledge_observed_at": "2026-10-25T00:00:00Z"}, "cutoff"),
        ({"source_locator": "http://unsafe.example"}, "HTTPS"),
        ({"retrieval_request": {}}, "supplied GET locator"),
        ({"response_context": {}}, "response metadata"),
        ({"extracted_candidate_keys": [None]}, "nonblank"),
    ]
    for patch, message in variants:
        modified = {**decision, **patch}
        with pytest.raises(ProductDiscoveryError, match=message):
            import_snapshot(snapshot, modified)
    with pytest.raises(ProductDiscoveryError, match="exact fields"):
        import_snapshot(snapshot, {k: v for k, v in decision.items() if k != "completion_state"})
    with pytest.raises(ProductDiscoveryError, match="saved bytes"):
        import_snapshot(b"", decision)
    with pytest.raises(ProductDiscoveryError, match="raw_sha256"):
        import_snapshot(snapshot + b"tamper", decision)
    with pytest.raises(ProductDiscoveryError, match="frozen query"):
        bad = _decision(item, snapshot)
        bad["retrieval_request"] = {
            "method": "GET", "locator": item["suggested_public_locator"],
            "request_context": {"query_or_seed_id": "wrong"},
        }
        import_snapshot(snapshot, bad)


def test_cli_catalog_and_synthetic_ingest(tmp_path: Path) -> None:
    catalog = subprocess.run(
        [sys.executable, "-m", "scripts.r1_7_literature_pilot", "catalog"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
    )
    assert json.loads(catalog.stdout)["work_item_count"] == 21
    pilot = subprocess.run(
        [sys.executable, "-m", "scripts.r1_7_literature_pilot", "pilot", "--count", "3"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
    )
    assert json.loads(pilot.stdout)["selected_distinct_papers"] == 3
    item = select_distinct_pilots(1)[0]
    data = b"synthetic fixture, not a real source"
    snapshot = tmp_path / "response.bin"
    snapshot.write_bytes(data)
    decision = tmp_path / "decision.json"
    decision.write_text(json.dumps(_decision(item, data)), encoding="utf-8")
    created = subprocess.run(
        [sys.executable, "-m", "scripts.r1_7_literature_pilot", "ingest", "--decision",
         str(decision), "--snapshot", str(snapshot)],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
    )
    bundle = json.loads(created.stdout)
    assert bundle["derived_state"]["pending_work_item_count"] == 192
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(created.stdout, encoding="utf-8")
    combined = subprocess.run(
        [sys.executable, "-m", "scripts.r1_7_literature_pilot", "combine", str(bundle_path)],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
    )
    assert json.loads(combined.stdout)["derived_state"]["active_ledger_entry_count"] == 1
