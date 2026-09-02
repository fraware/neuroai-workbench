"""Ops-gated live shadow cohort collection helpers.

Live network retrieval requires explicit environment and authorization gates. Artifacts remain
SHADOW_EVALUATION_NOT_CANONICAL. Capture digests prove retrieval bytes only and
do not establish substantive truth, authorization, or a canonical successor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..collector import CollectionScheduler, CollectorConfig, SchedulerConfig
from ..collector.authorization import (
    LIVE_COLLECTION_ENV,
    live_collection_enabled,
    load_live_authorization_from_environment,
)
from ..collector.dns import DnsGuard
from ..collector.http_client import HttpTransport
from ..collector.pinned_transport import PinnedSocketHttpTransport
from ..collector.scan import SCAN_BOUNDARY, ContentSafetyScanner, ensure_quarantine_result_scans
from ..util import load_json, sha256_bytes, utc_now
from .schemas import SHADOW_EVALUATION_STATUS, SHADOW_REFRESH_BOUNDARY

__all__ = ["LIVE_COLLECTION_ENV", "live_collection_enabled"]


def require_live_collection_enabled() -> None:
    if not live_collection_enabled():
        raise PermissionError(
            f"{LIVE_COLLECTION_ENV}=1 is required for live shadow cohort network collection. "
            "CI and default local runs remain network-free. Network capture also requires a "
            "digest-bound collection authorization packet; this environment variable is not a sufficient gate alone."
        )


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def evaluation_collection_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Promote HTTP cohort members into due for a one-shot evaluation retrieval.

    Cadence-based not_due entries are overridden for shadow evaluation only.
    CONTROLLED_LOCAL / no-network items remain in manual and never enter HTTP due.
    """
    due = list(plan.get("due", []))
    manual = list(plan.get("manual", []))
    not_due = list(plan.get("not_due", []))
    promoted: list[dict[str, Any]] = []
    remaining_not_due: list[dict[str, Any]] = []
    for item in not_due:
        url = str(item.get("url") or "")
        if _is_http_url(url) and item.get("network_access_required", True) is not False:
            clone = dict(item)
            clone["evaluation_override"] = "SHADOW_LIVE_FORCE_DUE"
            promoted.append(clone)
        else:
            remaining_not_due.append(item)
    evaluation_due = due + promoted
    return {
        **plan,
        "due": evaluation_due,
        "manual": manual,
        "not_due": remaining_not_due,
        "counts": {
            "due": len(evaluation_due),
            "manual": len(manual),
            "not_due": len(remaining_not_due),
            "evaluation_promoted": len(promoted),
        },
        "status": SHADOW_EVALUATION_STATUS,
        "live_evaluation": True,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def default_live_collector_config() -> CollectorConfig:
    configuration_hash = sha256_bytes(
        b"neuroai-live-shadow-collector-v1|requests_per_host_per_minute=12|max_redirects=8"
    )
    return CollectorConfig(
        collector_version="0.3.0.dev0-live-shadow",
        configuration_hash=configuration_hash,
        requests_per_host_per_minute=12,
        max_redirects=8,
        connect_timeout_seconds=15.0,
        read_timeout_seconds=45.0,
        total_timeout_seconds=90.0,
        max_attempts=2,
    )


def run_live_cohort_collection(
    *,
    plan: dict[str, Any],
    registry: dict[str, Any],
    registry_sha256: str,
    quarantine_root: Path,
    collector_config: CollectorConfig | None = None,
    transport: HttpTransport | None = None,
    dns_guard: DnsGuard | None = None,
    content_safety_scanner: ContentSafetyScanner | None = None,
) -> dict[str, Any]:
    """Execute allowlisted live HTTP collection for an evaluation plan.

    Writes quarantine-only under ``quarantine_root``. Does not hand off into
    monitoring and does not authorize canonical publication.

    ``transport`` / ``dns_guard`` / ``content_safety_scanner`` are injectable for
    offline unit tests. Live ops defaults are ``PinnedSocketHttpTransport``, the real
    ``DnsGuard``, and the fail-closed content-safety scanner. Live execution additionally
    requires a digest-bound authorization packet in the controlled authorization
    environment variable.
    """
    require_live_collection_enabled()
    authorization = load_live_authorization_from_environment()
    evaluation_plan = evaluation_collection_plan(plan)
    config = collector_config or default_live_collector_config()
    quarantine_root.mkdir(parents=True, exist_ok=True)
    source_index = {
        str(record["source_id"]): record
        for record in registry.get("sources", [])
        if isinstance(record, dict) and "source_id" in record
    }
    scheduler = CollectionScheduler(
        collector_config=config,
        transport=transport or PinnedSocketHttpTransport(),
        quarantine_root=quarantine_root,
        scheduler_config=SchedulerConfig(
            collection_enabled=True,
            handoff_enabled=False,
            include_manual_sources=False,
        ),
        dns_guard=dns_guard or DnsGuard(),
    )
    collection_run = scheduler.run_plan(
        evaluation_plan,
        registry_sha256=registry_sha256,
        source_index=source_index,
    )
    scan_records = ensure_quarantine_result_scans(
        quarantine_root,
        scanner=content_safety_scanner,
    )
    content_safety = _public_scan_summary(scan_records)
    digests = _collect_public_digests(quarantine_root)
    failures = _collect_public_failures(quarantine_root)
    failure_by_id = {item.get("failure_id"): item for item in failures if item.get("failure_id")}
    public_outcomes = []
    for item in collection_run.get("outcomes", []):
        entry = {
            "source_id": item.get("source_id"),
            "adapter_id": item.get("adapter_id"),
            "status": item.get("status"),
            "record_id": item.get("record_id"),
            "reason": item.get("reason"),
            "failure_class": item.get("failure_class"),
        }
        if entry["status"] == "FAILURE" and entry.get("record_id") in failure_by_id:
            detail = failure_by_id[entry["record_id"]]
            entry["failure_class"] = detail.get("failure_class") or entry.get("failure_class")
            entry["message"] = detail.get("message")
        public_outcomes.append(entry)
    return {
        "metadata": {
            "title": "Observed live shadow cohort collection run",
            "status": SHADOW_EVALUATION_STATUS,
            "executed_at": utc_now(),
            "authorization": {
                "authorization_id": authorization["authorization_id"],
                "authorization_sha256": authorization["authorization_sha256"],
                "authorized_by": authorization["authorized_by"],
                "authorized_at": authorization["authorized_at"],
                "purpose": authorization["purpose"],
                "identity_boundary": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
            },
            "boundary": (
                "Live capture proves retrieval into quarantine only. "
                "The local authorization packet records claimed permission for this controlled live operation; "
                "content-safety scan state is quarantine custody metadata and does not establish a substantive CLEAN claim. "
                "Neither capture, authorization, nor scan state establishes substantive truth, legal authorization, "
                "deployment readiness, or a canonical observatory successor."
            ),
        },
        "evaluation_plan_counts": evaluation_plan["counts"],
        "collection_run": {
            "run_id": collection_run.get("run_id"),
            "status": collection_run.get("status"),
            "counts": collection_run.get("counts"),
            "outcomes": public_outcomes,
        },
        "capture_digests": digests,
        "failure_summaries": failures,
        "content_safety": content_safety,
        "collector": {
            "collector_version": config.collector_version,
            "configuration_hash": config.configuration_hash,
            "handoff_enabled": False,
            "default_transport": "PinnedSocketHttpTransport" if transport is None else "INJECTED_TRANSPORT",
            "dns_guard": "DnsGuard" if dns_guard is None else "INJECTED_DNS_GUARD",
        },
        "status": SHADOW_EVALUATION_STATUS,
        "boundary": SHADOW_REFRESH_BOUNDARY,
    }


def observed_run_results_from_live(
    live_package: dict[str, Any],
    *,
    run_id: str,
    planned_total: int,
) -> dict[str, Any]:
    """Map live collection counts into shadow go/no-go run-results shape."""
    counts = live_package.get("collection_run", {}).get("counts", {})
    succeeded = int(counts.get("succeeded", 0))
    failed = int(counts.get("failed", 0))
    skipped = int(counts.get("skipped", 0))
    attempted = int(counts.get("total", succeeded + failed + skipped))
    digest_count = len(live_package.get("capture_digests", []))
    # First live shadow run has no prior capture baseline; treat successes as changed retrievals.
    return {
        "metadata": {
            "title": "Observed live shadow refresh run results",
            "status": SHADOW_EVALUATION_STATUS,
        },
        "run_id": run_id,
        "captures": {
            "attempted": attempted,
            "succeeded": succeeded,
            "failed": failed,
            "unchanged": 0,
            "changed": succeeded,
        },
        "candidates": {
            "generated": 0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "unsupported": 0,
        },
        "entity_resolution": {"decisions": 0, "correct": 0},
        "review": {
            "agreements": 0,
            "disagreements": 0,
            "sampled_candidates": 0,
            "total_adjudication_minutes": 0,
        },
        "reopening": {"recommended": 0, "true_positives": 0, "false_positives": 0},
        "provenance": {
            "complete_records": digest_count,
            "total_records": max(planned_total, attempted),
        },
        "publication": {"reconciliation_errors": 0},
        "model_assistance": {"minutes_saved": 0.0, "errors_introduced": 0},
        "cost_by_source_class": {},
    }


def _public_scan_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    state_counts: dict[str, int] = {}
    scanner_ids: set[str] = set()
    existing = 0
    created = 0
    for record in records:
        state = str(record["state"])
        state_counts[state] = state_counts.get(state, 0) + 1
        scanner_ids.add(str(record["scanner_id"]))
        if record.get("existing_scan_verified") is True:
            existing += 1
        else:
            created += 1
    return {
        "scope": "ALL_DURABLE_RESULTS_IN_QUARANTINE_ROOT",
        "durable_result_records_checked": len(records),
        "scans_created": created,
        "existing_scans_verified": existing,
        "state_counts": dict(sorted(state_counts.items())),
        "scanner_ids": sorted(scanner_ids),
        "detail_exposed": False,
        "boundary": SCAN_BOUNDARY,
    }


def _collect_public_digests(quarantine_root: Path) -> list[dict[str, Any]]:
    results_dir = quarantine_root / "results"
    if not results_dir.is_dir():
        return []
    digests: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            record = load_json(path)
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(record, dict):
            continue
        digests.append(
            {
                "source_id": record.get("source_id"),
                "result_id": record.get("result_id"),
                "sha256": record.get("sha256"),
                "http_status": record.get("http_status"),
                "size_bytes": record.get("size_bytes"),
                "media_type": record.get("media_type"),
                "final_url": record.get("final_url"),
                "evidence_state": record.get("evidence_state"),
            }
        )
    return digests


def _collect_public_failures(quarantine_root: Path) -> list[dict[str, Any]]:
    failures_dir = quarantine_root / "failures"
    if not failures_dir.is_dir():
        return []
    summaries: list[dict[str, Any]] = []
    for path in sorted(failures_dir.glob("*.json")):
        try:
            record = load_json(path)
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(record, dict):
            continue
        summaries.append(
            {
                "source_id": record.get("source_id"),
                "failure_id": record.get("failure_id"),
                "failure_class": record.get("failure_class"),
                "message": record.get("message"),
                "http_status": record.get("http_status"),
                "requested_url": record.get("requested_url"),
            }
        )
    return summaries
