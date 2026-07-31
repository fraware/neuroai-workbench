from __future__ import annotations

import hashlib
import json
from pathlib import Path

from neuroai_workbench.migration import migrate_v4_1_2
from neuroai_workbench.util import canonical_json_bytes
from neuroai_workbench.validation import validate_assessment


def test_v4_1_2_migration_is_valid_and_additive():
    source_path = Path(__file__).parents[1] / "fixtures/PILOT-02_v4.1.2.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    migrated = migrate_v4_1_2(source)
    assert migrated["assessment_metadata"]["instrument_version"] == "v4.2"
    assert migrated["assessment_metadata"]["migrated_from_version"] == "v4.1.2"
    assert migrated["legacy_bounded_decision"] == source["bounded_decision"]
    assert [row["finding_status"] for row in migrated["requirement_findings"]] == [
        row["finding_status"] for row in source["requirement_findings"]
    ]
    assert validate_assessment(migrated).valid


def test_migration_source_hash_is_exact():
    source_path = Path(__file__).parents[1] / "fixtures/PILOT-02_v4.1.2.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    migrated = migrate_v4_1_2(source)
    expected = hashlib.sha256(canonical_json_bytes(source)).hexdigest()
    assert migrated["migration_provenance"]["source_sha256"] == expected
