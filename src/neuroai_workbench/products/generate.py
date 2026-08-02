from __future__ import annotations

from pathlib import Path
from typing import Any

from .excel import write_analytical_workbook_bundle
from .query import query_release


def generate_publication_set(release_path: Path, output_dir: Path) -> dict[str, Any]:
    """Generate the analytical workbook product from a canonical release fixture."""
    output_dir.mkdir(parents=True, exist_ok=True)
    query = query_release(release_path)
    workbook = write_analytical_workbook_bundle(query, output_dir / "analytical-workbook.xlsx.stub.zip")
    return {
        "release_path": str(release_path),
        "release_sha256": query["release_sha256"],
        "products": {"analytical_workbook": workbook},
        "withheld_claims": query["withheld_claims"],
        "boundary": "Product generation renders controlled records only.",
    }
