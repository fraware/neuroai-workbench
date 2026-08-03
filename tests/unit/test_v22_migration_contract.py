from __future__ import annotations

import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "examples" / "migration" / "V2_2_MIGRATION_CONTRACT.json"
DISPOSITIONS = REPO_ROOT / "examples" / "migration" / "V2_2_WORKBOOK_SHEET_DISPOSITIONS.csv"


def test_v22_migration_contract_has_expected_programme_totals() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract["contract_version"] == "1.0.0"
    assert contract["baseline_release"] == "v2.2.0"
    assert contract["target_release"] == "v2.3.0-dev"
    assert contract["expected_sheet_count"] == 48
    assert contract["expected_key_counts"]["Organizations"] == 223
    assert contract["expected_key_counts"]["Sources"] == 224
    assert contract["expected_key_counts"]["Assessment_Findings"] == 312

    summaries = contract["assessment_summary"]
    assert set(summaries) == {"Brain2Qwerty", "FDA adaptive DBS", "BrainGate2 T15", "PRIMA"}
    for summary in summaries.values():
        assert summary["PASS"] + summary["PARTIAL"] + summary["FAIL"] + summary["NOT ASSESSED"] == 78
        assert summary["TOTAL"] == 78


def test_every_v22_workbook_sheet_has_one_explicit_disposition() -> None:
    with DISPOSITIONS.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    names = [row["sheet"] for row in rows]
    assert len(rows) == 48
    assert len(names) == len(set(names))
    assert all(row["role"] for row in rows)
    assert all(row["disposition"] for row in rows)
    assert all(row["update_requirement"] for row in rows)

    expected_canonical = {
        "Organizations",
        "Sources",
        "Assessment_Findings",
        "Assessment_Claims",
        "Assessment_Evidence",
        "Assessment_Endpoints",
        "Assessment_Gaps",
    }
    by_name = {row["sheet"]: row for row in rows}
    assert expected_canonical <= set(by_name)
    assert all("MIGRATE" in by_name[name]["disposition"] for name in expected_canonical)
