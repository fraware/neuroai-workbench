from __future__ import annotations

from pathlib import Path

from neuroai_workbench.products.dashboard import render_dashboard_html, write_dashboard_html
from neuroai_workbench.products.generate import generate_publication_set, reconcile_formats
from neuroai_workbench.products.narrative import render_narrative_markdown, write_narrative_markdown
from neuroai_workbench.products.pdf import render_pdf_stub
from neuroai_workbench.products.query import query_release

REPO = Path(__file__).resolve().parents[2]
COMPACT = REPO / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"


def test_narrative_and_dashboard_are_deterministic() -> None:
    query = query_release(COMPACT)
    assert render_narrative_markdown(query) == render_narrative_markdown(query)
    assert render_dashboard_html(query) == render_dashboard_html(query)
    assert render_pdf_stub(query) == render_pdf_stub(query)


def test_cross_format_reconciliation(tmp_path: Path) -> None:
    query = query_release(COMPACT)
    report = generate_publication_set(COMPACT, tmp_path)
    reconciliation = reconcile_formats(query, report["products"])
    assert reconciliation["reconciled"] is True
    assert reconciliation["checks"]["markdown_contains_release_hash"] is True
    assert reconciliation["checks"]["html_contains_release_hash"] is True
    assert reconciliation["checks"]["pdf_stub_contains_release_hash"] is True


def test_dashboard_includes_a11y_structure() -> None:
    html = render_dashboard_html(query_release(COMPACT))
    assert '<html lang="en">' in html
    assert "aria-labelledby" in html
    assert "<caption>" in html
    assert 'scope="col"' in html
    assert "not color alone" in html


def test_narrative_preserves_withheld_claims_and_boundary() -> None:
    text = render_narrative_markdown(query_release(COMPACT))
    assert "Withheld claims" in text
    assert "does not upgrade evidence" in text
    assert "No regulatory authorization" in text


def test_write_outputs_match_render(tmp_path: Path) -> None:
    query = query_release(COMPACT)
    md_path = tmp_path / "report.md"
    html_path = tmp_path / "dash.html"
    write_narrative_markdown(query, md_path)
    write_dashboard_html(query, html_path)
    assert md_path.read_text(encoding="utf-8") == render_narrative_markdown(query)
    assert html_path.read_text(encoding="utf-8") == render_dashboard_html(query)
