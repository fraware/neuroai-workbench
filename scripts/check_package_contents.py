
#!/usr/bin/env python3
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REQUIRED_SUFFIXES = {
    "neuroai_workbench/static/index.html",
    "neuroai_workbench/static/app.js",
    "neuroai_workbench/static/styles.css",
    "neuroai_workbench/resources/v4_2/KERNEL_REQUIREMENTS_v4.2.json",
    "neuroai_workbench/resources/v4_2/UNIVERSAL_NEUROAI_ASSESSMENT_SCHEMA_v4.2.json",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_package_contents.py WHEEL", file=sys.stderr)
        return 2
    wheel = Path(sys.argv[1])
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        missing = sorted(item for item in REQUIRED_SUFFIXES if item not in names)
        if archive.testzip() is not None:
            print("wheel ZIP integrity failed", file=sys.stderr)
            return 1
    if missing:
        for item in missing:
            print(f"missing package resource: {item}", file=sys.stderr)
        return 1
    print(f"package contents passed for {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
