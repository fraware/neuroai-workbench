"""MonitoringService facade over plan/compare/classify and onboarding lifecycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .monitoring import compare_snapshots, plan_monitoring_run
from .monitoring_lifecycle import (
    ONBOARDING_BOUNDARY,
    advance_onboarding,
    assert_no_monitor_from_source_acceptance,
    initial_onboarding_record,
    record_source_disappearance,
)

MONITORING_SERVICE_BOUNDARY = (
    "MonitoringService plans due work and classifies snapshot comparisons. "
    "It does not mutate assessments, authorize releases, or create monitors from source acceptance alone."
)

CHANGE_CLASSES = frozenset(
    {
        "NO_CHANGE",
        "NON_MATERIAL_REPRESENTATION_CHANGE",
        "CONTENT_CHANGED_REQUIRES_REVIEW",
        "SOURCE_INACCESSIBLE",
        "COMPARISON_SCOPE_INSUFFICIENT",
    }
)


class MonitoringService:
    def evaluate_due(self, workspace: Path, *, as_of: str | None = None) -> dict[str, Any]:
        plan = plan_monitoring_run(workspace, as_of=as_of) if as_of else plan_monitoring_run(workspace)
        return {**plan, "service_boundary": MONITORING_SERVICE_BOUNDARY}

    def compare(
        self,
        workspace: Path,
        source_id: str,
        older_snapshot_id: str,
        newer_snapshot_id: str,
        *,
        comparison_scope: str = "bytes_digest_and_normalized_text",
    ) -> dict[str, Any]:
        raw = compare_snapshots(workspace, source_id, older_snapshot_id, newer_snapshot_id)
        return self.classify(raw, comparison_scope=comparison_scope)

    def classify(
        self,
        comparison: dict[str, Any],
        *,
        comparison_scope: str,
    ) -> dict[str, Any]:
        classification = str(comparison.get("classification"))
        if classification not in CHANGE_CLASSES and classification != "MANUAL_CANDIDATE":
            # Preserve unknown upstream classes fail-closed as review-required.
            classification = "CONTENT_CHANGED_REQUIRES_REVIEW"
        typed = {
            **comparison,
            "comparison_scope": comparison_scope,
            "typed_change_class": classification,
            "no_change_explicit": classification == "NO_CHANGE",
            "empty_basis_is_not_no_change": True,
            "high_materiality_review_required": classification == "CONTENT_CHANGED_REQUIRES_REVIEW",
            "service_boundary": MONITORING_SERVICE_BOUNDARY,
        }
        if classification == "NO_CHANGE" and not comparison_scope.strip():
            typed["typed_change_class"] = "COMPARISON_SCOPE_INSUFFICIENT"
            typed["no_change_explicit"] = False
            typed["candidate_required"] = True
        return typed

    def open_onboarding(self, *, source_candidate_id: str, actor: str = "local-user") -> dict[str, Any]:
        return initial_onboarding_record(source_candidate_id=source_candidate_id, actor=actor)

    def advance_onboarding(
        self,
        record: dict[str, Any],
        *,
        next_stage: str,
        actor: str,
        note: str,
    ) -> dict[str, Any]:
        updated = advance_onboarding(record, next_stage=next_stage, actor=actor, note=note)
        assert_no_monitor_from_source_acceptance(updated)
        return updated

    def record_disappearance(self, record: dict[str, Any], *, actor: str, note: str) -> dict[str, Any]:
        return record_source_disappearance(record, actor=actor, note=note)


__all__ = [
    "CHANGE_CLASSES",
    "MONITORING_SERVICE_BOUNDARY",
    "ONBOARDING_BOUNDARY",
    "MonitoringService",
]
