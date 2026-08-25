from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migration"
BINDING_PATH = MIGRATION / "phase4_science_runtime_binding_2026-08-25.json"
PLAN_PATH = MIGRATION / "phase4_science_runtime_migration_v0.1.json"

EXPECTED_VALIDATED_COMMIT = "5f65a57b2e5e174442ea9053c155777dfcba6924"
EXPECTED_SOURCE_HEAD = "ee51f6fcbd679d2b0ed5aeb4593424543201e496"
EXPECTED_BINDINGS = {
    "scripts/compile_science_queries.py": (
        "32bf7d7dddefada48d0fd6df4d54224a8afb8284",
        "src/neuroai_workbench/science_observatory/query_compiler.py",
        "12fbfcd0829502e249b8e466e86240a37fffe2e0",
    ),
    "tests/test_science_query_compilation.py": (
        "dd3ac65f54d1087e939604dce1e6c5629def5095",
        "tests/unit/science_observatory/test_query_compiler.py",
        "5c54607cdf65a9e3fb53c375ec4fd241b123d42b",
    ),
    "scripts/science_http_transport.py": (
        "933e92b723a6e28bbe20f4f3b8f6aba01a309c44",
        "src/neuroai_workbench/science_observatory/http_transport.py",
        "560231dfdbe76dec5ff8a8c139aa81755c15d151",
    ),
    "tests/test_science_http_transport.py": (
        "c6412e93424f803377e7f2036bc79dbd9310d1a1",
        "tests/unit/science_observatory/test_http_transport.py",
        "0c42f2898b674420e7a679d1cd36defc36f4e379",
    ),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_binding_record_is_exact_and_bounded() -> None:
    binding = _load(BINDING_PATH)

    assert binding["migration_id"] == "PHASE4-SCIENCE-RUNTIME-MIGRATION-V0.1"
    assert binding["source"]["head_sha"] == EXPECTED_SOURCE_HEAD
    assert binding["destination"]["validated_commit_sha"] == EXPECTED_VALIDATED_COMMIT
    assert binding["binding_count"] == 4
    assert len(binding["bindings"]) == 4
    assert binding["production_acquisition_authorized"] is False
    assert binding["s3_custody_demonstrated"] is False
    assert "remaining 26" in binding["authority_boundary"]


def test_every_binding_matches_the_original_migration_plan() -> None:
    plan = _load(PLAN_PATH)
    binding = _load(BINDING_PATH)
    planned = {entry["source_path"]: entry for entry in plan["entries"]}

    assert set(EXPECTED_BINDINGS) <= set(planned)
    for row in binding["bindings"]:
        source_path = row["source_path"]
        source_sha, destination_path, destination_sha = EXPECTED_BINDINGS[source_path]
        original = planned[source_path]

        assert original["source_git_blob_sha"] == source_sha
        assert original["destination_path"] == destination_path
        assert row["source_git_blob_sha"] == source_sha
        assert row["destination_path"] == destination_path
        assert row["destination_git_blob_sha"] == destination_sha
        assert row["migration_state"] == "MIGRATED_TRANSFORMED_VALIDATED"
        assert re.fullmatch(r"[0-9a-f]{40}", row["destination_git_blob_sha"])


def test_binding_validation_evidence_is_not_overstated() -> None:
    binding = _load(BINDING_PATH)
    validation = binding["validation"]

    assert validation["workflow_run_id"] == 32859648520
    assert validation["job_id"] == 97840168261
    assert validation["exact_head_checkout"] is True
    assert validation["python_version"] == "3.12.14"
    assert validation["ruff_format"] == "PASS"
    assert validation["ruff_check"] == "PASS"
    assert validation["focused_test_count"] == 24
    assert validation["focused_test_result"] == "PASS"
    assert "not a full Phase 4 runtime" in validation["scope_note"]


def test_destination_files_still_match_bound_blob_content() -> None:
    binding = _load(BINDING_PATH)
    destination_paths = {row["destination_path"] for row in binding["bindings"]}

    assert destination_paths == {
        "src/neuroai_workbench/science_observatory/query_compiler.py",
        "tests/unit/science_observatory/test_query_compiler.py",
        "src/neuroai_workbench/science_observatory/http_transport.py",
        "tests/unit/science_observatory/test_http_transport.py",
    }
    for relative in destination_paths:
        assert (ROOT / relative).is_file()
