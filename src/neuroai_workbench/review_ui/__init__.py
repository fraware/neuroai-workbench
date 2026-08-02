"""Accessible monitoring review UI projections and safe capture rendering."""

from __future__ import annotations

import difflib
import html
from pathlib import Path
from typing import Any, cast

from ..monitoring import (
    ADJUDICATION_DECISIONS,
    MATERIALITY_STATES,
    MONITORING_BOUNDARY,
    REOPENING_EFFECTS,
    load_change_candidate,
    load_snapshot,
    monitoring_status,
    plan_monitoring_run,
)
from ..review_queue import (
    IDENTITY_BOUNDARY,
    QUEUE_ROLES,
    REVIEW_QUEUE_BOUNDARY,
    get_queue_item,
    list_queue_items,
    load_item_opinions,
    review_queue_status,
)
from ..util import safe_join

MAX_DIFF_LINES = 200
MAX_CAPTURE_PREVIEW_BYTES = 64 * 1024

REVIEW_UI_BOUNDARY = (
    "The monitoring review UI projects rebuildable queue and ops-health counts from workspace records. "
    "Rendered capture diffs are escaped for display only; they do not establish authenticity, "
    "completeness, or substantive truth of monitored sources."
)


def escape_html(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def build_line_diff(before: str, after: str, *, context: int = 3) -> list[dict[str, str]]:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    diff = difflib.unified_diff(before_lines, after_lines, lineterm="", n=context)
    lines: list[dict[str, str]] = []
    for raw in diff:
        if len(lines) >= MAX_DIFF_LINES:
            lines.append({"kind": "truncated", "text": "… diff truncated for local preview …"})
            break
        if raw.startswith("+++") or raw.startswith("---"):
            kind = "meta"
        elif raw.startswith("@@"):
            kind = "hunk"
        elif raw.startswith("+"):
            kind = "add"
        elif raw.startswith("-"):
            kind = "remove"
        else:
            kind = "context"
        lines.append({"kind": kind, "text": raw})
    return lines


def _read_snapshot_text(workspace: Path, source_id: str, snapshot_id: str) -> tuple[str, dict[str, Any]]:
    manifest = load_snapshot(workspace, source_id, snapshot_id)
    content_path = safe_join(workspace, str(manifest["stored_path"]))
    data = content_path.read_bytes()
    if len(data) > MAX_CAPTURE_PREVIEW_BYTES:
        preview = data[:MAX_CAPTURE_PREVIEW_BYTES].decode("utf-8", errors="replace")
        preview += f"\n… truncated after {MAX_CAPTURE_PREVIEW_BYTES} bytes …"
    else:
        preview = data.decode("utf-8", errors="replace")
    return preview, manifest


def build_capture_diff(workspace: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    source_id = str(candidate["source_id"])
    snapshot_ids = [str(item) for item in candidate.get("source_snapshot_ids", [])]
    if not snapshot_ids:
        return {
            "available": False,
            "reason": "No linked snapshots",
            "lines": [],
            "sandbox_mode": "text-only",
            "boundary": REVIEW_UI_BOUNDARY,
        }

    if len(snapshot_ids) == 1:
        text, manifest = _read_snapshot_text(workspace, source_id, snapshot_ids[0])
        return {
            "available": True,
            "mode": "single_snapshot",
            "snapshot_ids": snapshot_ids,
            "preview_text": text,
            "preview_sha256": manifest["sha256"],
            "lines": [],
            "sandbox_mode": "text-only",
            "boundary": REVIEW_UI_BOUNDARY,
        }

    older_id, newer_id = snapshot_ids[0], snapshot_ids[1]
    before, older_manifest = _read_snapshot_text(workspace, source_id, older_id)
    after, newer_manifest = _read_snapshot_text(workspace, source_id, newer_id)
    return {
        "available": True,
        "mode": "snapshot_pair",
        "snapshot_ids": snapshot_ids,
        "older_sha256": older_manifest["sha256"],
        "newer_sha256": newer_manifest["sha256"],
        "lines": build_line_diff(before, after),
        "sandbox_mode": "text-only",
        "boundary": REVIEW_UI_BOUNDARY,
    }


def adjudication_fields() -> list[dict[str, Any]]:
    return [
        {"name": "decision", "label": "Decision", "control": "select", "required": True, "options": sorted(ADJUDICATION_DECISIONS)},
        {"name": "change_class", "label": "Change class", "control": "text", "required": False, "help": "Required when decision is ACCEPT."},
        {"name": "materiality", "label": "Materiality", "control": "select", "required": True, "options": sorted(MATERIALITY_STATES)},
        {"name": "reopening_effect", "label": "Reopening effect", "control": "select", "required": True, "options": sorted(REOPENING_EFFECTS)},
        {"name": "rationale", "label": "Rationale", "control": "textarea", "required": True},
        {"name": "decided_by", "label": "Decided by (local profile)", "control": "profile", "required": True, "help": IDENTITY_BOUNDARY},
    ]


def reviewer_profile_fields() -> list[dict[str, Any]]:
    return [
        {"name": "profile_id", "label": "Profile ID", "control": "text", "required": True},
        {"name": "display_name", "label": "Display name", "control": "text", "required": True},
        {"name": "roles", "label": "Roles", "control": "checkbox-group", "required": True, "options": sorted(QUEUE_ROLES)},
    ]


def ops_health_projection(workspace: Path) -> dict[str, Any]:
    root = workspace if isinstance(workspace, Path) else Path(workspace)
    monitoring: dict[str, Any] | None = None
    plan_counts: dict[str, int] = {"due": 0, "manual": 0, "not_due": 0}
    overdue_source_count = 0
    monitoring_error: str | None = None

    try:
        monitoring = monitoring_status(root)
        plan = plan_monitoring_run(root)
        plan_counts = cast(dict[str, int], plan.get("counts", plan_counts))
        overdue_source_count = sum(1 for item in plan.get("due", []) if int(item.get("overdue_days", 0)) > 0)
    except ValueError as exc:
        monitoring_error = str(exc)

    queue = review_queue_status(root)
    queue_items: list[dict[str, Any]] = []
    if queue.get("initialized"):
        queue_items = list_queue_items(root)

    candidate_counts = {
        "total": int(monitoring.get("candidate_count", 0)) if monitoring else 0,
        "pending": int(monitoring.get("pending_candidate_count", 0)) if monitoring else 0,
        "adjudicated": int(monitoring.get("adjudication_count", 0)) if monitoring else 0,
        "open_queue_items": sum(1 for item in queue_items if item.get("queue_status") == "OPEN"),
        "stale_queue_items": sum(1 for item in queue_items if item.get("queue_status") == "STALE"),
    }

    return {
        "rebuildable": True,
        "source": "projections",
        "monitoring_initialized": monitoring is not None,
        "monitoring_error": monitoring_error,
        "monitoring": monitoring or {},
        "plan_counts": plan_counts,
        "overdue_source_count": overdue_source_count,
        "queue": queue,
        "candidate_counts": candidate_counts,
        "boundaries": {
            "monitoring": MONITORING_BOUNDARY,
            "review_queue": REVIEW_QUEUE_BOUNDARY,
            "review_ui": REVIEW_UI_BOUNDARY,
        },
    }


def queue_item_detail(workspace: Path, item_id: str) -> dict[str, Any]:
    root = workspace if isinstance(workspace, Path) else Path(workspace)
    item = get_queue_item(root, item_id)
    candidate = load_change_candidate(root, str(item["candidate_id"]))
    return {
        "item": item,
        "candidate": candidate,
        "capture_diff": build_capture_diff(root, candidate),
        "opinions": load_item_opinions(root, item_id),
        "adjudication_fields": adjudication_fields(),
        "boundary": REVIEW_UI_BOUNDARY,
    }


def render_health_summary_html(health: dict[str, Any]) -> str:
    counts = health.get("candidate_counts", {})
    plan = health.get("plan_counts", {})
    cards = [
        ("Due sources", plan.get("due", 0)),
        ("Overdue sources", health.get("overdue_source_count", 0)),
        ("Pending candidates", counts.get("pending", 0)),
        ("Open queue items", counts.get("open_queue_items", 0)),
    ]
    parts = ['<section class="ops-health" aria-label="Observatory ops health">']
    for label, value in cards:
        parts.append(
            f'<div class="card"><div class="value">{escape_html(value)}</div>'
            f'<div class="label">{escape_html(label)}</div></div>'
        )
    parts.append("</section>")
    return "".join(parts)


def render_capture_preview_html(capture_diff: dict[str, Any]) -> str:
    if not capture_diff.get("available"):
        return f'<p class="muted">{escape_html(capture_diff.get("reason", "Diff unavailable"))}</p>'
    if capture_diff.get("mode") == "single_snapshot":
        return (
            f'<pre class="capture-preview" data-sandbox="text-only">'
            f'{escape_html(capture_diff.get("preview_text", ""))}</pre>'
        )
    body = "".join(
        f'<span class="diff-{escape_html(line.get("kind", "context"))}">{escape_html(line.get("text", ""))}</span>\n'
        for line in capture_diff.get("lines", [])
    )
    return f'<pre class="capture-preview" data-sandbox="text-only">{body}</pre>'
