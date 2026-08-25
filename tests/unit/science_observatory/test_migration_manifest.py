from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "migration" / "phase4_science_runtime_migration_v0.1.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_source_and_destination_boundaries_are_exact() -> None:
    manifest = _manifest()

    assert manifest["source"]["head_sha"] == "ee51f6fcbd679d2b0ed5aeb4593424543201e496"
    assert manifest["source"]["tree_sha"] == "c8671f41518ecd259c7c08c25b1aed74aeb896c5"
    assert manifest["destination"]["base_commit_sha"] == "2349a1f0125ceadbe4f6802e3686963e74360b7f"
    assert manifest["destination"]["runtime_package_root"] == "src/neuroai_workbench/science_observatory"
    assert manifest["configuration_boundary"]["state"] == "EXPLICIT_S2_INPUT_REQUIRED"
    assert manifest["configuration_boundary"]["production_acquisition_authorized"] is False
    assert manifest["configuration_boundary"]["s3_custody_demonstrated"] is False


def test_all_thirty_source_entries_are_unique_and_git_bound() -> None:
    manifest = _manifest()
    entries = manifest["entries"]

    assert manifest["entry_count"] == 30
    assert len(entries) == 30
    assert len({entry["source_path"] for entry in entries}) == 30
    assert len({entry["destination_path"] for entry in entries}) == 30
    assert all(re.fullmatch(r"[0-9a-f]{40}", entry["source_git_blob_sha"]) for entry in entries)


def test_runtime_destination_avoids_existing_observatory_module_namespace() -> None:
    entries = _manifest()["entries"]
    runtime = [entry for entry in entries if entry["source_path"].startswith("scripts/")]
    runtime_tests = [entry for entry in entries if entry["source_path"].startswith("tests/")]

    assert len(runtime) == 11
    assert len(runtime_tests) == 11
    assert all(entry["destination_path"].startswith("src/neuroai_workbench/science_observatory/") for entry in runtime)
    assert all(entry["destination_path"].startswith("tests/unit/science_observatory/") for entry in runtime_tests)
    assert not any("src/neuroai_workbench/observatory/science/" in entry["destination_path"] for entry in runtime)


def test_planned_state_does_not_claim_destination_identity() -> None:
    manifest = _manifest()

    assert manifest["bound_destination_count"] == 0
    assert manifest["transformed_destination_count"] == 0
    for entry in manifest["entries"]:
        assert entry["state"] in {"PLANNED", "PLANNED_TRANSFORM_REQUIRED"}
        assert entry["destination_git_blob_sha"] is None
        assert entry["destination_commit_sha"] is None
    assert "PLANNED" in manifest["authority_boundary"]
    assert "No production acquisition" in manifest["authority_boundary"]
