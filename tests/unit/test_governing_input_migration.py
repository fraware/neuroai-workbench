from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroai_workbench.migration_ops.adapters import adapt_inaccessible
from neuroai_workbench.migration_ops.constants import (
    ACCESS_INACCESSIBLE,
    DISPOSITION_PENDING,
    MIGRATION_BLOCKED,
)
from neuroai_workbench.migration_ops.inventory import load_archive_inventory
from neuroai_workbench.migration_ops.verification import build_migration_verification

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/migration"
RECORDED_AT = "2026-08-02T14:00:00Z"
EXPECTED = json.loads((FIXTURES / "expected_verification_summary.json").read_text(encoding="utf-8"))


def test_migration_verification_is_deterministic():
    first = build_migration_verification(REPO_ROOT, recorded_at=RECORDED_AT)
    second = build_migration_verification(REPO_ROOT, recorded_at=RECORDED_AT)
    assert first == second
    assert first["verification_digest"] == EXPECTED["verification_digest"]
    assert first["verification_id"] == EXPECTED["verification_id"]
    assert first["summary"] == EXPECTED["summary"]
    assert first["human_disposition"] == DISPOSITION_PENDING


def test_golden_lineage_digests_match():
    document = build_migration_verification(REPO_ROOT, recorded_at=RECORDED_AT)
    by_id = {record["inventory_id"]: record for record in document["records"]}
    for inventory_id, expected_digest in EXPECTED["lineage_digests"].items():
        assert by_id[inventory_id]["lineage_digest"] == expected_digest


def test_inaccessible_governing_objects_never_invent_values():
    document = build_migration_verification(REPO_ROOT, recorded_at=RECORDED_AT)
    blocked = [record for record in document["records"] if record["inventory_id"] in EXPECTED["blocked_inventory_ids"]]
    assert len(blocked) == 2
    for record in blocked:
        assert record["migration_state"] == MIGRATION_BLOCKED
        assert record["source_sha256"] == ACCESS_INACCESSIBLE
        assert record["lineage_digest"] == "UNKNOWN"
        assert record["material_warnings"]
        assert record["material_warnings"][0]["human_disposition"] == DISPOSITION_PENDING


def test_material_warnings_include_human_disposition():
    document = build_migration_verification(REPO_ROOT, recorded_at=RECORDED_AT)
    assert document["material_warnings"]
    for warning in document["material_warnings"]:
        assert warning["human_disposition"] == DISPOSITION_PENDING


def test_committed_template_matches_generator():
    template_path = REPO_ROOT / "migration/MIGRATION_VERIFICATION.json"
    assert template_path.is_file()
    template = json.loads(template_path.read_text(encoding="utf-8"))
    generated = build_migration_verification(REPO_ROOT, recorded_at=RECORDED_AT)
    assert template["verification_digest"] == generated["verification_digest"]


@pytest.mark.parametrize(
    "inventory_id",
    [
        "INV-OBS-V14",
        "INV-OBS-V17",
        "INV-ASM-PRIMA",
        "INV-ASM-BG2",
        "INV-ASM-ADBS",
        "INV-ASM-B2Q",
        "INV-REG-SAMPLE",
        "INV-PROG-PRIMA",
    ],
)
def test_accessible_governing_records_migrate(inventory_id: str):
    document = build_migration_verification(REPO_ROOT, recorded_at=RECORDED_AT)
    record = next(item for item in document["records"] if item["inventory_id"] == inventory_id)
    assert record["migration_state"] == "MIGRATED"
    assert record["access_state"] == "ACCESSIBLE"
    assert len(record["source_sha256"]) == 64


def test_inaccessible_adapter_emits_typed_states():
    entry = {
        "inventory_id": "INV-TEST",
        "family": "OBSERVATORY_V1_6",
        "archive_key": "external/archive/observatory_v1.6_live_refresh_delta.json",
        "sha256": "INACCESSIBLE",
        "governing": True,
        "notes": "fixture",
    }
    record = adapt_inaccessible(entry, reason="fixture inaccessible")
    assert record["source_sha256"] == ACCESS_INACCESSIBLE
    assert record["lineage_digest"] == "UNKNOWN"


def test_inventory_loader_rejects_non_object_lines(tmp_path: Path):
    bad_inventory = tmp_path / "bad.jsonl"
    bad_inventory.write_text('{"inventory_id":"OK"}\n"not-an-object"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Inventory line 2"):
        load_archive_inventory(bad_inventory)
