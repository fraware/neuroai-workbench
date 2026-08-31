"""Assessment validation cohort tooling hooks (M4).

Supports freezing protocol parameters and recording disagreement metrics without
claiming global scientific validation or optimizing reviewers into agreement.

This package is intentionally named ``assessment_validation`` so it does not
shadow the mechanical ``neuroai_workbench.validation`` assessment validator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..util import atomic_write_json, canonical_json_bytes, load_json, sha256_bytes, utc_now

VALIDATION_BOUNDARY = (
    "Validation cohort tooling freezes study parameters and records mechanical disagreement "
    "metrics. It does not establish instrument validity, clinical effectiveness, conformance, "
    "or global scientific validation. Blinded comparison must not optimize reviewers into agreement."
)

REQUIRED_FREEZE_FIELDS = (
    "protocol_id",
    "instrument_version",
    "case_battery_id",
    "reviewer_assignment_id",
    "evidence_cutoff",
    "study_arm",
)

COHORT_SIZE_TARGET_MIN = 20
COHORT_SIZE_TARGET_MAX = 30
PROTECTED_EXPORT_FIELDS = frozenset(
    {
        "participant_name",
        "reviewer_email",
        "neural_recording",
        "protected_note",
        "reviewer_identity_proof",
    }
)


def freeze_validation_cohort(
    *,
    protocol_id: str,
    instrument_version: str,
    case_battery_id: str,
    reviewer_assignment_id: str,
    evidence_cutoff: str,
    study_arm: str,
    case_ids: list[str],
    actor: str = "local-user",
    allow_undersized_for_tooling: bool = True,
) -> dict[str, Any]:
    if not case_ids:
        raise ValueError("Validation cohort requires at least one case_id")
    unique_cases = list(dict.fromkeys(case_ids))
    record = {
        "protocol_id": protocol_id,
        "instrument_version": instrument_version,
        "case_battery_id": case_battery_id,
        "reviewer_assignment_id": reviewer_assignment_id,
        "evidence_cutoff": evidence_cutoff,
        "study_arm": study_arm,
        "case_ids": unique_cases,
        "case_count": len(unique_cases),
        "cohort_size_target": {"min": COHORT_SIZE_TARGET_MIN, "max": COHORT_SIZE_TARGET_MAX},
        "cohort_size_in_target_band": COHORT_SIZE_TARGET_MIN <= len(unique_cases) <= COHORT_SIZE_TARGET_MAX,
        "frozen_at": utc_now(),
        "frozen_by": actor,
        "outcome_collection_authorized": False,
        "global_validation_claim": False,
        "empirical_outcomes_present": False,
        "boundary": VALIDATION_BOUNDARY,
    }
    for field in REQUIRED_FREEZE_FIELDS:
        if not str(record.get(field) or "").strip():
            raise ValueError(f"Validation freeze requires {field}")
    if not record["cohort_size_in_target_band"] and not allow_undersized_for_tooling:
        raise ValueError(
            f"Cohort size {len(unique_cases)} is outside the {COHORT_SIZE_TARGET_MIN}-{COHORT_SIZE_TARGET_MAX} target band"
        )
    record["cohort_sha256"] = sha256_bytes(
        canonical_json_bytes({k: v for k, v in record.items() if k != "cohort_sha256"})
    )
    return record


def write_cohort_manifest(workspace: Path, cohort: dict[str, Any]) -> Path:
    """Persist an immutable cohort freeze manifest under an isolated validation workspace."""
    root = workspace / "assessment_validation" / "cohorts"
    root.mkdir(parents=True, exist_ok=True)
    cohort_id = str(cohort.get("protocol_id") or "cohort")
    digest = str(cohort.get("cohort_sha256") or sha256_bytes(canonical_json_bytes(cohort)))[:16]
    path = root / f"{cohort_id}-{digest}.manifest.json"
    if path.exists():
        existing = load_json(path)
        if existing != cohort:
            raise ValueError("Refusing to overwrite a divergent cohort manifest")
        return path
    atomic_write_json(path, cohort)
    return path


def isolate_reviewer_workspace(workspace: Path, *, reviewer_slot: str, cohort_sha256: str) -> Path:
    """Create an isolated reviewer workspace path. Does not copy protected evidence bytes."""
    if not reviewer_slot.strip() or "/" in reviewer_slot or "\\" in reviewer_slot or ".." in reviewer_slot:
        raise ValueError("reviewer_slot must be a simple non-escaping identifier")
    path = workspace / "assessment_validation" / "reviewers" / reviewer_slot
    path.mkdir(parents=True, exist_ok=True)
    marker = {
        "reviewer_slot": reviewer_slot,
        "cohort_sha256": cohort_sha256,
        "isolated": True,
        "shared_outcome_store": False,
        "agreement_optimization_forbidden": True,
        "boundary": VALIDATION_BOUNDARY,
    }
    atomic_write_json(path / "isolation.json", marker)
    return path


def record_disagreement_metrics(
    *,
    cohort_sha256: str,
    case_id: str,
    requirement_id: str,
    findings: list[str],
    evidence_selection_disagreement: bool,
    time_burden_minutes: float | None = None,
    uncertainty_flagged: bool = False,
    reopening_triggered: bool = False,
) -> dict[str, Any]:
    distinct = sorted({item for item in findings if item.strip()})
    return {
        "cohort_sha256": cohort_sha256,
        "case_id": case_id,
        "requirement_id": requirement_id,
        "finding_states": distinct,
        "disagreement": len(distinct) > 1,
        "evidence_selection_disagreement": evidence_selection_disagreement,
        "time_burden_minutes": time_burden_minutes,
        "uncertainty_flagged": uncertainty_flagged,
        "reopening_triggered": reopening_triggered,
        "agreement_optimization_forbidden": True,
        "deidentified_export_only": True,
        "boundary": VALIDATION_BOUNDARY,
    }


def validation_export_guard(payload: dict[str, Any]) -> dict[str, Any]:
    """Refuse protected participant/reviewer fields in S2-bound exports."""
    hits = [key for key in PROTECTED_EXPORT_FIELDS if key in payload]
    if hits:
        raise ValueError(f"Validation export refused protected fields: {hits}")
    return {
        **payload,
        "protected_participant_reviewer_data_excluded": True,
        "s2_safe": True,
        "boundary": VALIDATION_BOUNDARY,
    }


def export_disagreement_bundle(
    *,
    cohort: dict[str, Any],
    metrics: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    """Write a deidentified disagreement export. No empirical global-validation claim."""
    if cohort.get("global_validation_claim") is True:
        raise ValueError("Refusing export that claims global validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    guarded_metrics = [validation_export_guard(dict(item)) for item in metrics]
    bundle = {
        "cohort_sha256": cohort.get("cohort_sha256"),
        "protocol_id": cohort.get("protocol_id"),
        "case_count": cohort.get("case_count"),
        "metric_count": len(guarded_metrics),
        "disagreement_count": sum(1 for item in guarded_metrics if item.get("disagreement")),
        "empirical_outcomes_present": False,
        "global_validation_claim": False,
        "agreement_optimization_forbidden": True,
        "boundary": VALIDATION_BOUNDARY,
    }
    atomic_write_json(output_dir / "disagreement-summary.json", bundle)
    metrics_path = output_dir / "disagreement-metrics.jsonl"
    metrics_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in guarded_metrics),
        encoding="utf-8",
    )
    return {**bundle, "output_dir": str(output_dir), "metrics_path": str(metrics_path)}
