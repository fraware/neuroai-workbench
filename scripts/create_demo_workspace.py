#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from neuroai_workbench.workspace import Workspace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and args.replace:
        import shutil
        shutil.rmtree(args.output)
    workspace = Workspace.initialize(args.output, name="NeuroAI v4.2 reference workspace")
    examples = Path(__file__).resolve().parents[1] / "examples" / "assessments"
    for path in sorted(examples.glob("*.json")):
        workspace.import_case(path, actor="release-builder")
    workspace.create_case("CASE-TEMPLATE", "Blank controlled assessment template", actor="release-builder")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
