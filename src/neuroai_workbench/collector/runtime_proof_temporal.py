"""Temporal guardrails for the bounded Phase 3 live/replay proof harness.

This module does not alter general replay selection. It verifies that one exact,
hash-checked collector capture is temporally eligible for the replay cutoff declared
by a Phase 3 proof run.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..util import ensure_identifier, load_json, safe_join
from .prior_capture_replay import (
    PriorCaptureError,
    PriorCaptureReference,
    _capture_age_seconds,
    _reference_from_result,
    verify_prior_capture_reference,
)


class RuntimeProofTemporalError(ValueError):
    """Raised when an exact Phase 3 capture is incompatible with a replay cutoff."""


def require_phase3_result_eligible_at_cutoff(
    quarantine_root: Path,
    *,
    result_id: str,
    as_of: str,
    expected_source_id: str | None = None,
) -> PriorCaptureReference:
    """Return an integrity-checked result only when it existed at ``as_of``.

    Date-only cutoffs retain the general replay contract: they mean end-of-day UTC.
    A capture newer than the cutoff fails closed; the guard never rewrites either the
    capture timestamp or the requested cutoff.
    """

    try:
        ensure_identifier(result_id, "result_id")
        result_path = safe_join(quarantine_root, "results", f"{result_id}.json")
    except ValueError as exc:
        raise RuntimeProofTemporalError("result_id is invalid") from exc
    if not result_path.is_file():
        raise RuntimeProofTemporalError("expected Phase 3 collector result record is missing")
    try:
        result = load_json(result_path)
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise RuntimeProofTemporalError("expected Phase 3 collector result record is unreadable") from exc
    if not isinstance(result, dict):
        raise RuntimeProofTemporalError("expected Phase 3 collector result record must be an object")

    try:
        reference = _reference_from_result(quarantine_root, result)
        verify_prior_capture_reference(quarantine_root, reference)
    except PriorCaptureError as exc:
        raise RuntimeProofTemporalError(f"expected Phase 3 capture failed integrity validation: {exc}") from exc
    if reference.result_id != result_id:
        raise RuntimeProofTemporalError("collector result identity does not match expected Phase 3 result_id")
    if expected_source_id is not None and reference.source_id != expected_source_id:
        raise RuntimeProofTemporalError("collector capture source_id does not match expected Phase 3 source")

    try:
        _capture_age_seconds(as_of=as_of, retrieved_at=reference.retrieved_at)
    except PriorCaptureError as exc:
        if "later than the replay cutoff" in str(exc):
            raise RuntimeProofTemporalError(
                "Phase 3 replay cutoff precedes the exact expected capture: "
                f"as_of={as_of!r}, retrieved_at={reference.retrieved_at!r}"
            ) from exc
        raise RuntimeProofTemporalError(f"Phase 3 replay cutoff is invalid: {exc}") from exc
    return reference
