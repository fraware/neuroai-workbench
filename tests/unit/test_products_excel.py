from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.products.excel import render_analytical_workbook_bundle, write_analytical_workbook_bundle
from neuroai_workbench.products.generate import generate_publication_set
from neuroai_workbench.products.query import query_release

REPO = Path(__file__).resolve().parents[2]
COMPACT = REPO / "examples" / "observatory" / "canonical_successor_snapshot_v1.7.json"
FULL = REPO / "examples" / "observatory" / "evidence_depth_release_v1.4.json"


def test_workbook_render_is_deterministic() -> None:
    query = query_release(COMPACT)
    first = render_analytical_workbook_bundle(query)
    second = render_analytical_workbook_bundle(query)
    assert first == second
    assert len(first) > 0


def test_workbook_includes_release_identity() -> None:
    query = query_release(COMPACT)
    payload = render_analytical_workbook_bundle(query)
    try:
        from openpyxl import load_workbook
    except ImportError:
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert "sheets/verification.csv" in archive.namelist()
            verification = archive.read("sheets/verification.csv").decode("utf-8")
            assert query["release_sha256"] in verification
        return
    workbook = load_workbook(__import__("io").BytesIO(payload))
    assert "verification" in workbook.sheetnames
    flat = [item for row in workbook["verification"].iter_rows(values_only=True) for item in row]
    assert query["release_sha256"] in flat


def test_query_preview_limit_and_release_unbounded() -> None:
    preview = query_release(FULL, limit=50)
    release = json.loads(FULL.read_text(encoding="utf-8"))
    assert len(preview["rows"]["organizations"]) == min(50, len(release.get("organizations", [])))
    assert len(preview["rows"]["sources"]) == min(50, len(release.get("sources", [])))
    full = query_release(FULL, limit=None)
    assert len(full["rows"]["organizations"]) == len(release.get("organizations", []))
    assert len(full["rows"]["sources"]) == len(release.get("sources", []))


def test_generate_publication_set_writes_workbook(tmp_path: Path) -> None:
    report = generate_publication_set(COMPACT, tmp_path, limit=None)
    workbook_path = tmp_path / "analytical-workbook.xlsx"
    assert workbook_path.is_file()
    assert report["products"]["analytical_workbook"]["sha256"]
    assert report["release_sha256"] == query_release(COMPACT, limit=None)["release_sha256"]
    assert (tmp_path / "current-state-report.docx").is_file()
    assert (tmp_path / "current-state-report.pdf").is_file()


def test_write_workbook_matches_render(tmp_path: Path) -> None:
    query = query_release(COMPACT)
    output = tmp_path / "book.xlsx"
    meta = write_analytical_workbook_bundle(query, output)
    assert output.is_file()
    assert meta["bytes"] == output.stat().st_size
    assert meta["format"] in {"openpyxl-native-xlsx", "csv-in-zip-xlsx-fallback"}
    if meta["format"] == "csv-in-zip-xlsx-fallback":
        import zipfile

        with zipfile.ZipFile(output) as archive:
            assert "sheets/verification.csv" in archive.namelist()
        return
    from openpyxl import load_workbook

    workbook = load_workbook(output)
    assert "verification" in workbook.sheetnames
