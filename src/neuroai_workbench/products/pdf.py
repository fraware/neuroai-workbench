from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ..util import atomic_write_bytes, sha256_bytes
from .query import iter_appendix_sheets

_CELL_LIMIT = 120


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) > _CELL_LIMIT:
        return text[: _CELL_LIMIT - 1] + "…"
    return text


def _table_data(rows: list[dict[str, Any]]) -> list[list[str]]:
    fieldnames = sorted({key for row in rows for key in row})
    matrix = [fieldnames]
    for row in rows:
        matrix.append([_stringify(row.get(key, "")) for key in fieldnames])
    return matrix


def render_pdf(query: dict[str, Any]) -> bytes | None:
    try:
        from reportlab.lib import colors  # type: ignore[import-untyped]
        from reportlab.lib.enums import TA_LEFT  # type: ignore[import-untyped]
        from reportlab.lib.pagesizes import landscape, letter  # type: ignore[import-untyped]
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
        from reportlab.lib.units import inch  # type: ignore[import-untyped]
        from reportlab.platypus import (  # type: ignore[import-untyped]
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        return None

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        invariant=1,
    )
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    heading_style = styles["Heading2"]
    subheading_style = styles["Heading3"]
    body_style = ParagraphStyle(
        "BodyWrap",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        alignment=TA_LEFT,
    )
    small_style = ParagraphStyle(
        "SmallWrap",
        parent=body_style,
        fontSize=7,
        leading=9,
    )

    story: list[Any] = [
        Paragraph("NeuroAI observatory publication", title_style),
        Paragraph(
            "Generators are views: this PDF restates canonical JSON projections only. "
            "It does not establish scientific truth, regulatory authorization, or institutional authority.",
            body_style,
        ),
        Spacer(1, 8),
        Paragraph(f"release_sha256: {query['release_sha256']}", body_style),
        Paragraph(f"release_version: {query['metadata'].get('version', 'UNRESOLVED')}", body_style),
        Paragraph(f"release_kind: {query.get('release_kind', 'UNRESOLVED')}", body_style),
        Paragraph(f"query_depth: {query.get('depth', 'UNRESOLVED')}", body_style),
        Spacer(1, 10),
        Paragraph("Withheld claims", heading_style),
    ]
    for claim in query["withheld_claims"]:
        story.append(Paragraph(f"• {_stringify(claim)}", body_style))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Release summary", heading_style))
    for row in query["rows"].get("release_summary", []):
        story.append(
            Paragraph(
                ", ".join(f"{key}={_stringify(row.get(key))}" for key in sorted(row)),
                body_style,
            )
        )

    counts_key = "successor_counts" if "successor_counts" in query["rows"] else "coverage_counts"
    if counts_key in query["rows"]:
        story.append(Paragraph("Counts", heading_style))
        for row in query["rows"][counts_key]:
            story.append(Paragraph(f"• {_stringify(row.get('metric'))}: {_stringify(row.get('value'))}", body_style))

    appendices = iter_appendix_sheets(query)
    if appendices:
        story.append(PageBreak())
        story.append(Paragraph("Publication appendices", heading_style))
        story.append(
            Paragraph(
                "Tables below project first-class query sheets present on the canonical release. "
                "Missing canonical sections are omitted.",
                body_style,
            )
        )
        usable_width = landscape(letter)[0] - 1.2 * inch
        for index, (sheet_name, rows) in enumerate(appendices):
            if index > 0:
                story.append(PageBreak())
            story.append(Paragraph(sheet_name.replace("_", " "), subheading_style))
            story.append(Paragraph(f"Rows: {len(rows)}", body_style))
            matrix = _table_data(rows)
            col_count = max(len(matrix[0]), 1)
            col_width = usable_width / col_count
            wrapped: list[list[Any]] = []
            for row in matrix:
                wrapped.append(
                    [
                        Paragraph(_stringify(cell).replace("&", "&amp;").replace("<", "&lt;"), small_style)
                        for cell in row
                    ]
                )
            table = Table(wrapped, colWidths=[col_width] * col_count, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            story.append(table)

    story.append(Spacer(1, 12))
    story.append(Paragraph("Boundary", heading_style))
    story.append(
        Paragraph(
            "Boundary: PDF restates canonical JSON projections only; generators are views.",
            body_style,
        )
    )

    def _disable_compression(canvas, _doc) -> None:  # noqa: ANN001
        canvas.setPageCompression(0)

    document.build(story, onFirstPage=_disable_compression, onLaterPages=_disable_compression)
    return bytes(buffer.getvalue())


def render_pdf_stub(query: dict[str, Any]) -> str:
    return (
        "NeuroAI publication PDF stub\n"
        "==============================\n\n"
        "Native PDF generation requires optional reportlab (extra: products).\n"
        f"release_sha256: {query['release_sha256']}\n"
        f"release_version: {query['metadata'].get('version', 'UNRESOLVED')}\n\n"
        "Withheld claims:\n"
        + "".join(f"- {item}\n" for item in query["withheld_claims"])
        + "\nBoundary: PDF stub confirms identity only; it does not establish substantive authority.\n"
    )


def write_pdf(query: dict[str, Any], output: Path) -> dict[str, Any]:
    payload = render_pdf(query)
    if payload is None:
        text = render_pdf_stub(query)
        atomic_write_bytes(output, text.encode("utf-8"))
        return {
            "output": str(output),
            "sha256": sha256_bytes(text.encode("utf-8")),
            "bytes": len(text.encode("utf-8")),
            "format": "pdf-stub-text",
            "limitation": "Native PDF unavailable without optional dependencies.",
            "boundary": "Stub records release identity for reconciliation tests only.",
        }
    atomic_write_bytes(output, payload)
    return {
        "output": str(output),
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "format": "reportlab-native-pdf",
        "boundary": "PDF is a deterministic projection of canonical JSON; no new findings.",
    }


write_pdf_stub = write_pdf
