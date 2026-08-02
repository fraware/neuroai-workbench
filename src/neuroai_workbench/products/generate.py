from __future__ import annotations

from pathlib import Path
from typing import Any

from .dashboard import write_dashboard_html
from .docx import write_docx
from .excel import write_analytical_workbook_bundle
from .narrative import write_narrative_markdown
from .pdf import write_pdf
from .query import query_release


def generate_publication_set(
    release_path: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Generate workbook, narrative, dashboard, docx, and PDF products from a canonical release."""
    output_dir.mkdir(parents=True, exist_ok=True)
    query = query_release(release_path, limit=limit)
    workbook_name = "analytical-workbook.xlsx" if query.get("limit") is None else "analytical-workbook.xlsx"
    workbook = write_analytical_workbook_bundle(query, output_dir / workbook_name)
    narrative = write_narrative_markdown(query, output_dir / "current-state-report.md")
    dashboard = write_dashboard_html(query, output_dir / "observatory-dashboard.html")
    pdf = write_pdf(query, output_dir / "current-state-report.pdf")
    docx = write_docx(query, output_dir / "current-state-report.docx")
    products = {
        "analytical_workbook": workbook,
        "narrative_markdown": narrative,
        "dashboard_html": dashboard,
        "pdf": pdf,
        "docx": docx,
        # Backward-compatible alias used by older reconciliation callers.
        "pdf_stub": pdf,
    }
    return {
        "release_path": str(release_path),
        "release_sha256": query["release_sha256"],
        "withheld_claims": query["withheld_claims"],
        "products": products,
        "boundary": "Publication set renders controlled records only.",
    }


def reconcile_formats(query: dict[str, Any], products: dict[str, Any]) -> dict[str, Any]:
    """Cross-format reconciliation comparing release identity across generated products."""
    expected = query["release_sha256"]
    narrative_text = Path(products["narrative_markdown"]["output"]).read_text(encoding="utf-8")
    pdf_path = Path(products.get("pdf", products.get("pdf_stub"))["output"])
    pdf_bytes = pdf_path.read_bytes()
    pdf_contains = expected.encode("utf-8") in pdf_bytes or expected in pdf_bytes.decode("utf-8", errors="ignore")
    docx_ok = Path(products["docx"]["output"]).is_file() if "docx" in products else True
    checks = {
        "markdown_contains_release_hash": expected in narrative_text,
        "html_contains_release_hash": expected
        in Path(products["dashboard_html"]["output"]).read_text(encoding="utf-8"),
        "pdf_contains_release_hash": pdf_contains,
        "workbook_bundle_exists": Path(products["analytical_workbook"]["output"]).is_file(),
        "docx_exists": docx_ok,
        "withheld_claims_count_matches": all(claim in narrative_text for claim in query["withheld_claims"]),
    }
    return {
        "release_sha256": expected,
        "checks": checks,
        "reconciled": all(checks.values()),
        "boundary": "Reconciliation confirms identity projection only.",
    }
