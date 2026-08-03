"""Native product-path smoke assertions for hashed CI pins.

These tests require the optional product extras (openpyxl, python-docx, reportlab).
They must not soft-skip: CI installs hashed pins from requirements/constraints.txt so the
native XLSX/DOCX/PDF branches are exercised. Core/default installs remain free of these
extras for end users.

Full-depth sheet coverage for publication queries is asserted in a follow-on change once
query/docx/pdf depth scaffolding lands; this module only locks the native container path.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import openpyxl  # noqa: F401 — required native extra; do not soft-skip
import reportlab  # noqa: F401 — required native extra; do not soft-skip
from docx import Document
from openpyxl import load_workbook

from neuroai_workbench.products.docx import write_docx
from neuroai_workbench.products.excel import render_analytical_workbook_bundle, write_analytical_workbook_bundle
from neuroai_workbench.products.pdf import write_pdf
from neuroai_workbench.products.query import query_release

REPO = Path(__file__).resolve().parents[2]
COMPACT = REPO / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"


def test_native_workbook_has_single_verification_sheet() -> None:
    query = query_release(COMPACT, depth="full", limit=None)
    payload = render_analytical_workbook_bundle(query)
    workbook = load_workbook(io.BytesIO(payload))
    assert "verification" in workbook.sheetnames
    assert "verification1" not in workbook.sheetnames
    verification_like = [name for name in workbook.sheetnames if name.startswith("verification")]
    assert verification_like == ["verification"]
    flat = " ".join(
        str(value) for row in workbook["verification"].iter_rows(values_only=True) for value in row if value is not None
    )
    assert query["release_sha256"] in flat


def test_native_workbook_write_round_trip(tmp_path: Path) -> None:
    query = query_release(COMPACT, depth="full", limit=None)
    output = tmp_path / "analytical.xlsx"
    meta = write_analytical_workbook_bundle(query, output)
    assert output.is_file()
    assert meta["sha256"]
    workbook = load_workbook(output)
    assert workbook.sheetnames.count("verification") == 1
    assert "verification1" not in workbook.sheetnames


def test_native_docx_is_real_office_container(tmp_path: Path) -> None:
    query = query_release(COMPACT, depth="full", limit=None)
    output = tmp_path / "report.docx"
    write_docx(query, output)
    assert output.is_file()
    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())
    assert "word/document.xml" in names
    document = Document(str(output))
    assert document.paragraphs


def test_native_pdf_is_real_pdf_container(tmp_path: Path) -> None:
    query = query_release(COMPACT, depth="full", limit=None)
    output = tmp_path / "report.pdf"
    write_pdf(query, output)
    raw = output.read_bytes()
    assert raw.startswith(b"%PDF")
    assert b"%%EOF" in raw[-1024:]