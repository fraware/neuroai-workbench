from __future__ import annotations

import io
import json
import zipfile
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


def test_workbook_includes_verification_sheet() -> None:
    query = query_release(COMPACT)
    payload = render_analytical_workbook_bundle(query)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
        assert "sheets/verification.csv" in names
        manifest = json.loads(archive.read("workbook.manifest.json"))
        assert manifest["release_sha256"] == query["release_sha256"]
        verification = archive.read("sheets/verification.csv").decode("utf-8")
        assert query["release_sha256"] in verification


def test_query_row_counts_match_canonical_release() -> None:
    query = query_release(FULL)
    release = json.loads(FULL.read_text(encoding="utf-8"))
    assert len(query["rows"]["organizations"]) == min(50, len(release.get("organizations", [])))
    assert len(query["rows"]["sources"]) == min(50, len(release.get("sources", [])))


def test_generate_publication_set_writes_workbook(tmp_path: Path) -> None:
    report = generate_publication_set(COMPACT, tmp_path)
    workbook_path = tmp_path / "analytical-workbook.xlsx.stub.zip"
    assert workbook_path.is_file()
    assert report["products"]["analytical_workbook"]["sha256"]
    assert report["release_sha256"] == query_release(COMPACT)["release_sha256"]


def test_write_workbook_matches_render(tmp_path: Path) -> None:
    query = query_release(COMPACT)
    output = tmp_path / "book.zip"
    meta = write_analytical_workbook_bundle(query, output)
    assert output.read_bytes() == render_analytical_workbook_bundle(query)
    assert meta["format"] == "csv-in-zip-xlsx-stub"
