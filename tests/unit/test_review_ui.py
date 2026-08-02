from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.monitoring import (
    create_change_candidate,
    initialize_monitoring,
    record_snapshot,
)
from neuroai_workbench.review_queue import initialize_review_queue, rebuild_queue_projection
from neuroai_workbench.review_ui import (
    adjudication_fields,
    build_capture_diff,
    build_line_diff,
    escape_html,
    ops_health_projection,
    render_capture_preview_html,
    render_health_summary_html,
)
from neuroai_workbench.util import atomic_write_json


XSS_PAYLOAD = '<script>alert("xss")</script><img src=x onerror=alert(1)>'


def source_record(source_id: str = "SRC-0001") -> dict[str, object]:
    return {
        "monitor_id": "MON-SRC-0001",
        "source_id": source_id,
        "url": "https://example.org/source",
        "publisher": "Example source",
        "source_class": "REGULATORY_RECORD",
        "cadence": "WEEKLY",
        "last_successful_retrieval": "2026-07-01",
        "baseline_evidence_state": "CURRENT_SOURCE_RETRIEVED",
        "baseline_verification_state": "CURRENT_VERIFIED",
        "baseline_claim_boundary": "Human adjudication controls every substantive effect.",
        "network_access_required": True,
        "current_status": "BASELINE_REGISTERED",
        "next_action": "RETRIEVE_AND_COMPARE",
    }


def setup_workspace(tmp_path: Path) -> Path:
    registry = tmp_path / "registry.json"
    atomic_write_json(registry, [source_record()])
    workspace = tmp_path / "workspace"
    initialize_monitoring(workspace, registry)
    initialize_review_queue(workspace, actor="tester")
    return workspace


def test_escape_html_neutralizes_xss_payload() -> None:
    escaped = escape_html(XSS_PAYLOAD)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "onerror=alert(1)" in escaped


def test_build_line_diff_returns_structured_lines() -> None:
    lines = build_line_diff("alpha\nbeta", "alpha\ngamma")
    kinds = {line["kind"] for line in lines}
    assert "remove" in kinds
    assert "add" in kinds


def test_capture_diff_escapes_xss_in_html_render(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    snapshot = record_snapshot(workspace, "SRC-0001", XSS_PAYLOAD.encode("utf-8"), media_type="text/html")
    candidate = create_change_candidate(
        workspace,
        "SRC-0001",
        snapshot["snapshot_id"],
        summary=f"Detected change with payload {XSS_PAYLOAD}",
    )
    capture = build_capture_diff(workspace, candidate)
    html = render_capture_preview_html(capture)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_ops_health_projection_counts(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    first = record_snapshot(workspace, "SRC-0001", b"alpha", media_type="text/plain")
    second = record_snapshot(workspace, "SRC-0001", b"beta", media_type="text/plain")
    create_change_candidate(
        workspace,
        "SRC-0001",
        second["snapshot_id"],
        previous_snapshot_id=first["snapshot_id"],
    )
    health = ops_health_projection(workspace)
    assert health["rebuildable"] is True
    assert health["monitoring_initialized"] is True
    assert health["candidate_counts"]["pending"] == 1
    assert health["candidate_counts"]["open_queue_items"] == len(rebuild_queue_projection(workspace))


def test_ops_health_without_monitoring_reports_error(tmp_path: Path) -> None:
    workspace = tmp_path / "empty"
    workspace.mkdir()
    health = ops_health_projection(workspace)
    assert health["monitoring_initialized"] is False
    assert health["monitoring_error"]


def test_render_health_summary_html_is_numeric_only(tmp_path: Path) -> None:
    workspace = setup_workspace(tmp_path)
    html = render_health_summary_html(ops_health_projection(workspace))
    assert "<script>" not in html
    assert "ops-health" in html


def test_adjudication_fields_match_schema_concepts() -> None:
    names = {field["name"] for field in adjudication_fields()}
    assert names == {
        "decision",
        "change_class",
        "materiality",
        "reopening_effect",
        "rationale",
        "decided_by",
    }


@pytest.mark.parametrize(
    "payload",
    [
        XSS_PAYLOAD,
        'javascript:alert("x")',
        "<svg/onload=alert(1)>",
    ],
)
def test_xss_fixtures_do_not_render_raw_markup(payload: str) -> None:
    html = render_capture_preview_html(
        {
            "available": True,
            "mode": "single_snapshot",
            "preview_text": payload,
        }
    )
    assert "<script" not in html.lower()
    assert "<svg" not in html.lower()
    assert payload not in html
