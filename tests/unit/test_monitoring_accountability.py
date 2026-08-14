from __future__ import annotations

import copy

import pytest

from neuroai_workbench.monitoring_accountability import (
    BOUNDARY,
    evaluate_monitoring_accountability,
    verify_monitoring_accountability_report,
)


def _source(source_id: str) -> dict[str, str]:
    return {"source_id": source_id, "url": f"https://example.org/{source_id}"}


def _monitor(source_id: str) -> dict[str, str]:
    return {
        "monitor_id": f"MON-{source_id}",
        "source_id": source_id,
        "url": f"https://example.org/{source_id}",
        "cadence": "MONTHLY",
    }


def _explicit(source_id: str, state: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "accountability_state": state,
        "rationale": f"Explicit test rationale for {source_id}",
        "supporting_record_id": f"ELIG-{source_id}",
        "supporting_sha256": "a" * 64,
    }


def test_248_source_namespace_reconciles_224_monitored_plus_explicit_nonmonitor_states() -> None:
    effective = [_source(f"SRC-{index:04d}") for index in range(1, 249)]
    monitors = [_monitor(f"SRC-{index:04d}") for index in range(1, 225)]
    non_monitor = [
        *[_explicit(f"SRC-{index:04d}", "MANUAL_ONLY") for index in range(225, 233)],
        *[_explicit(f"SRC-{index:04d}", "EXEMPT_WITH_RATIONALE") for index in range(233, 249)],
    ]

    report = evaluate_monitoring_accountability(
        effective_sources=effective,
        monitor_registry=monitors,
        non_monitor_accountability=non_monitor,
    )

    assert report["complete"] is True
    assert report["coverage_fraction"] == 1.0
    assert report["counts"]["effective_sources"] == 248
    assert report["counts"]["MONITORED"] == 224
    assert report["counts"]["MANUAL_ONLY"] == 8
    assert report["counts"]["EXEMPT_WITH_RATIONALE"] == 16
    assert report["counts"]["GAP"] == 0
    assert report["counts"]["AMBIGUOUS"] == 0
    assert report["gap_source_ids"] == []
    assert report["errors"] == []
    assert report["boundary"] == BOUNDARY
    assert len(report["report_sha256"]) == 64


def test_missing_nonmonitor_disposition_remains_visible_gap() -> None:
    report = evaluate_monitoring_accountability(
        effective_sources=[_source("SRC-1"), _source("SRC-2")],
        monitor_registry=[_monitor("SRC-1")],
    )
    assert report["complete"] is False
    assert report["coverage_fraction"] == 0.5
    assert report["gap_source_ids"] == ["SRC-2"]
    assert "monitoring accountability gap: SRC-2" in report["errors"]


def test_monitor_and_nonmonitor_overlap_is_ambiguous_not_counted_as_covered() -> None:
    report = evaluate_monitoring_accountability(
        effective_sources=[_source("SRC-1")],
        monitor_registry=[_monitor("SRC-1")],
        non_monitor_accountability=[_explicit("SRC-1", "MANUAL_ONLY")],
    )
    assert report["complete"] is False
    assert report["coverage_fraction"] == 0.0
    assert report["ambiguous_source_ids"] == ["SRC-1"]
    assert report["counts"]["AMBIGUOUS"] == 1


def test_orphan_monitor_and_orphan_accountability_fail_closed() -> None:
    report = evaluate_monitoring_accountability(
        effective_sources=[_source("SRC-1")],
        monitor_registry=[_monitor("SRC-1"), _monitor("SRC-ORPHAN")],
        non_monitor_accountability=[_explicit("SRC-EXEMPT-ORPHAN", "EXEMPT_WITH_RATIONALE")],
    )
    assert report["complete"] is False
    assert report["orphan_monitor_source_ids"] == ["SRC-ORPHAN"]
    assert report["orphan_accountability_source_ids"] == ["SRC-EXEMPT-ORPHAN"]


def test_duplicate_effective_monitor_and_nonmonitor_records_are_reported() -> None:
    report = evaluate_monitoring_accountability(
        effective_sources=[_source("SRC-1"), _source("SRC-1")],
        monitor_registry=[_monitor("SRC-1"), _monitor("SRC-1")],
        non_monitor_accountability=[
            _explicit("SRC-1", "MANUAL_ONLY"),
            _explicit("SRC-1", "MANUAL_ONLY"),
        ],
    )
    assert report["complete"] is False
    assert report["duplicate_effective_source_ids"] == ["SRC-1"]
    assert report["duplicate_monitor_source_ids"] == ["SRC-1"]
    assert report["duplicate_non_monitor_source_ids"] == ["SRC-1"]


def test_nonmonitor_records_require_supported_state_and_rationale_and_valid_digest() -> None:
    with pytest.raises(ValueError, match="unsupported accountability_state"):
        evaluate_monitoring_accountability(
            effective_sources=["SRC-1"],
            monitor_registry=[],
            non_monitor_accountability=[{"source_id": "SRC-1", "accountability_state": "GAP", "rationale": "x"}],
        )
    with pytest.raises(ValueError, match="requires rationale"):
        evaluate_monitoring_accountability(
            effective_sources=["SRC-1"],
            monitor_registry=[],
            non_monitor_accountability=[{"source_id": "SRC-1", "accountability_state": "MANUAL_ONLY"}],
        )
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        evaluate_monitoring_accountability(
            effective_sources=["SRC-1"],
            monitor_registry=[],
            non_monitor_accountability=[
                {
                    "source_id": "SRC-1",
                    "accountability_state": "MANUAL_ONLY",
                    "rationale": "controlled manual handling",
                    "supporting_sha256": "BAD",
                }
            ],
        )


def test_source_record_validation_rejects_missing_or_invalid_source_id_shapes() -> None:
    with pytest.raises(ValueError, match="missing source_id"):
        evaluate_monitoring_accountability(effective_sources=[{}], monitor_registry=[])
    with pytest.raises(ValueError, match="source ID string or object"):
        evaluate_monitoring_accountability(effective_sources=[123], monitor_registry=[])
    with pytest.raises(ValueError, match="must be an object"):
        evaluate_monitoring_accountability(
            effective_sources=["SRC-1"],
            monitor_registry=[],
            non_monitor_accountability=["SRC-1"],
        )


def test_report_verification_detects_tampering_and_input_substitution() -> None:
    effective = [_source("SRC-1"), _source("SRC-2")]
    monitors = [_monitor("SRC-1")]
    explicit = [_explicit("SRC-2", "MANUAL_ONLY")]
    report = evaluate_monitoring_accountability(
        effective_sources=effective,
        monitor_registry=monitors,
        non_monitor_accountability=explicit,
    )
    verification = verify_monitoring_accountability_report(
        report,
        effective_sources=effective,
        monitor_registry=monitors,
        non_monitor_accountability=explicit,
    )
    assert verification["valid"] is True
    assert verification["complete"] is True

    tampered = copy.deepcopy(report)
    tampered["counts"]["MONITORED"] = 999
    verification = verify_monitoring_accountability_report(
        tampered,
        effective_sources=effective,
        monitor_registry=monitors,
        non_monitor_accountability=explicit,
    )
    assert verification["valid"] is False
    assert "recorded report hash mismatch" in verification["errors"]

    verification = verify_monitoring_accountability_report(
        report,
        effective_sources=[*effective, _source("SRC-3")],
        monitor_registry=monitors,
        non_monitor_accountability=explicit,
    )
    assert verification["valid"] is False
    assert "report does not match recomputed accountability projection" in verification["errors"]


def test_empty_effective_namespace_is_vacuously_complete_without_orphans() -> None:
    report = evaluate_monitoring_accountability(
        effective_sources=[],
        monitor_registry=[],
        non_monitor_accountability=[],
    )
    assert report["complete"] is True
    assert report["coverage_fraction"] == 1.0
    assert report["counts"]["effective_sources"] == 0
