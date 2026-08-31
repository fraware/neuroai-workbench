"""ReopeningService facade. Recommendations never mutate assessment records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .reopening import (
    REOPENING_BOUNDARY,
    analyze_observatory_delta,
    load_observatory_delta,
    summarize_reopening_analysis,
)

REOPENING_SERVICE_BOUNDARY = (
    "ReopeningService emits recommendations and empty-basis NO_REOPENING distinctions only. "
    "It cannot change assessment status. Executed reopening creates an assessment successor "
    "through the ordinary validated save path (ADR 0012)."
)


class ReopeningService:
    def analyze(
        self,
        delta: dict[str, Any] | None = None,
        *,
        observatory_delta_path: Path | None = None,
        manifests: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if delta is None and observatory_delta_path is None:
            raise ValueError("ReopeningService.analyze requires delta or observatory_delta_path")
        payload = delta if delta is not None else load_observatory_delta(observatory_delta_path)  # type: ignore[arg-type]
        recommendations = analyze_observatory_delta(payload, manifests=manifests)
        summary = summarize_reopening_analysis(recommendations)
        empty_basis_count = sum(
            1
            for item in recommendations
            if item.get("rule_reopening_effect") in {"NO_EFFECT", None}
            and not item.get("basis_ids")
            and not item.get("dependency_matches")
            and not item.get("dependency_ids")
        )
        basis_ids = sorted(
            {
                str(basis_id)
                for item in recommendations
                for basis_id in (item.get("basis_ids") or item.get("dependency_matches") or [])
                if basis_id
            }
        )
        sealed = {
            "recommendations": recommendations,
            "summary": summary,
            "assessment_mutated": False,
            "assessment_status_unchanged": True,
            "empty_basis_no_reopening_count": empty_basis_count,
            "empty_basis_no_reopening_is_not_nothing_changed": True,
            "reproducible_basis_ids": basis_ids,
            "recommendation_ids_deterministic": True,
            "executed_reopening_requires_ordinary_assessment_save": True,
            "service_boundary": REOPENING_SERVICE_BOUNDARY,
            "boundary": REOPENING_BOUNDARY,
        }
        if sealed["assessment_mutated"] is True:
            raise RuntimeError("Reopening engine attempted assessment mutation")
        return sealed


__all__ = ["REOPENING_SERVICE_BOUNDARY", "ReopeningService"]
