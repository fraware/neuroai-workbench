"""Validate archive inventory entries and recompute fixture digests."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "archive-inventory.schema.json"
INVENTORY_PATH = ROOT / "migration" / "archive_inventory.jsonl"
AMBIGUITIES_PATH = ROOT / "migration" / "unresolved_ambiguities.json"
DECISIONS_PATH = ROOT / "migration" / "MIGRATION_DECISIONS.jsonl"

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
        "INV-EXT-V16-REFRESH",
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
        if row.get("ops_relpath"):
            assert ABSOLUTE_PATH_RE.search(row["ops_relpath"]) is None
            assert "\\" not in row["ops_relpath"]
            assert not Path(row["ops_relpath"]).is_absolute()
        assert row["boundary"] == BOUNDARY


def test_external_digest_verified_objects_have_hashes() -> None:
    rows = {row["inventory_id"]: row for row in _load_inventory()}
    for inv_id, expected_sha, expected_size in (
        ("INV-EXT-REG-V15", "1d1f9774a3ad559792fa2bc7e459a4a65c6574ec14fa0b1501240bbb18dcc315", 167593),
        ("INV-EXT-V16-REFRESH", "937b2fcd807392e64f946f88a89756cc91890cc6db9f98e519035725e46c7035", 26240),
        ("INV-EXT-V16-DELTA", "49ef4944e4dd7e5d4b3534926e41220a1493ef12d68965a7b6caa4431524b0c5", 4058),
    ):
        assert rows[inv_id]["sha256"] == expected_sha
        assert rows[inv_id]["size_bytes"] == expected_size
        assert rows[inv_id]["ops_relpath"]
    assert rows["INV-EXT-COMBINED-XLSX"]["sha256"] == "INACCESSIBLE"
    assert rows["INV-EXT-COMBINED-XLSX"]["size_bytes"] == 0


def test_starter_zip_verified_locally() -> None:
    rows = {row["inventory_id"]: row for row in _load_inventory()}
    starter = rows["INV-EXT-STARTER"]
    assert starter["sha256"] == "7f9162bff65e3572a9d148ba2fb7ad86439a93ab111597a97861a82554a207b0"
    assert starter["size_bytes"] == 221520
    ambiguities = json.loads(AMBIGUITIES_PATH.read_text(encoding="utf-8"))
    assert ambiguities["starter_zip"]["local_status"] == "ACCESSIBLE"
    by_id = {item["ambiguity_id"]: item for item in ambiguities["ambiguities"]}
    assert by_id["AMB-001"]["status"] == "RESOLVED_OPS_DIGEST_VERIFIED"
    assert by_id["AMB-002"]["status"] == "RESOLVED_OPS_DIGEST_VERIFIED"
    assert by_id["AMB-003"]["status"] == "INACCESSIBLE"
    assert by_id["AMB-004"]["status"] == "RESOLVED_REPO_EXISTS"
    assert "neuroai-observatory-data" in by_id["AMB-004"]["url"]


def test_migration_decisions_close_material_items() -> None:
    assert DECISIONS_PATH.is_file()
    decisions = [json.loads(line) for line in DECISIONS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    subjects = {item["subject_id"] for item in decisions}
    assert "AMB-003" in subjects
    assert "MIGRATION_VERIFICATION" in subjects
    top = next(item for item in decisions if item["subject_id"] == "MIGRATION_VERIFICATION")
    assert top["disposition"] == "ACCEPTED_WITH_RESIDUALS"
    assert "AMB-003" in top["residuals"]


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
    assert "HISTORICAL_ONLY" in roles
    assert "OPERATIONS_POLICY" in roles
