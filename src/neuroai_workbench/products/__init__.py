"""Deterministic publication products from canonical observatory records."""

from .dashboard import render_dashboard_html, write_dashboard_html
from .generate import generate_publication_set
from .narrative import render_narrative_markdown, write_narrative_markdown
from .pdf import render_pdf_stub, write_pdf_stub
from .query import query_release

__all__ = [
    "generate_publication_set",
    "query_release",
    "render_dashboard_html",
    "render_narrative_markdown",
    "render_pdf_stub",
    "write_dashboard_html",
    "write_narrative_markdown",
    "write_pdf_stub",
]
