#!/usr/bin/env python3
from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

from neuroai_workbench.util import utc_now

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "neuroai-workbench-v0.2.0",
        "documentNamespace": "https://github.com/fraware/neuroai-workbench/releases/tag/v0.2.0/sbom",
        "creationInfo": {"created": utc_now(), "creators": ["Tool: neuroai-workbench-release-builder"]},
        "packages": [
            {
                "name": "neuroai-workbench",
                "SPDXID": "SPDXRef-Package-Workbench",
                "versionInfo": "0.2.0",
                "downloadLocation": "NOASSERTION",
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "filesAnalyzed": False,
                "supplier": "Organization: NeuroAI Workbench Contributors",
            },
            {
                "name": "jsonschema",
                "SPDXID": "SPDXRef-Package-jsonschema",
                "versionInfo": version("jsonschema"),
                "downloadLocation": "https://pypi.org/project/jsonschema/",
                "licenseConcluded": "MIT",
                "licenseDeclared": "MIT",
                "filesAnalyzed": False,
                "supplier": "Organization: Python JSON Schema",
            },
        ],
        "relationships": [
            {"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Package-Workbench"},
            {"spdxElementId": "SPDXRef-Package-Workbench", "relationshipType": "DEPENDS_ON", "relatedSpdxElement": "SPDXRef-Package-jsonschema"},
        ],
        "annotations": [{
            "annotationDate": utc_now(),
            "annotationType": "OTHER",
            "annotator": "Tool: neuroai-workbench-release-builder",
            "comment": "No dependency source code is vendored. The workbench uses Python standard-library components for the local server and browser assets included in the package.",
        }],
    }
    target = ROOT / "SBOM.spdx.json"
    target.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
