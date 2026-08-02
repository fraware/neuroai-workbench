from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from ..util import atomic_write_bytes, sha256_bytes
from .query import query_release

__all__ = ["query_release", "render_analytical_workbook_bundle", "write_analytical_workbook_bundle"]


def _sheet_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "column\n"
    buffer = io.StringIO()
    fieldnames = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return buffer.getvalue()


def render_analytical_workbook_bundle(query: dict[str, Any]) -> bytes:
    """Render a deterministic CSV-in-ZIP workbook bundle (xlsx stub without openpyxl)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        readme = (
            "NeuroAI analytical workbook bundle (CSV-in-ZIP xlsx stub).\n"
            "Native .xlsx generation requires optional openpyxl; this bundle preserves deterministic sheets.\n"
            f"release_sha256={query['release_sha256']}\n"
        )
        archive.writestr("README.txt", readme)
        archive.writestr(
            "workbook.manifest.json",
            json.dumps(
                {
                    "format": "csv-in-zip-xlsx-stub",
                    "release_sha256": query["release_sha256"],
                    "sheets": sorted(query["rows"]),
                    "withheld_claims": query["withheld_claims"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        for sheet_name in sorted(query["rows"]):
            archive.writestr(f"sheets/{sheet_name}.csv", _sheet_to_csv(query["rows"][sheet_name]))
    return buffer.getvalue()


def write_analytical_workbook_bundle(query: dict[str, Any], output: Path) -> dict[str, Any]:
    payload = render_analytical_workbook_bundle(query)
    atomic_write_bytes(output, payload)
    return {
        "output": str(output),
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "format": "csv-in-zip-xlsx-stub",
        "boundary": "Workbook sheets are deterministic projections of canonical JSON; no manual master data.",
    }
