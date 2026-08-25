from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migration"

EXPECTED_ARCHIVE_SHA256 = "bf4656c60470e87cd2b454f6aea557a3b51a09cf2de8793fd6d844942b62f0f1"
EXPECTED_ARCHIVE_SIZE = 78_309_902
EXPECTED_ARCHIVE_ENTRIES = 1_669
EXPECTED_XLSX_SHA256 = "db5bfca8c30e8b1945c52dc208dcbb486d1e0146adeb125b7fef9f557fcaa49a"
EXPECTED_DOCX_SHA256 = "881db3fecc53b4c9389de63b877c4552eca11cf0ac6f81fcb73594cef6c6fb3a"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_archive_registration_is_identity_only_and_outside_git() -> None:
    record = _load(MIGRATION / "archive_registration_2026-08-25.json")
    archive = record["outer_archive"]

    assert record["archive_class"] == "IMMUTABLE_PREDECESSOR_S5"
    assert archive["sha256"] == EXPECTED_ARCHIVE_SHA256
    assert archive["size_bytes"] == EXPECTED_ARCHIVE_SIZE
    assert archive["zip_entry_count"] == EXPECTED_ARCHIVE_ENTRIES
    assert archive["zip_crc_check"] == "PASS"
    assert archive["bytes_committed_to_repository"] is False

    wrapper = record["outer_wrapper_observation"]
    assert wrapper["status"] == "SUCCESSOR_WRAPPER_REQUIRES_OWN_REGISTRATION"
    assert wrapper["historical_manifests_modified"] is False


def test_generated_products_remain_noncanonical() -> None:
    record = _load(MIGRATION / "archive_registration_2026-08-25.json")
    products = {item["filename"]: item for item in record["newly_accessible_generated_products"]}

    xlsx = products["UNESCO_NeuroAI_All_Data_Combined_v2.2.0.xlsx"]
    docx = products["UNESCO_NeuroAI_All_Reports_Findings_and_Conclusions_Combined_v2.2.0.docx"]

    assert xlsx["sha256"] == EXPECTED_XLSX_SHA256
    assert docx["sha256"] == EXPECTED_DOCX_SHA256
    for product in (xlsx, docx):
        assert product["store_class"] == "S4_GENERATED_ARTIFACT"
        assert product["canonical_master"] is False
        assert product["related_ambiguity"] == "AMB-003"


def test_amb003_review_advances_accessibility_without_rewriting_predecessor() -> None:
    predecessor = _load(MIGRATION / "unresolved_ambiguities.json")
    review = _load(MIGRATION / "ambiguity_review_amb003_2026-08-25.json")

    predecessor_amb003 = next(item for item in predecessor["ambiguities"] if item["ambiguity_id"] == "AMB-003")
    assert predecessor_amb003["status"] == "INACCESSIBLE"

    assert review["predecessor_record"]["ambiguity_id"] == "AMB-003"
    assert review["predecessor_record"]["predecessor_status"] == "INACCESSIBLE"
    assert review["current_status"] == "ACCESSIBLE_PENDING_DETERMINISTIC_RECONCILIATION"
    assert review["historical_record_mutated"] is False
    assert review["observed_source_archive"]["sha256"] == EXPECTED_ARCHIVE_SHA256

    observed = {item["filename"]: item for item in review["observed_products"]}
    assert observed["UNESCO_NeuroAI_All_Data_Combined_v2.2.0.xlsx"]["sha256"] == EXPECTED_XLSX_SHA256
    assert (
        observed["UNESCO_NeuroAI_All_Reports_Findings_and_Conclusions_Combined_v2.2.0.docx"]["sha256"]
        == EXPECTED_DOCX_SHA256
    )
    assert observed["UNESCO_NeuroAI_All_Data_Combined_v2.2.0.xlsx"]["observed_sheet_count"] == 48
    assert (
        observed["UNESCO_NeuroAI_All_Reports_Findings_and_Conclusions_Combined_v2.2.0.docx"][
            "observed_word_table_count"
        ]
        == 349
    )


def test_amb003_stage1_records_scope_difference_without_closing_ambiguity() -> None:
    stage1 = _load(MIGRATION / "amb003_reconciliation_stage1_2026-08-25.json")

    assert stage1["status"] == "STRUCTURAL_RECONCILIATION_PASS_CONTENT_RECONCILIATION_PENDING"
    assert stage1["workbook"]["sha256"] == EXPECTED_XLSX_SHA256
    assert stage1["workbook"]["sheet_count"] == 48
    assert stage1["workbook"]["file_manifest_data_rows"] == 1436
    assert stage1["outer_archive"]["sha256"] == EXPECTED_ARCHIVE_SHA256
    assert stage1["outer_archive"]["file_entry_count"] == 1344

    identity = stage1["byte_identity_reconciliation"]
    assert identity["historical_manifest_rows"] == 1436
    assert identity["historical_manifest_rows_with_sha_present_in_outer_archive"] == 1355
    assert identity["historical_manifest_rows_without_sha_present_in_outer_archive"] == 81
    assert identity["outer_archive_files"] == 1344
    assert identity["outer_archive_files_with_sha_present_in_historical_manifest"] == 1339
    assert identity["outer_archive_files_without_sha_present_in_historical_manifest"] == 5

    assert stage1["historical_records_mutated"] is False
    assert len(stage1["remaining_before_amb003_resolution"]) >= 4
    assert "not the S2 canonical machine-readable master" in stage1["workbook"]["authority_interpretation"]


def test_graph_layer_nomenclature_does_not_reclassify_store_authority() -> None:
    adr = (ROOT / "docs" / "adr" / "0014-programme-store-and-graph-layer-boundaries.md").read_text(encoding="utf-8")

    for store in ("S1", "S2", "S3", "S4", "S5"):
        assert store in adr
    for layer in ("L0", "L1", "L2", "L3", "L4", "L5"):
        assert layer in adr
    assert "historical graph S0 -> L0" in adr
    assert "historical graph S5 -> L5" in adr
    assert "Historical vNext documents" in adr
    assert "are not edited" in adr
