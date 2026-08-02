from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.monitoring import (
    adjudicate_change_candidate,
    build_refresh_candidate,
    build_source_health_report,
    compare_snapshots,
    create_change_candidate,
    initialize_monitoring,
    load_source_registry,
    monitoring_status,
    normalize_source_registry,
    plan_monitoring_run,
    record_snapshot,
    validate_source_registry,
)
from neuroai_workbench.util import atomic_write_json, load_json

SAMPLE_REGISTRY = Path(__file__).parents[2] / "examples" / "operations" / "SOURCE_MONITOR_REGISTRY_SAMPLE.json"


def small_registry() -> list[dict[str, object]]:
    boundary = "Official pages establish representations only; human adjudication controls all substantive effects."
    return [
        {
            "monitor_id": "MON-SRC-0001",
            "source_id": "SRC-0001",
            "url": "https://example.org/regulatory",
            "publisher": "Example regulator",
            "source_class": "REGULATORY_RECORD",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2026-07-01",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": boundary,
            "network_access_required": True,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "RETRIEVE_AND_COMPARE",
        },
        {
            "monitor_id": "MON-SRC-0002",
            "source_id": "SRC-0002",
            "url": "https://example.org/company",
            "publisher": "Example company",
            "source_class": "OFFICIAL_COMPANY_PAGE",
            "cadence": "QUARTERLY",
            "last_successful_retrieval": "2026-07-29",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": boundary,
            "network_access_required": True,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "RETRIEVE_AND_COMPARE",
        },
    ]


def write_registry(tmp_path: Path, records: list[dict[str, object]] | None = None) -> Path:
    path = tmp_path / "registry.json"
    atomic_write_json(path, records or small_registry())
    return path


def initialize(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, write_registry(tmp_path), actor="tester")
    return workspace


def test_sample_registry_validates_and_surfaces_local_reference() -> None:
    registry = load_source_registry(SAMPLE_REGISTRY)
    result = validate_source_registry(registry)
    assert result["valid"] is True
    assert result["counts"]["sources"] == 3
    assert any(item["code"] == "NON_PORTABLE_LOCAL_REFERENCE" for item in result["warnings"])


def test_legacy_list_normalizes_without_mutating_records() -> None:
    records = small_registry()
    normalized = normalize_source_registry(records)
    assert normalized["metadata"]["source_release"] == "v1.5"
    assert normalized["sources"] == records
    assert normalized["metadata"]["record_count"] == 2


def test_registry_duplicate_and_unsafe_url_fail() -> None:
    records = small_registry()
    records[1]["source_id"] = "SRC-0001"
    records[1]["url"] = "file:///etc/passwd"
    result = validate_source_registry(records)
    assert result["valid"] is False
    codes = {item["code"] for item in result["errors"]}
    assert "DUPLICATE_SOURCE_ID" in codes
    assert "INVALID_PUBLIC_URL" in codes


def test_initialize_is_idempotent_for_identical_registry(tmp_path: Path) -> None:
    registry = write_registry(tmp_path)
    workspace = tmp_path / "workspace"
    first = initialize_monitoring(workspace, registry, actor="tester")
    second = initialize_monitoring(workspace, registry, actor="tester")
    assert first["registry_sha256"] == second["registry_sha256"]
    state = load_json(workspace / "observatory" / "monitoring" / "state.json")
    assert state["registry_sha256"] == first["registry_sha256"]


def test_initialize_refuses_registry_replacement(tmp_path: Path) -> None:
    registry = write_registry(tmp_path)
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, registry)
    changed = small_registry()
    changed[0]["publisher"] = "Different publisher"
    atomic_write_json(registry, changed)
    with pytest.raises(ValueError, match="different canonical content"):
        initialize_monitoring(workspace, registry)


def test_plan_uses_cadence_and_baseline_date(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02")
    assert plan["counts"] == {"due": 1, "manual": 0, "not_due": 1}
    assert plan["due"][0]["source_id"] == "SRC-0001"
    assert plan["due"][0]["overdue_days"] == 25


def test_plan_routes_controlled_local_and_no_network_to_manual(tmp_path: Path) -> None:
    records = small_registry()
    records.append(
        {
            "monitor_id": "MON-SRC-0003",
            "source_id": "SRC-0003",
            "url": "controlled-inputs/local.json",
            "publisher": "Controlled project input",
            "source_class": "CONTROLLED_LOCAL_INPUT",
            "cadence": "QUARTERLY",
            "last_successful_retrieval": "2025-01-01",
            "baseline_evidence_state": "PUBLIC_RESEARCH_ARTIFACT",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": "A controlled local input is not independent appraisal.",
            "network_access_required": True,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "MIGRATE_TO_CONTENT_ADDRESSED_OBJECT",
        }
    )
    records.append(
        {
            "monitor_id": "MON-SRC-0004",
            "source_id": "SRC-0004",
            "url": "https://example.org/offline-only",
            "publisher": "Offline-only publisher",
            "source_class": "OFFICIAL_COMPANY_PAGE",
            "cadence": "WEEKLY",
            "last_successful_retrieval": "2025-01-01",
            "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
            "baseline_verification_state": "CURRENT_VERIFIED",
            "baseline_claim_boundary": "Offline-only sources require manual ingest.",
            "network_access_required": False,
            "current_status": "BASELINE_REGISTERED",
            "next_action": "MANUAL_RETRIEVE",
        }
    )
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, write_registry(tmp_path, records), actor="tester")
    plan = plan_monitoring_run(workspace, as_of="2026-10-28")
    due_ids = {item["source_id"] for item in plan["due"]}
    manual_by_id = {item["source_id"]: item for item in plan["manual"]}
    assert "SRC-0003" not in due_ids
    assert "SRC-0004" not in due_ids
    assert manual_by_id["SRC-0003"]["manual_reason"] == "CONTROLLED_LOCAL_OR_NO_NETWORK"
    assert manual_by_id["SRC-0004"]["manual_reason"] == "CONTROLLED_LOCAL_OR_NO_NETWORK"


def test_sample_registry_local_never_due(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, SAMPLE_REGISTRY, actor="tester")
    plan = plan_monitoring_run(workspace, as_of="2026-10-28")
    due_ids = {item["source_id"] for item in plan["due"]}
    manual_ids = {item["source_id"] for item in plan["manual"]}
    assert "SRC-SAMPLE-003" not in due_ids
    assert "SRC-SAMPLE-003" in manual_ids
    assert all(
        item.get("manual_reason") == "CONTROLLED_LOCAL_OR_NO_NETWORK"
        for item in plan["manual"]
        if item["source_id"] == "SRC-SAMPLE-003"
    )


def test_source_health_reconciles_plan_without_silent_drop(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    plan = plan_monitoring_run(workspace, as_of="2026-08-02")
    health = build_source_health_report(workspace, as_of="2026-08-02", plan=plan)
    assert health["counts"]["sources"] == 2
    assert health["counts"]["silent_drop"] == 0
    assert health["counts"]["due"] == plan["counts"]["due"]
    assert {item["source_id"] for item in health["sources"]} == {"SRC-0001", "SRC-0002"}
    assert health["registry_sha256"] == monitoring_status(workspace)["registry_sha256"]


def test_plan_rejects_unknown_source(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    with pytest.raises(ValueError, match="Unknown source IDs"):
        plan_monitoring_run(workspace, as_of="2026-08-02", source_ids=["SRC-MISSING"])


def test_snapshots_are_content_addressed_and_verified(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    first = record_snapshot(
        workspace,
        "SRC-0001",
        b"line one\nline two\n",
        media_type="text/plain",
        retrieved_at="2026-08-02T01:00:00Z",
        actor="collector",
    )
    same = record_snapshot(
        workspace,
        "SRC-0001",
        b"line one\nline two\n",
        media_type="text/plain",
        retrieved_at="2026-08-02T01:00:00Z",
        actor="collector",
    )
    assert first["snapshot_id"] == same["snapshot_id"]
    assert first["sha256"] == same["sha256"]
    assert (workspace / first["stored_path"]).is_file()


def test_snapshot_rejects_empty_bytes_and_unknown_source(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    with pytest.raises(ValueError, match="zero bytes"):
        record_snapshot(workspace, "SRC-0001", b"")
    with pytest.raises(ValueError, match="Unknown source ID"):
        record_snapshot(workspace, "SRC-9999", b"content")


def test_snapshot_diff_classifications(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    first = record_snapshot(
        workspace,
        "SRC-0001",
        b"alpha\nbeta\n",
        media_type="text/plain",
        retrieved_at="2026-08-02T01:00:00Z",
    )
    formatting = record_snapshot(
        workspace,
        "SRC-0001",
        b"alpha  \r\nbeta\r\n",
        media_type="text/plain",
        retrieved_at="2026-08-02T02:00:00Z",
    )
    changed = record_snapshot(
        workspace,
        "SRC-0001",
        b"alpha\ngamma\n",
        media_type="text/plain",
        retrieved_at="2026-08-02T03:00:00Z",
    )
    assert (
        compare_snapshots(workspace, "SRC-0001", first["snapshot_id"], first["snapshot_id"])["classification"]
        == "NO_CHANGE"
    )
    assert (
        compare_snapshots(workspace, "SRC-0001", first["snapshot_id"], formatting["snapshot_id"])["classification"]
        == "NON_MATERIAL_REPRESENTATION_CHANGE"
    )
    assert (
        compare_snapshots(workspace, "SRC-0001", formatting["snapshot_id"], changed["snapshot_id"])["classification"]
        == "CONTENT_CHANGED_REQUIRES_REVIEW"
    )


def test_candidate_requires_material_change_and_never_mutates_observatory(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    changed = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    candidate = create_change_candidate(
        workspace,
        "SRC-0001",
        changed["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
        actor="detector",
    )
    assert candidate["status"] == "PENDING_HUMAN_ADJUDICATION"
    assert candidate["automatic_mutation_performed"] is False
    with pytest.raises(ValueError, match="not required"):
        create_change_candidate(
            workspace,
            "SRC-0001",
            first["snapshot_id"],
            previous_snapshot_id=first["snapshot_id"],
        )


def test_accepted_candidate_requires_explicit_human_classification(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    changed = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    candidate = create_change_candidate(
        workspace,
        "SRC-0001",
        changed["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
    )
    with pytest.raises(ValueError, match="Accepted candidates require"):
        adjudicate_change_candidate(
            workspace,
            candidate["candidate_id"],
            "ACCEPT",
            rationale="The source changed.",
        )
    adjudication = adjudicate_change_candidate(
        workspace,
        candidate["candidate_id"],
        "ACCEPT",
        rationale="A regulatory record changed and requires exact-system review.",
        change_class="REGULATORY_OR_MARKET_EVENT",
        materiality="MATERIAL",
        reopening_effect="REVIEW_REQUIRED",
        actor="reviewer",
    )
    assert adjudication["canonical_observatory_mutation_performed"] is False
    with pytest.raises(ValueError, match="immutable"):
        adjudicate_change_candidate(
            workspace,
            candidate["candidate_id"],
            "REJECT",
            rationale="Second decision forbidden.",
        )


def test_refresh_package_is_noncanonical_and_contains_reopening_queue(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    changed = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    candidate = create_change_candidate(
        workspace,
        "SRC-0001",
        changed["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
    )
    adjudicate_change_candidate(
        workspace,
        candidate["candidate_id"],
        "ACCEPT",
        rationale="Material regulatory change.",
        change_class="REGULATORY_OR_MARKET_EVENT",
        materiality="MATERIAL",
        reopening_effect="PARTIAL_REASSESSMENT_REQUIRED",
    )
    result = build_refresh_candidate(workspace, "refresh-2026-08", "2026-08-02", actor="release-manager")
    assert result["package"]["metadata"]["status"] == "REVIEW_CANDIDATE_NOT_CANONICAL"
    assert result["package"]["counts"]["accepted"] == 1
    assert result["package"]["counts"]["reopening_queue"] == 1
    assert result["manifest"]["refresh_candidate_sha256"]
    with pytest.raises(ValueError, match="overwrite"):
        build_refresh_candidate(workspace, "refresh-2026-08", "2026-08-02")


def test_monitoring_status_summarizes_operational_state(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    status = monitoring_status(workspace)
    assert status["source_count"] == 2
    assert status["sources_checked"] == 1
    assert status["pending_candidate_count"] == 0


def test_repeated_unchanged_capture_is_distinct_and_content_deduplicated(tmp_path: Path) -> None:
    workspace = initialize(tmp_path)
    first = record_snapshot(
        workspace,
        "SRC-0001",
        b"same-bytes",
        media_type="text/plain",
        retrieved_at="2026-08-02T01:00:00Z",
    )
    later = record_snapshot(
        workspace,
        "SRC-0001",
        b"same-bytes",
        media_type="text/plain",
        retrieved_at="2026-08-02T02:00:00Z",
    )
    assert first["snapshot_id"] != later["snapshot_id"]
    assert first["sha256"] == later["sha256"]
    assert (
        compare_snapshots(
            workspace,
            "SRC-0001",
            first["snapshot_id"],
            later["snapshot_id"],
        )["classification"]
        == "NO_CHANGE"
    )
    with pytest.raises(ValueError, match="different metadata"):
        record_snapshot(
            workspace,
            "SRC-0001",
            b"same-bytes",
            media_type="application/octet-stream",
            retrieved_at="2026-08-02T01:00:00Z",
        )


def test_snapshot_size_url_timezone_and_filename_controls(tmp_path: Path) -> None:
    from neuroai_workbench import monitoring

    workspace = initialize(tmp_path)
    with pytest.raises(ValueError, match="ingestion limit"):
        record_snapshot(workspace, "SRC-0001", b"x" * (monitoring.MAX_SNAPSHOT_BYTES + 1))
    with pytest.raises(ValueError, match="explicit timezone"):
        record_snapshot(workspace, "SRC-0001", b"content", retrieved_at="2026-08-02T01:00:00")
    with pytest.raises(ValueError, match="retrieval_url is invalid"):
        record_snapshot(
            workspace,
            "SRC-0001",
            b"content",
            retrieval_url="http://127.0.0.1/private",
        )
    with pytest.raises(ValueError, match="basename"):
        record_snapshot(
            workspace,
            "SRC-0001",
            b"content",
            original_filename="/tmp/private.txt",
        )

    records = small_registry()
    records[0]["url"] = "http://127.0.0.1/private"
    result = validate_source_registry(records)
    assert any(item["code"] == "INVALID_PUBLIC_URL" for item in result["errors"])
