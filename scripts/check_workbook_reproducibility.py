#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from typing import Any

from neuroai_workbench.products import excel as excel_module

# Calibrated on the complete Python 3.10-3.14 supported-runtime matrix. A reviewed
# serializer change may intentionally update this value only with cross-version evidence.
EXPECTED_NATIVE_SHA256 = "042d48eda03e6963ea701d105c207261e9286cf9dd6f9670c24f8520f2a37b81"


def _synthetic_query() -> dict[str, Any]:
    release_sha256 = "1" * 64
    return {
        "release_sha256": release_sha256,
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
            "verification": [
                {"field": "release_sha256", "value": release_sha256},
            ],
        },
    }


def main() -> int:
    query = _synthetic_query()
    first = excel_module.render_analytical_workbook_bundle(query)
    second = excel_module.render_analytical_workbook_bundle(query)
    if first != second:
        print("ERROR: repeated workbook renders are not byte-identical", file=sys.stderr)
        return 1

    try:
        with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        print("ERROR: workbook renderer did not emit a ZIP package", file=sys.stderr)
        return 1
    if not {"[Content_Types].xml", "xl/workbook.xml"} <= names:
        print("ERROR: native XLSX dependency is unavailable in the supported-runtime gate", file=sys.stderr)
        return 1

    digest = hashlib.sha256(first).hexdigest()
    print(f"workbook-reproducibility-sha256={digest}")
    if digest != EXPECTED_NATIVE_SHA256:
        print(
            f"ERROR: workbook fingerprint drifted: {digest} != {EXPECTED_NATIVE_SHA256}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
