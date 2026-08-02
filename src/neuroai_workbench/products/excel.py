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


def _render_native_xlsx(query: dict[str, Any]) -> bytes | None:
    try:
        from openpyxl import Workbook  # type: ignore[import-untyped]
    except ImportError:
        return None
    workbook = Workbook()
    # Remove default sheet after creating named sheets.
    default = workbook.active
    first = True
    for sheet_name in sorted(query["rows"]):
        rows = query["rows"][sheet_name]
        if first:
            worksheet = default
            worksheet.title = sheet_name[:31]
            first = False
        else:
            worksheet = workbook.create_sheet(title=sheet_name[:31])
        if not rows:
            worksheet.append(["column"])
            continue
        fieldnames = sorted({key for row in rows for key in row})
        worksheet.append(fieldnames)
        for row in rows:
            worksheet.append([row.get(key, "") for key in fieldnames])
    # Merge format metadata into the existing verification projection sheet.
    # Never create a second "verification" sheet (openpyxl would rename it verification1).
    if "verification" in workbook.sheetnames:
        verification = workbook["verification"]
    else:
        verification = workbook.create_sheet(title="verification")
        verification.append(["field", "value"])
    verification.append(["format", "openpyxl-native-xlsx"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_analytical_workbook_bundle(query: dict[str, Any]) -> bytes:
    """Render native xlsx when openpyxl is installed; otherwise CSV-in-ZIP fallback."""
    native = _render_native_xlsx(query)
    if native is not None:
        return native
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        readme = (
            "NeuroAI analytical workbook bundle (CSV-in-ZIP fallback).\n"
            "Install optional extra 'products' (openpyxl) for native .xlsx.\n"
            f"release_sha256={query['release_sha256']}\n"
        )
        archive.writestr("README.txt", readme)
        archive.writestr(
            "workbook.manifest.json",
            json.dumps(
                {
                    "format": "csv-in-zip-xlsx-fallback",
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
    native = payload[:2] == b"PK" and output.suffix == ".xlsx"
    # Native xlsx is also a zip; detect via openpyxl availability + content type heuristic.
    format_name = "openpyxl-native-xlsx" if _render_native_xlsx(query) is not None else "csv-in-zip-xlsx-fallback"
    del native
    return {
        "output": str(output),
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "format": format_name,
        "boundary": "Workbook sheets are deterministic projections of canonical JSON; no manual master data.",
    }
