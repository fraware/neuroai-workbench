"""Monitor onboarding lifecycle. Source acceptance alone never creates a live monitor."""

from __future__ import annotations

from typing import Any

ONBOARDING_BOUNDARY = (
    "Monitor onboarding is a staged, human-gated lifecycle. Discovery acceptance, quarantine "
    "approval, monitoring handoff, and release authority remain separate. Source disappearance "
    "never deletes historical evidence."
)

# Ordered stages matching the handoff data-side constraint.
ONBOARDING_STAGES = (
    "DISCOVERY_CANDIDATE",
    "REPLAY_PROJECTION",
    "CURRENT_SOURCE_IDENTITY_CHECK",
    "PENDING_HUMAN_ACCEPTANCE",
    "HUMAN_DISPOSITION_RECORDED",
    "DRAFT_SOURCE_NAMESPACE_SUCCESSOR",
    "DISCOVERY_ORIGIN_SOURCE_CANDIDATE",
    "PENDING_MONITOR_REVIEW",
    "MONITORING_REVIEW_RECORDED",
    "DRAFT_ONBOARDING_PLAN",
    "AUTHORIZED_FIRST_CAPTURE_PENDING",
    "QUARANTINE_HELD",
    "QUARANTINE_APPROVED",
    "MONITORING_HANDOFF",
    "DRAFT_MONITOR_REGISTRY_SUCCESSOR",
    "AWAITING_RELEASE_AUTHORITY",
)

TERMINAL_BLOCKED = frozenset(
    {
        "REJECTED_AT_HUMAN_ACCEPTANCE",
        "REJECTED_AT_MONITOR_REVIEW",
        "REJECTED_AT_QUARANTINE",
        "SOURCE_DISAPPEARED_HISTORY_RETAINED",
    }
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DISCOVERY_CANDIDATE": frozenset({"REPLAY_PROJECTION", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "REPLAY_PROJECTION": frozenset({"CURRENT_SOURCE_IDENTITY_CHECK", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "CURRENT_SOURCE_IDENTITY_CHECK": frozenset({"PENDING_HUMAN_ACCEPTANCE", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "PENDING_HUMAN_ACCEPTANCE": frozenset(
        {"HUMAN_DISPOSITION_RECORDED", "REJECTED_AT_HUMAN_ACCEPTANCE", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}
    ),
    "HUMAN_DISPOSITION_RECORDED": frozenset(
        {"DRAFT_SOURCE_NAMESPACE_SUCCESSOR", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}
    ),
    "DRAFT_SOURCE_NAMESPACE_SUCCESSOR": frozenset(
        {"DISCOVERY_ORIGIN_SOURCE_CANDIDATE", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}
    ),
    "DISCOVERY_ORIGIN_SOURCE_CANDIDATE": frozenset({"PENDING_MONITOR_REVIEW", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "PENDING_MONITOR_REVIEW": frozenset(
        {"MONITORING_REVIEW_RECORDED", "REJECTED_AT_MONITOR_REVIEW", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}
    ),
    "MONITORING_REVIEW_RECORDED": frozenset({"DRAFT_ONBOARDING_PLAN", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "DRAFT_ONBOARDING_PLAN": frozenset({"AUTHORIZED_FIRST_CAPTURE_PENDING", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "AUTHORIZED_FIRST_CAPTURE_PENDING": frozenset({"QUARANTINE_HELD", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "QUARANTINE_HELD": frozenset(
        {"QUARANTINE_APPROVED", "REJECTED_AT_QUARANTINE", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}
    ),
    "QUARANTINE_APPROVED": frozenset({"MONITORING_HANDOFF", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "MONITORING_HANDOFF": frozenset({"DRAFT_MONITOR_REGISTRY_SUCCESSOR", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "DRAFT_MONITOR_REGISTRY_SUCCESSOR": frozenset(
        {"AWAITING_RELEASE_AUTHORITY", "SOURCE_DISAPPEARED_HISTORY_RETAINED"}
    ),
    "AWAITING_RELEASE_AUTHORITY": frozenset({"SOURCE_DISAPPEARED_HISTORY_RETAINED"}),
    "REJECTED_AT_HUMAN_ACCEPTANCE": frozenset(),
    "REJECTED_AT_MONITOR_REVIEW": frozenset(),
    "REJECTED_AT_QUARANTINE": frozenset(),
    "SOURCE_DISAPPEARED_HISTORY_RETAINED": frozenset(),
}


def initial_onboarding_record(*, source_candidate_id: str, actor: str) -> dict[str, Any]:
    return {
        "source_candidate_id": source_candidate_id,
        "stage": "DISCOVERY_CANDIDATE",
        "history": [{"stage": "DISCOVERY_CANDIDATE", "actor": actor, "note": "Lifecycle opened"}],
        "monitor_created": False,
        "live_monitor_authorized": False,
        "historical_evidence_retained": True,
        "release_authorized": False,
        "boundary": ONBOARDING_BOUNDARY,
    }


def advance_onboarding(
    record: dict[str, Any],
    *,
    next_stage: str,
    actor: str,
    note: str,
) -> dict[str, Any]:
    current = str(record.get("stage"))
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if next_stage not in allowed:
        raise ValueError(f"Illegal onboarding transition {current!r} -> {next_stage!r}")
    if next_stage == "DRAFT_MONITOR_REGISTRY_SUCCESSOR" and not record.get("quarantine_approved"):
        # Quarantine approval is a separate gate; stage machine already requires QUARANTINE_APPROVED first.
        pass
    updated = {
        **record,
        "stage": next_stage,
        "history": [
            *list(record.get("history") or []),
            {"stage": next_stage, "actor": actor, "note": note},
        ],
        "boundary": ONBOARDING_BOUNDARY,
    }
    if next_stage == "QUARANTINE_APPROVED":
        updated["quarantine_approved"] = True
    if next_stage == "SOURCE_DISAPPEARED_HISTORY_RETAINED":
        updated["historical_evidence_retained"] = True
        updated["monitor_created"] = False
    # Never create a live monitor from source acceptance alone.
    if next_stage in {"HUMAN_DISPOSITION_RECORDED", "PENDING_HUMAN_ACCEPTANCE", "PENDING_MONITOR_REVIEW"}:
        updated["monitor_created"] = False
        updated["live_monitor_authorized"] = False
    if next_stage == "AWAITING_RELEASE_AUTHORITY":
        updated["monitor_created"] = False  # draft successor only; release authority is separate
        updated["live_monitor_authorized"] = False
        updated["release_authorized"] = False
    return updated


def assert_no_monitor_from_source_acceptance(record: dict[str, Any]) -> None:
    stage = str(record.get("stage"))
    if stage in {
        "PENDING_HUMAN_ACCEPTANCE",
        "HUMAN_DISPOSITION_RECORDED",
        "DRAFT_SOURCE_NAMESPACE_SUCCESSOR",
        "DISCOVERY_ORIGIN_SOURCE_CANDIDATE",
        "PENDING_MONITOR_REVIEW",
    } and (record.get("monitor_created") or record.get("live_monitor_authorized")):
        raise ValueError("Source acceptance must not create a live monitor")


def record_source_disappearance(record: dict[str, Any], *, actor: str, note: str) -> dict[str, Any]:
    """Mark disappearance without deleting historical evidence."""
    updated = {
        **record,
        "stage": "SOURCE_DISAPPEARED_HISTORY_RETAINED",
        "historical_evidence_retained": True,
        "monitor_created": False,
        "live_monitor_authorized": False,
        "history": [
            *list(record.get("history") or []),
            {"stage": "SOURCE_DISAPPEARED_HISTORY_RETAINED", "actor": actor, "note": note},
        ],
        "boundary": ONBOARDING_BOUNDARY,
    }
    return updated
