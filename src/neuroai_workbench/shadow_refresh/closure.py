"""Wave 2 shadow-refresh closure helpers for issue #43.

Automates software/ops steps that do not require forged dual-human review
signatures. Artifacts remain SHADOW_EVALUATION_NOT_CANONICAL. Unresolved
network access is recorded as typed outcomes, never as FAIL findings.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..collector.handoff import (
    HandoffBlockedError,
    load_collection_result,
    load_quarantine_record,
    prepare_monitoring_handoff,
)
from ..entities import initialize_registry, propose_resolution, record_resolution_disposition
from ..extraction.disposition import (
    dispose_extraction_response,
    record_extraction_request,
    record_extraction_response,
)
from ..extraction.evaluation import build_extraction_request_from_capture
from ..extraction.providers import (
    FAKE_OFFLINE_PROVIDER_ID,
    ExtractionProviderConfig,
    new_request_id,
    resolve_provider,
)
from ..monitoring import (
    create_change_candidate,
    initialize_monitoring,
    record_snapshot,
)
from ..review_queue import (
    claim_lease,
    initialize_review_queue,
    list_queue_items,
    load_item_opinions,
    register_reviewer_profile,
    release_lease,
    submit_opinion,
)
from ..util import atomic_write_json, load_json, sha256_bytes, utc_now
from .live import run_live_cohort_collection
from .metrics import compute_go_no_go_metrics
from .schemas import SHADOW_EVALUATION_STATUS, SHADOW_REFRESH_BOUNDARY

DEFAULT_FAILED_SOURCE_IDS = ("SRC-0041", "SRC-0115", "SRC-14-007")
EVAL_ACTOR = "shadow-eval-scaffolding"
REVIEWER_A = "REV-SHADOW-A"
REVIEWER_B = "REV-SHADOW-B"
REQUIRED_SHADOW_REVIEWERS = (REVIEWER_A, REVIEWER_B)
GOVERNANCE_ISSUE = "#101"
ALLOWED_OPINION_POSITIONS = frozenset({"SUPPORT", "OPPOSE", "DEFER", "ABSTAIN", "NEEDS_EVIDENCE"})


def classify_retrieval_failure(failure: dict[str, Any]) -> dict[str, Any]:
    """Map a collector failure record into a typed retrieval outcome (not a finding)."""
    message = str(failure.get("failure_message") or failure.get("message") or "")
    failure_class = str(failure.get("failure_class") or "UNKNOWN")
    http_status = failure.get("http_status")
    status_match = re.search(r"Unexpected HTTP status\s+(\d{3})", message)
    if http_status is None and status_match:
        http_status = int(status_match.group(1))

    outcome_type = "UNRESOLVED_RETRIEVAL"
    if failure_class == "TIMEOUT" or "timeout" in message.casefold():
        outcome_type = "TIMEOUT"
    elif failure_class == "DNS_FAILURE":
        outcome_type = "DNS_FAILURE"
    elif failure_class == "SSRF_BLOCK" or failure_class == "POLICY_BLOCK":
        outcome_type = "POLICY_BLOCK"
    elif http_status in {401, 403}:
        outcome_type = "ACCESS_DENIAL"
    elif http_status == 404:
        outcome_type = "CONTENT_NOT_FOUND_OR_URL_REPLACEMENT_NEEDED"
    elif http_status in {301, 302, 303, 307, 308} or "redirect" in message.casefold():
        outcome_type = "REDIRECT_FAILURE"
    elif isinstance(http_status, int) and http_status >= 500:
        outcome_type = "UPSTREAM_SERVER_ERROR"
    elif failure_class == "HTTP_ERROR":
        outcome_type = "HTTP_ERROR_UNCLASSIFIED"

    return {
        "source_id": failure.get("source_id"),
        "failure_id": failure.get("failure_id") or failure.get("record_id"),
        "requested_url": failure.get("requested_url"),
        "failure_class": failure_class,
        "http_status": http_status,
        "message": message,
        "outcome_type": outcome_type,
        "finding_effect": "NONE",
        "notes": (
            "Typed retrieval outcome only. Unresolved access must not be converted into a FAIL finding "
            "or substantive assessment mutation."
        ),
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def build_source_retry_plan(
    registry: dict[str, Any],
    source_ids: list[str],
    *,
    as_of: str = "2026-08-03",
) -> dict[str, Any]:
    """Build a one-shot evaluation plan limited to the listed HTTP sources."""
    wanted = set(source_ids)
    source_index = {
        str(record["source_id"]): record
        for record in registry.get("sources", [])
        if isinstance(record, dict) and "source_id" in record
    }
    due: list[dict[str, Any]] = []
    missing: list[str] = []
    for source_id in source_ids:
        record = source_index.get(source_id)
        if record is None:
            missing.append(source_id)
            continue
        due.append(
            {
                "source_id": source_id,
                "monitor_id": record.get("monitor_id"),
                "url": record.get("url"),
                "publisher": record.get("publisher"),
                "source_class": record.get("source_class"),
                "network_access_required": record.get("network_access_required", True),
                "evaluation_override": "SHADOW_LIVE_RETRY_DUE",
            }
        )
    if missing:
        raise ValueError(f"Retry source IDs missing from registry: {', '.join(missing)}")
    if wanted - {item["source_id"] for item in due}:
        raise ValueError("Retry plan incomplete")
    return {
        "plan_id": f"SHADOW-RETRY-{as_of}",
        "as_of": as_of,
        "due": due,
        "manual": [],
        "not_due": [],
        "counts": {"due": len(due), "manual": 0, "not_due": 0},
        "status": SHADOW_EVALUATION_STATUS,
        "live_evaluation": True,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def retry_failed_sources(
    *,
    registry: dict[str, Any],
    registry_sha256: str,
    quarantine_root: Path,
    source_ids: list[str] | None = None,
    as_of: str = "2026-08-03",
) -> dict[str, Any]:
    """Retry allowlisted failed sources into a dedicated quarantine root."""
    ids = list(source_ids or DEFAULT_FAILED_SOURCE_IDS)
    plan = build_source_retry_plan(registry, ids, as_of=as_of)
    live_package = run_live_cohort_collection(
        plan=plan,
        registry=registry,
        registry_sha256=registry_sha256,
        quarantine_root=quarantine_root,
    )
    by_source: dict[str, dict[str, Any]] = {}
    failures_dir = quarantine_root / "failures"
    if failures_dir.is_dir():
        for path in sorted(failures_dir.glob("*.json")):
            try:
                record = load_json(path)
            except (OSError, ValueError, TypeError):
                continue
            if isinstance(record, dict) and record.get("source_id"):
                by_source[str(record["source_id"])] = classify_retrieval_failure(record)
    for outcome in live_package.get("collection_run", {}).get("outcomes", []):
        sid = str(outcome.get("source_id") or "")
        if not sid:
            continue
        if outcome.get("status") == "RESULT":
            by_source[sid] = {
                "source_id": sid,
                "outcome_type": "RETRIEVAL_SUCCEEDED",
                "failure_class": None,
                "http_status": None,
                "message": None,
                "finding_effect": "NONE",
                "record_id": outcome.get("record_id"),
                "status": SHADOW_EVALUATION_STATUS,
                "boundary": SHADOW_REFRESH_BOUNDARY,
            }
        elif sid not in by_source:
            by_source[sid] = classify_retrieval_failure(outcome)
    return {
        "metadata": {
            "title": "Shadow refresh HTTP_ERROR retry outcomes",
            "executed_at": utc_now(),
            "status": SHADOW_EVALUATION_STATUS,
        },
        "source_ids": ids,
        "live_package": live_package,
        "typed_outcomes": [by_source[sid] for sid in ids if sid in by_source],
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def list_quarantine_successes(quarantine_root: Path) -> list[dict[str, Any]]:
    records_dir = quarantine_root / "records"
    if not records_dir.is_dir():
        return []
    successes: list[dict[str, Any]] = []
    for path in sorted(records_dir.glob("*.json")):
        record = load_json(path)
        if not isinstance(record, dict):
            continue
        if record.get("result_id"):
            successes.append(record)
    return successes


def handoff_quarantine_sample_to_evaluation(
    *,
    quarantine_root: Path,
    evaluation_workspace: Path,
    registry_path: Path,
    sample_size: int = 5,
    approved_by: str = EVAL_ACTOR,
) -> dict[str, Any]:
    """Handoff a sample of pre-approved quarantine records into an evaluation workspace only.

    Each selected record must already be ``APPROVED_FOR_HANDOFF``. This function does
    not call ``approve_quarantine_record`` and fails closed on pending or rejected
    records in the selected sample. Does not enable the collector monitoring handoff
    kill-switch and does not mutate the canonical ops workbench.
    """
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    evaluation_workspace.mkdir(parents=True, exist_ok=True)
    if not (evaluation_workspace / "observatory" / "monitoring" / "registry" / "registry.json").is_file():
        initialize_monitoring(evaluation_workspace, registry_path, actor=approved_by)

    # Fail closed: only pre-approved records may enter the handoff sample. Pending
    # successes are left untouched for per-record human review.
    records = [
        record
        for record in list_quarantine_successes(quarantine_root)
        if record.get("approval_state") == "APPROVED_FOR_HANDOFF"
    ][:sample_size]
    handoffs: list[dict[str, Any]] = []
    for record in records:
        qid = str(record["quarantine_id"])
        current = load_quarantine_record(quarantine_root, qid)
        if current.get("approval_state") != "APPROVED_FOR_HANDOFF":
            raise HandoffBlockedError(
                f"Quarantine record {qid!r} requires APPROVED_FOR_HANDOFF before "
                f"evaluation handoff (current: {current.get('approval_state')!r}); "
                "handoff does not auto-approve"
            )
        payload = prepare_monitoring_handoff(quarantine_root, qid)
        result = load_collection_result(quarantine_root, payload.result_id)
        media_type = str(result.get("media_type") or "application/octet-stream")
        data = payload.bytes_path.read_bytes()
        snapshot = record_snapshot(
            evaluation_workspace,
            payload.source_id,
            data,
            media_type=media_type,
            retrieved_at=payload.captured_at,
            retrieval_url=str(result.get("final_url") or result.get("requested_url") or ""),
            original_filename=payload.original_filename,
            actor=approved_by,
        )
        handoffs.append(
            {
                "quarantine_id": qid,
                "source_id": payload.source_id,
                "snapshot_id": snapshot["snapshot_id"],
                "sha256": snapshot["sha256"],
                "size_bytes": snapshot["size_bytes"],
                "media_type": media_type,
            }
        )
    return {
        "metadata": {
            "title": "Evaluation-only quarantine to snapshot handoff",
            "status": SHADOW_EVALUATION_STATUS,
            "approved_by": approved_by,
            "executed_at": utc_now(),
        },
        "evaluation_workspace": str(evaluation_workspace),
        "sample_size_requested": sample_size,
        "handoffs": handoffs,
        "monitoring_handoff_kill_switch": "DISABLED",
        "canonical_workbench_mutated": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def create_first_capture_candidates(
    *,
    evaluation_workspace: Path,
    handoffs: list[dict[str, Any]],
    actor: str = EVAL_ACTOR,
) -> dict[str, Any]:
    """Create MANUAL change candidates for first-time evaluation snapshots.

    Baseline comparison is unavailable when no prior snapshots exist; mechanical
    NO_CHANGE/CONTENT_CHANGED comparison therefore cannot run until a second capture.
    """
    candidates: list[dict[str, Any]] = []
    for item in handoffs:
        candidate = create_change_candidate(
            evaluation_workspace,
            str(item["source_id"]),
            str(item["snapshot_id"]),
            previous_snapshot_id=None,
            summary=(
                "First evaluation snapshot after live quarantine handoff; "
                "no baseline capture available for mechanical comparison."
            ),
            actor=actor,
        )
        candidates.append(
            {
                "candidate_id": candidate["candidate_id"],
                "source_id": candidate["source_id"],
                "snapshot_id": item["snapshot_id"],
                "detection": candidate["detection"],
                "status": candidate["status"],
            }
        )
    return {
        "metadata": {
            "title": "First-capture change candidates (no baseline)",
            "status": SHADOW_EVALUATION_STATUS,
            "executed_at": utc_now(),
        },
        "baseline_comparison": "UNAVAILABLE_NO_PRIOR_SNAPSHOTS",
        "candidates": candidates,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def scaffold_dual_human_review(
    *,
    evaluation_workspace: Path,
    output_dir: Path,
    actor: str = EVAL_ACTOR,
) -> dict[str, Any]:
    """Register two reviewer profiles and project the queue; do not forge opinions."""
    initialize_review_queue(evaluation_workspace, actor=actor)
    profile_a = register_reviewer_profile(
        evaluation_workspace,
        REVIEWER_A,
        "Shadow Reviewer A (claimed local workflow identity)",
        ["MONITORING_REVIEWER", "ADJUDICATION_REVIEWER"],
        actor=actor,
    )
    profile_b = register_reviewer_profile(
        evaluation_workspace,
        REVIEWER_B,
        "Shadow Reviewer B (claimed local workflow identity)",
        ["MONITORING_REVIEWER", "ADJUDICATION_REVIEWER"],
        actor=actor,
    )
    items = list_queue_items(evaluation_workspace, persist_projection=True)
    instructions = {
        "metadata": {
            "title": "Dual human review instructions for shadow evaluation candidates",
            "status": SHADOW_EVALUATION_STATUS,
            "generated_at": utc_now(),
            "core_issue": "#43",
            "governance_issue": GOVERNANCE_ISSUE,
        },
        "required_reviewers": [REVIEWER_A, REVIEWER_B],
        "identity_boundary": (
            "Reviewer profile IDs are claimed local workflow identities only. "
            "They do not authenticate persons or establish institutional authority."
        ),
        "recording_cli": "scripts/record_shadow_dual_review.py",
        "steps": [
            "status → list OPEN item IDs.",
            "REV-SHADOW-A and REV-SHADOW-B each record an opinion on every OPEN item (disagreement optional).",
            "assess → confirm dual_review_complete.",
            "Owners record formal-disposition; software refuses forged GO.",
            "Do not write a canonical successor from this workspace.",
            f"Canonical release remains deferred to {GOVERNANCE_ISSUE}.",
        ],
        "open_item_ids": [item["item_id"] for item in items if item.get("queue_status") == "OPEN"],
        "completion_state": "SCAFFOLDED_AWAITING_HUMAN_OPINIONS",
        "forged_completions": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "dual_review_instructions.json", instructions)
    residual = build_human_residual_checklist(dual_review_complete=False)
    atomic_write_json(output_dir / "human_residual_checklist.json", residual)
    return {
        "profiles": {
            "reviewer_a": profile_a["profile"]["profile_id"],
            "reviewer_b": profile_b["profile"]["profile_id"],
            "created_a": profile_a["created"],
            "created_b": profile_b["created"],
        },
        "queue_item_count": len(items),
        "open_item_count": sum(1 for item in items if item.get("queue_status") == "OPEN"),
        "instructions_path": str(output_dir / "dual_review_instructions.json"),
        "residual_checklist_path": str(output_dir / "human_residual_checklist.json"),
        "dual_review_complete": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def build_human_residual_checklist(*, dual_review_complete: bool) -> dict[str, Any]:
    """Build the residual human checklist without inventing review opinions."""
    dual_state = "SATISFIED" if dual_review_complete else "BLOCKED_HUMAN"
    go_state = "READY_FOR_OWNER" if dual_review_complete else "BLOCKED_HUMAN"
    return {
        "metadata": {
            "title": "Small-team residual checklist (shadow #101)",
            "status": SHADOW_EVALUATION_STATUS,
            "generated_at": utc_now(),
            "core_issue": "#43",
            "governance_issue": GOVERNANCE_ISSUE,
        },
        "checklist": [
            {
                "id": "DUAL_REVIEW_OPINIONS",
                "state": dual_state,
                "detail": (
                    "REV-SHADOW-A and REV-SHADOW-B each record an opinion on every OPEN item "
                    f"(claimed local IDs only). Tracked under {GOVERNANCE_ISSUE}."
                ),
            },
            {
                "id": "DISAGREEMENT_PRESERVATION",
                "state": "PENDING_HUMAN" if not dual_review_complete else "REQUIRED",
                "detail": "Keep any disagreement or abstention on record; do not erase dissent.",
            },
            {
                "id": "FORMAL_GO_AUTHORIZATION",
                "state": go_state,
                "detail": (
                    "After dual review, owners record formal disposition; software refuses forged GO. "
                    f"Canonical release stays under {GOVERNANCE_ISSUE}."
                ),
            },
            {
                "id": "UNRESOLVED_RETRIEVAL_URLS",
                "state": "PENDING_HUMAN",
                "detail": (
                    "SRC-0041 / SRC-0115 / SRC-14-007: KEEP_AS_TYPED_FAILURE; "
                    "finding_effect=NONE; do not invent FAIL findings."
                ),
            },
            {
                "id": "PROTECTED_ARCHIVE_APPROVALS",
                "state": "EXTERNAL",
                "detail": "Archive/network approvals remain under #44.",
            },
        ],
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def assess_dual_human_review(
    evaluation_workspace: Path,
    *,
    required_reviewers: tuple[str, ...] = REQUIRED_SHADOW_REVIEWERS,
) -> dict[str, Any]:
    """Assess whether every OPEN queue item has opinions from both required reviewers.

    Never forges opinions. Disagreement and abstention count toward completeness.
    """
    items = list_queue_items(evaluation_workspace, persist_projection=True)
    open_items = [item for item in items if item.get("queue_status") == "OPEN"]
    required = tuple(required_reviewers)
    per_item: list[dict[str, Any]] = []
    agreements = 0
    disagreements = 0
    missing_pairs = 0

    for item in open_items:
        item_id = str(item["item_id"])
        opinions = load_item_opinions(evaluation_workspace, item_id)
        by_reviewer: dict[str, list[dict[str, Any]]] = {}
        for opinion in opinions:
            profile = str(opinion.get("reviewer_profile_id") or "")
            by_reviewer.setdefault(profile, []).append(opinion)
        present = [profile for profile in required if profile in by_reviewer]
        missing = [profile for profile in required if profile not in by_reviewer]
        positions = sorted(
            {
                str(opinion.get("position"))
                for profile in present
                for opinion in by_reviewer[profile]
                if opinion.get("position")
            }
        )
        complete = not missing
        if not complete:
            missing_pairs += 1
        elif len(positions) <= 1:
            agreements += 1
        else:
            disagreements += 1
        per_item.append(
            {
                "item_id": item_id,
                "source_id": item.get("source_id"),
                "candidate_id": item.get("candidate_id"),
                "required_reviewers": list(required),
                "present_reviewers": present,
                "missing_reviewers": missing,
                "positions": positions,
                "opinion_count": len(opinions),
                "complete": complete,
            }
        )

    dual_complete = bool(open_items) and missing_pairs == 0
    if not open_items:
        dual_complete = False

    return {
        "metadata": {
            "title": "Dual human review assessment for shadow evaluation candidates",
            "assessed_at": utc_now(),
            "status": SHADOW_EVALUATION_STATUS,
            "core_issue": "#43",
            "governance_issue": GOVERNANCE_ISSUE,
        },
        "required_reviewers": list(required),
        "open_item_count": len(open_items),
        "complete_item_count": sum(1 for row in per_item if row["complete"]),
        "incomplete_item_count": missing_pairs,
        "review_agreements": agreements,
        "review_disagreements": disagreements,
        "dual_review_complete": dual_complete,
        "forged_completions": False,
        "items": per_item,
        "residual": build_human_residual_checklist(dual_review_complete=dual_complete),
        "identity_boundary": (
            "Reviewer profile IDs are claimed local workflow identities only. "
            "They do not authenticate persons or establish institutional authority."
        ),
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def record_human_review_opinion(
    evaluation_workspace: Path,
    *,
    item_id: str,
    reviewer_profile_id: str,
    position: str,
    rationale: str,
    ttl_seconds: int = 3600,
    role: str | None = None,
) -> dict[str, Any]:
    """Claim a lease (if needed) and record one human opinion. Never forges content."""
    if reviewer_profile_id not in REQUIRED_SHADOW_REVIEWERS:
        raise ValueError(
            f"Shadow dual-review recorder accepts only {REQUIRED_SHADOW_REVIEWERS}; got {reviewer_profile_id!r}"
        )
    if position not in ALLOWED_OPINION_POSITIONS:
        raise ValueError(f"Unsupported opinion position {position!r}; allowed={sorted(ALLOWED_OPINION_POSITIONS)}")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Opinion rationale must not be empty")

    items = {str(item["item_id"]): item for item in list_queue_items(evaluation_workspace)}
    if item_id not in items:
        raise ValueError(f"Unknown queue item {item_id!r}")

    active_lease = items[item_id].get("active_lease") or {}
    lease_record: dict[str, Any] | None = None
    if active_lease.get("reviewer_profile_id") == reviewer_profile_id:
        lease_record = dict(active_lease)
    else:
        claimed = claim_lease(
            evaluation_workspace,
            item_id,
            reviewer_profile_id,
            ttl_seconds=ttl_seconds,
            actor=reviewer_profile_id,
        )
        lease_record = claimed["lease"]

    submitted = submit_opinion(
        evaluation_workspace,
        item_id,
        reviewer_profile_id,
        position,
        rationale,
        role=role,
        actor=reviewer_profile_id,
    )
    release = release_lease(
        evaluation_workspace,
        str(lease_record["lease_id"]),
        reviewer_profile_id,
        reason="RELEASED",
        actor=reviewer_profile_id,
    )
    assessment = assess_dual_human_review(evaluation_workspace)
    return {
        "lease": lease_record,
        "lease_release": release["release"],
        "opinion": submitted["opinion"],
        "opinion_path": submitted["path"],
        "assessment": assessment,
        "dual_review_complete": assessment["dual_review_complete"],
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def run_offline_entity_sample(
    *,
    evaluation_workspace: Path,
    sample_mentions: list[dict[str, str]],
    actor: str = EVAL_ACTOR,
) -> dict[str, Any]:
    """Propose entity resolutions and record evaluation dispositions (not dual review)."""
    initialize_registry(evaluation_workspace, actor=actor)
    proposals: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for item in sample_mentions:
        mention = item["mention"].strip()
        if not mention:
            continue
        proposal = propose_resolution(
            evaluation_workspace,
            raw_mention=mention,
            source_capture_ref=item.get("source_id"),
            actor=actor,
        )
        proposals.append(
            {
                "proposal_id": proposal["proposal_id"],
                "source_id": item.get("source_id"),
                "mention": mention,
                "resolution_state": proposal["resolution_state"],
                "status": proposal["status"],
            }
        )
        if proposal["status"] == "PENDING_HUMAN_DISPOSITION":
            decision = (
                "DEFER" if proposal["resolution_state"] in {"AMBIGUOUS", "DUPLICATE_CANDIDATE"} else "NEEDS_EVIDENCE"
            )
            disposition = record_resolution_disposition(
                evaluation_workspace,
                proposal["proposal_id"],
                decision,
                rationale=(
                    "Shadow evaluation offline disposition recorded by claimed local scaffolding actor. "
                    "Not a dual-human monitoring review completion."
                ),
                actor=actor,
            )
            dispositions.append(
                {
                    "disposition_id": disposition["disposition_id"],
                    "proposal_id": proposal["proposal_id"],
                    "decision": disposition["decision"],
                }
            )
    return {
        "metadata": {
            "title": "Offline entity disposition sample for shadow evaluation",
            "status": SHADOW_EVALUATION_STATUS,
            "executed_at": utc_now(),
            "actor": actor,
        },
        "proposal_count": len(proposals),
        "disposition_count": len(dispositions),
        "proposals": proposals,
        "dispositions": dispositions,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def run_offline_extraction_sample(
    *,
    evaluation_workspace: Path,
    quarantine_root: Path,
    handoffs: list[dict[str, Any]],
    actor: str = EVAL_ACTOR,
) -> dict[str, Any]:
    """Run offline fake-provider extraction on synthetic public stubs linked to capture digests.

    Raw quarantine HTML is not fed into the extraction request path: disclosure controls may
    refuse local-path-like strings embedded in page markup. The sample remains
    CONTRACT_FIXTURE_NON_ACCURACY and is not an accuracy evaluation.
    """
    del quarantine_root  # Digests come from handoff metadata; bodies stay out of extraction requests.
    config = ExtractionProviderConfig(
        config_id="CFG-SHADOW-FAKE-OFFLINE",
        provider_id=FAKE_OFFLINE_PROVIDER_ID,
        model_id="fake-offline-shadow-eval-v1",
        enabled=True,
        profile="conservative",
        endpoint_class="NOT_EXECUTED",
        notes="CONTRACT_FIXTURE_NON_ACCURACY for shadow evaluation sample only.",
    )
    provider = resolve_provider(config)
    recorded: list[dict[str, Any]] = []
    for item in handoffs[: min(3, len(handoffs))]:
        source_id = str(item["source_id"])
        sha = str(item["sha256"])
        excerpt = (
            f"Public synthetic shadow evaluation stub for {source_id}. "
            "This text is not source page content. Capture digest linkage is metadata-only."
        )
        capture_stub = {
            "capture_id": f"CAP-SHADOW-{source_id}",
            "content_sha256": sha,
            "public_text": excerpt,
        }
        request = build_extraction_request_from_capture(
            capture_stub,
            request_id=new_request_id(),
        )
        record_extraction_request(evaluation_workspace, request, actor=actor)
        response = provider.extract(request)
        record_extraction_response(
            evaluation_workspace,
            request,
            response,
            provider=config.provider_id,
            model=config.model_id,
            actor=actor,
        )
        disposition = dispose_extraction_response(
            evaluation_workspace,
            request["request_id"],
            "REJECTED",
            notes=(
                "Shadow evaluation offline disposition: CONTRACT_FIXTURE_NON_ACCURACY output rejected "
                "for substantive use. Does not authorize findings or dual-review completion."
            ),
            actor=actor,
        )
        recorded.append(
            {
                "source_id": source_id,
                "request_id": request["request_id"],
                "content_sha256": sha,
                "disposition": disposition["disposition"]["disposition"],
                "provider": config.provider_id,
                "accuracy_lane": "CONTRACT_FIXTURE_NON_ACCURACY",
            }
        )
    return {
        "metadata": {
            "title": "Offline extraction disposition sample for shadow evaluation",
            "status": SHADOW_EVALUATION_STATUS,
            "executed_at": utc_now(),
            "actor": actor,
        },
        "records": recorded,
        "record_count": len(recorded),
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def build_closure_run_results(
    *,
    run_id: str,
    live_succeeded: int,
    live_failed: int,
    live_attempted: int,
    digest_count: int,
    candidate_count: int,
    entity_decisions: int,
    entity_correct: int,
    dual_review_complete: bool,
    review_agreements: int = 0,
    review_disagreements: int = 0,
) -> dict[str, Any]:
    """Build observed run-results for metrics from executed shadow steps."""
    sampled = candidate_count if dual_review_complete else 0
    return {
        "metadata": {
            "title": "Observed shadow refresh closure run results",
            "status": SHADOW_EVALUATION_STATUS,
        },
        "run_id": run_id,
        "captures": {
            "attempted": live_attempted,
            "succeeded": live_succeeded,
            "failed": live_failed,
            "unchanged": 0,
            "changed": live_succeeded,
        },
        "candidates": {
            "generated": candidate_count,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "unsupported": candidate_count if candidate_count else 0,
        },
        "entity_resolution": {"decisions": entity_decisions, "correct": entity_correct},
        "review": {
            "agreements": review_agreements,
            "disagreements": review_disagreements,
            "sampled_candidates": sampled,
            "total_adjudication_minutes": 0,
        },
        "reopening": {"recommended": 0, "true_positives": 0, "false_positives": 0},
        "provenance": {
            "complete_records": digest_count,
            "total_records": max(live_attempted, digest_count),
        },
        "publication": {"reconciliation_errors": 0},
        "model_assistance": {"minutes_saved": 0.0, "errors_introduced": 0},
        "cost_by_source_class": {},
    }


def record_formal_disposition(
    *,
    run_id: str,
    metrics_recommendation: str,
    dual_review_complete: bool,
    owners: list[str],
    residual_checklist: list[dict[str, Any]],
    typed_retry_outcomes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Record GO / NO_GO / WITHHELD without writing a canonical successor.

    Incomplete dual human review forces WITHHELD or NO_GO (never GO).
    """
    if dual_review_complete and metrics_recommendation == "GO":
        disposition = "GO"
    elif dual_review_complete:
        disposition = "NO_GO"
    else:
        # Prefer WITHHELD when the human sample has not completed; NO_GO remains
        # available via metrics_recommendation for threshold failures already observed.
        disposition = "WITHHELD"

    return {
        "metadata": {
            "title": "Formal shadow refresh disposition",
            "recorded_at": utc_now(),
            "status": SHADOW_EVALUATION_STATUS,
            "core_issue": "#43",
            "governance_issue": GOVERNANCE_ISSUE,
            "evaluation_issue": "#43",
        },
        "run_id": run_id,
        "disposition": disposition,
        "metrics_recommendation": metrics_recommendation,
        "dual_review_complete": dual_review_complete,
        "owners": owners,
        "closure_conditions": [
            "REV-SHADOW-A and REV-SHADOW-B record opinions on sampled candidates.",
            "Disagreement and abstention remain on record when present.",
            "Formal GO only after dual review plus owner recording; software refuses forged GO.",
            "No canonical observatory successor is written from this shadow evaluation.",
            f"Canonical AUTHORIZED/PUBLISHED gates remain deferred to {GOVERNANCE_ISSUE}.",
        ],
        "residual_checklist": residual_checklist,
        "typed_retry_outcomes": typed_retry_outcomes or [],
        "withheld_claims": [
            "This disposition does not authorize AUTHORIZED or PUBLISHED successor gates (#41).",
            "Capture digests prove retrieval bytes only and do not establish substantive truth.",
            "Claimed local reviewer profiles are not authenticated identities.",
            "Unresolved retrieval access was not converted into FAIL findings.",
            f"Core engineering completeness for #43 does not complete governance under {GOVERNANCE_ISSUE}.",
        ],
        "canonical_successor_written": False,
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def compute_closure_metrics(run_results: dict[str, Any], *, generated_by: str) -> dict[str, Any]:
    return compute_go_no_go_metrics(
        run_results,
        generated_at=utc_now(),
        generated_by=generated_by,
    )


def build_public_closure_summary(
    *,
    run_id: str,
    live_counts: dict[str, Any],
    capture_digests: list[dict[str, Any]],
    typed_retry_outcomes: list[dict[str, Any]],
    candidate_count: int,
    dual_review_complete: bool,
    metrics_recommendation: str,
    formal_disposition: str,
) -> dict[str, Any]:
    return {
        "metadata": {
            "title": "Shadow refresh Wave 2 public closure summary",
            "status": SHADOW_EVALUATION_STATUS,
            "run_id": run_id,
            "evaluation_issue": "#43",
            "governance_issue": GOVERNANCE_ISSUE,
            "boundary": SHADOW_REFRESH_BOUNDARY,
        },
        "network_retrieval": "EXECUTED_LIVE_QUARANTINE_ONLY",
        "live_collection_counts": live_counts,
        "capture_digest_count": len(capture_digests),
        "capture_digests": [
            {
                "source_id": item.get("source_id"),
                "sha256": item.get("sha256"),
                "http_status": item.get("http_status"),
                "size_bytes": item.get("size_bytes"),
            }
            for item in capture_digests
        ],
        "retry_outcomes": [
            {
                "source_id": item.get("source_id"),
                "outcome_type": item.get("outcome_type"),
                "http_status": item.get("http_status"),
                "failure_class": item.get("failure_class"),
                "finding_effect": item.get("finding_effect", "NONE"),
            }
            for item in typed_retry_outcomes
        ],
        "candidate_count": candidate_count,
        "dual_review_complete": dual_review_complete,
        "metrics_recommendation": metrics_recommendation,
        "formal_disposition": formal_disposition,
        "withheld_claims": [
            "Public digests and metrics only; protected capture bodies remain outside git.",
            "Formal disposition does not authorize a canonical observatory successor.",
            "Claimed local reviewer profiles are not authenticated institutional identities.",
            f"Canonical AUTHORIZED/PUBLISHED gates remain deferred to {GOVERNANCE_ISSUE}.",
        ],
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def publisher_mentions_for_sources(
    registry: dict[str, Any],
    source_ids: list[str],
) -> list[dict[str, str]]:
    index = {
        str(record["source_id"]): record
        for record in registry.get("sources", [])
        if isinstance(record, dict) and "source_id" in record
    }
    mentions: list[dict[str, str]] = []
    for source_id in source_ids:
        record = index.get(source_id)
        if not record:
            continue
        publisher = str(record.get("publisher") or "").strip()
        if publisher:
            mentions.append({"source_id": source_id, "mention": publisher})
    return mentions


def content_addressed_run_id(seed: bytes) -> str:
    return f"SHADOW-RUN-202608-WAVE2-{sha256_bytes(seed)[:12]}"
