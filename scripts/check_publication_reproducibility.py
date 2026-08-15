#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from typing import Any

from neuroai_workbench.products.docx import render_docx
from neuroai_workbench.products.excel import render_analytical_workbook_bundle
from neuroai_workbench.products.pdf import render_pdf

EXPECTED_XLSX_SHA256 = "042d48eda03e6963ea701d105c207261e9286cf9dd6f9670c24f8520f2a37b81"
EXPECTED_DOCX_SHA256: str | None = None
EXPECTED_PDF_SHA256: str | None = None


def _synthetic_query() -> dict[str, Any]:
    release_sha256 = "1" * 64
    return {
        "release_sha256": release_sha256,
        "metadata": {"version": "synthetic-v1"},
        "release_kind": "synthetic",
        "depth": "full",
        "withheld_claims": ["synthetic fixture"],
        "rows": {
            "empty": [],
            "organizations": [
                {
                    "canonical_name": "Example Neurotech",
                    "organization_id": "org-example",
                    "verification_state": "verified",
                }
            ],
            "verification": [{"field": "release_sha256", "value": release_sha256}],
        },
    }


def _digest(label: str, first: bytes, second: bytes, expected: str | None) -> bool:
    if first != second:
        print(f"ERROR: repeated {label} renders are not byte-identical", file=sys.stderr)
        return False
    digest = hashlib.sha256(first).hexdigest()
    print(f"publication-reproducibility-{label}-sha256={digest}")
    if expected is not None and digest != expected:
        print(f"ERROR: {label} fingerprint drifted: {digest} != {expected}", file=sys.stderr)
        return False
    return True


def main() -> int:
    query = _synthetic_query()

    xlsx_first = render_analytical_workbook_bundle(query)
    xlsx_second = render_analytical_workbook_bundle(query)
    try:
        with zipfile.ZipFile(io.BytesIO(xlsx_first), "r") as archive:
            xlsx_names = set(archive.namelist())
    except zipfile.BadZipFile:
        print("ERROR: workbook renderer did not emit a ZIP package", file=sys.stderr)
        return 1
    if not {"[Content_Types].xml", "xl/workbook.xml"} <= xlsx_names:
        print("ERROR: native XLSX dependency is unavailable in the supported-runtime gate", file=sys.stderr)
        return 1

    docx_first = render_docx(query)
    docx_second = render_docx(query)
    if docx_first is None or docx_second is None:
        print("ERROR: native DOCX dependency is unavailable in the supported-runtime gate", file=sys.stderr)
        return 1
    try:
        with zipfile.ZipFile(io.BytesIO(docx_first), "r") as archive:
            docx_names = set(archive.namelist())
    except zipfile.BadZipFile:
        print("ERROR: DOCX renderer did not emit an OPC ZIP package", file=sys.stderr)
        return 1
    if not {"[Content_Types].xml", "word/document.xml", "docProps/core.xml"} <= docx_names:
        print("ERROR: DOCX package is missing required structural members", file=sys.stderr)
        return 1

    pdf_first = render_pdf(query)
    pdf_second = render_pdf(query)
    if pdf_first is None or pdf_second is None:
        print("ERROR: native PDF dependency is unavailable in the supported-runtime gate", file=sys.stderr)
        return 1
    if not pdf_first.startswith(b"%PDF"):
        print("ERROR: PDF renderer did not emit a PDF document", file=sys.stderr)
        return 1

    ok = True
    ok &= _digest("xlsx", xlsx_first, xlsx_second, EXPECTED_XLSX_SHA256)
    ok &= _digest("docx", docx_first, docx_second, EXPECTED_DOCX_SHA256)
    ok &= _digest("pdf", pdf_first, pdf_second, EXPECTED_PDF_SHA256)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
