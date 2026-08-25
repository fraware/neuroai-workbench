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


def test_amb003_stage2_internal_parity_is_bounded_and_noncanonical() -> None:
    stage2 = _load(MIGRATION / "amb003_reconciliation_stage2_2026-08-25.json")

    assert stage2["status"] == "INTERNAL_CROSS_VIEW_PARITY_PASS_INDEPENDENT_CANONICAL_RECONCILIATION_PENDING"
    assert stage2["method"]["workbook_sha256"] == EXPECTED_XLSX_SHA256
    assert stage2["predecessor_reconciliation_id"] == "AMB-003-STAGE1-20260825"

    summary = stage2["scope_summary"]
    assert summary["direct_view_sheet_count"] == 18
    assert summary["direct_source_dataset_count"] == 18
    assert summary["direct_records_compared"] == 554
    assert summary["direct_field_values_compared"] == 7144
    assert summary["assessment_view_sheet_count"] == 6
    assert summary["assessment_source_dataset_count"] == 22
    assert summary["assessment_records_compared"] == 525
    assert summary["assessment_field_values_compared"] == 7375
    assert summary["total_records_compared"] == 1079
    assert summary["total_field_values_compared"] == 14519
    assert summary["total_value_mismatches"] == 0
    assert summary["total_missing_keys"] == 0
    assert summary["total_extra_keys"] == 0

    direct = stage2["direct_view_results"]
    assessment = stage2["assessment_view_results"]
    assert len(direct) == 18
    assert len(assessment) == 22
    assert all(row[-1] == 0 for row in direct)
    assert all(row[-1] == 0 for row in assessment)
    assert all(len(row[2]) == 64 for row in direct)
    assert all(len(row[3]) == 64 for row in assessment)

    assert stage2["historical_records_mutated"] is False
    assert len(stage2["remaining_before_amb003_resolution"]) >= 5
    assert "does not establish original-archive byte parity" in stage2["authority_boundary"]
    assert "does not independently verify" in stage2["method"]["authority_rule"]


def test_amb003_stage3_records_report_parity_and_blank_kernel_defect() -> None:
    stage3 = _load(MIGRATION / "amb003_reconciliation_stage3_2026-08-25.json")

    assert (
        stage3["status"]
        == "COMPANION_REPORT_TABULAR_PARITY_WITH_ONE_GENERATED_TABLE_DEFECT_INDEPENDENT_CANONICAL_RECONCILIATION_PENDING"
    )
    assert stage3["predecessor_reconciliation_id"] == "AMB-003-STAGE2-20260825"
    assert stage3["artifacts"]["workbook"]["sha256"] == EXPECTED_XLSX_SHA256
    assert stage3["artifacts"]["report"]["sha256"] == EXPECTED_DOCX_SHA256

    summary = stage3["scope_summary"]
    assert summary["appendices_examined"] == 23
    assert summary["appendices_with_exact_bounded_parity"] == 22
    assert summary["appendices_with_detected_representation_defect"] == 1
    assert summary["exact_parity_rows_compared"] == 1376
    assert summary["exact_parity_field_values_compared"] == 11617
    assert summary["missing_stable_keys_in_exact_parity_appendices"] == 0
    assert summary["extra_stable_keys_in_exact_parity_appendices"] == 0
    assert summary["value_mismatches_in_exact_parity_appendices"] == 0

    appendices = {item["appendix"]: item for item in stage3["appendix_results"]}
    assert set(appendices) == {chr(code) for code in range(ord("A"), ord("W") + 1)}
    assert all(item["result"] == "EXACT_BOUNDED_PARITY" for key, item in appendices.items() if key != "K")

    kernel = stage3["kernel_appendix_defect"]
    assert appendices["K"]["result"] == "GENERATED_TABLE_DATA_CELLS_EMPTY"
    assert kernel["report_data_rows"] == 78
    assert kernel["report_data_cells"] == 468
    assert kernel["report_nonempty_data_cells"] == 0
    assert kernel["ooxml_text_nodes_in_table"] == 6
    assert kernel["ooxml_text_nodes_are_headers_only"] is True
    assert kernel["workbook_data_rows"] == 78
    assert kernel["workbook_nonempty_selected_cells"] == 468
    assert kernel["classification"] == "S4_GENERATED_REPORT_REPRESENTATION_DEFECT"
    assert kernel["canonical_corruption_established"] is False

    discrepancy = stage3["authority_label_discrepancy"]
    assert "canonical row-level analytical representation" in discrepancy["observed_historical_claim"]
    assert "S4 generated views" in discrepancy["successor_architecture_interpretation"]
    assert stage3["historical_records_mutated"] is False
    assert "does not establish independent canonical correctness" in stage3["authority_boundary"]


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
