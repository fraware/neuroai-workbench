from __future__ import annotations

from pathlib import Path
from typing import Any

from .dashboard import write_dashboard_html
from .narrative import write_narrative_markdown
from .pdf import write_pdf_stub
from .query import query_release


def generate_publication_set(release_path: Path, output_dir: Path) -> dict[str, Any]:
    """Generate narrative, dashboard, and PDF-stub products from a canonical release fixture."""
    output_dir.mkdir(parents=True, exist_ok=True)
    query = query_release(release_path)
    narrative = write_narrative_markdown(query, output_dir / "current-state-report.md")
    dashboard = write_dashboard_html(query, output_dir / "observatory-dashboard.html")
    pdf_stub = write_pdf_stub(query, output_dir / "current-state-report.pdf.stub.txt")
    return {
        "release_path": str(release_path),
        "release_sha256": query["release_sha256"],
        "withheld_claims": query["withheld_claims"],
        "products": {
            "narrative_markdown": narrative,
            "dashboard_html": dashboard,
            "pdf_stub": pdf_stub,
        },
        "boundary": "Publication set renders controlled records only.",
    }


def reconcile_formats(query: dict[str, Any], products: dict[str, Any]) -> dict[str, Any]:
    """Cross-format reconciliation stub comparing release identity across generated products."""
    expected = query["release_sha256"]
    checks = {
        "markdown_contains_release_hash": expected
        in Path(products["narrative_markdown"]["output"]).read_text(encoding="utf-8"),
        "html_contains_release_hash": expected
        in Path(products["dashboard_html"]["output"]).read_text(encoding="utf-8"),
        "pdf_stub_contains_release_hash": expected in Path(products["pdf_stub"]["output"]).read_text(encoding="utf-8"),
        "withheld_claims_count_matches": all(
            claim in Path(products["narrative_markdown"]["output"]).read_text(encoding="utf-8")
            for claim in query["withheld_claims"]
        ),
    }
    return {
        "release_sha256": expected,
        "checks": checks,
        "reconciled": all(checks.values()),
        "boundary": "Reconciliation confirms identity projection only.",
    }
