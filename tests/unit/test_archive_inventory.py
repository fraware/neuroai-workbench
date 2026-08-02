"""Validate archive inventory entries and recompute fixture digests."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "archive-inventory.schema.json"
INVENTORY_PATH = ROOT / "migration" / "archive_inventory.jsonl"
AMBIGUITIES_PATH = ROOT / "migration" / "unresolved_ambiguities.json"

BOUNDARY = "Inventory classifies storage lineage only; it does not validate substantive claims."

ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")
SECRET_RE = re.compile(
    r"(api[_-]?key|secret|password|token|bearer\s+[A-Za-z0-9._\-]+)",
    re.IGNORECASE,
)


def _load_schema() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _load_inventory() -> list[dict]:
    rows: list[dict] = []
    for line in INVENTORY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def test_inventory_schema_validates_all_rows() -> None:
    validator = _load_schema()
    rows = _load_inventory()
    assert len(rows) >= 10
    for row in rows:
        errors = sorted(validator.iter_errors(row), key=lambda e: list(e.path))
        assert not errors, f"{row.get('inventory_id')}: {errors[0].message}"


def test_governing_objects_present() -> None:
    rows = _load_inventory()
    governing = {row["inventory_id"] for row in rows if row["governing"]}
    required = {
        "INV-OBS-V14",
        "INV-OBS-V17",
        "INV-ASM-PRIMA",
        "INV-ASM-BG2",
        "INV-ASM-ADBS",
        "INV-ASM-B2Q",
        "INV-REG-SAMPLE",
        "INV-EXT-V16-DELTA",
        "INV-EXT-REG-V15",
    }
    assert required <= governing


def test_recompute_sha256_for_workbench_fixtures() -> None:
    rows = _load_inventory()
    checked = 0
    for row in rows:
        rel = row.get("workbench_path")
        if not rel:
            continue
        path = ROOT / rel
        assert path.is_file(), rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert row["sha256"] == digest, rel
        assert row["size_bytes"] == path.stat().st_size, rel
        checked += 1
    assert checked >= 10


def test_no_absolute_paths_or_secrets_in_public_inventory() -> None:
    text = INVENTORY_PATH.read_text(encoding="utf-8")
    assert SECRET_RE.search(text) is None
    for row in _load_inventory():
        assert ABSOLUTE_PATH_RE.search(row["archive_key"]) is None
        assert "\\" not in row["archive_key"]
        if row.get("workbench_path"):
            assert ABSOLUTE_PATH_RE.search(row["workbench_path"]) is None
            assert not Path(row["workbench_path"]).is_absolute()
        assert row["boundary"] == BOUNDARY


def test_inaccessible_external_objects_do_not_invent_hashes() -> None:
    rows = {row["inventory_id"]: row for row in _load_inventory()}
    for inv_id in ("INV-EXT-V16-DELTA", "INV-EXT-REG-V15", "INV-EXT-COMBINED-XLSX"):
        assert rows[inv_id]["sha256"] in {"INACCESSIBLE", "NOT_YET_VERIFIED"}
        assert rows[inv_id]["size_bytes"] == 0


def test_starter_zip_declared_digest_recorded() -> None:
    rows = {row["inventory_id"]: row for row in _load_inventory()}
    starter = rows["INV-EXT-STARTER"]
    assert starter["sha256"] == "7f9162bff65e3572a9d148ba2fb7ad86439a93ab111597a97861a82554a207b0"
    ambiguities = json.loads(AMBIGUITIES_PATH.read_text(encoding="utf-8"))
    assert ambiguities["starter_zip"]["local_status"] == "INACCESSIBLE"
    assert len(ambiguities["ambiguities"]) >= 4


def test_schema_rejects_absolute_archive_key_and_extra_properties() -> None:
    validator = _load_schema()
    base = _load_inventory()[0].copy()
    bad_abs = {**base, "archive_key": "/etc/passwd"}
    assert list(validator.iter_errors(bad_abs))
    bad_extra = {**base, "credential": "secret"}
    assert list(validator.iter_errors(bad_extra))
    bad_tz = {**base, "recorded_at": "2026-08-02T14:00:00"}
    assert list(validator.iter_errors(bad_tz))


def test_coverage_includes_all_roles_used() -> None:
    roles = {row["role"] for row in _load_inventory()}
    assert "CANONICAL_INPUT" in roles
    assert "GENERATED_VIEW" in roles
    assert "UNRESOLVED" in roles
    assert "HISTORICAL_ONLY" in roles
