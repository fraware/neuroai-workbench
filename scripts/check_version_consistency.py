#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from neuroai_workbench import __version__  # noqa: E402
from neuroai_workbench.workspace import Workspace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    args = parser.parse_args()
    expected_tag = f"v{__version__}"
    errors: list[str] = []

    status_path = ROOT / f"CONTROLLED_STATUS_{expected_tag}.json"
    notes_path = ROOT / f"RELEASE_NOTES_{expected_tag}.md"
    if not status_path.is_file():
        errors.append(f"missing {status_path.name}")
    else:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("release") != expected_tag:
            errors.append("controlled status release does not match package version")
    if not notes_path.is_file():
        errors.append(f"missing {notes_path.name}")
    elif expected_tag not in notes_path.read_text(encoding="utf-8"):
        errors.append("release notes do not contain the expected version")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"`{expected_tag}`" not in readme:
        errors.append("README repository status does not contain the expected version")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^## {re.escape(__version__)}\b", changelog, flags=re.MULTILINE):
        errors.append("CHANGELOG does not contain the expected version heading")

    if args.tag and args.tag != expected_tag:
        errors.append(f"tag {args.tag!r} does not match {expected_tag!r}")

    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="neuroai-version-") as tmp:
        workspace = Workspace.initialize(Path(tmp) / "workspace")
        if workspace.metadata.get("workbench_version") != __version__:
            errors.append("workspace metadata does not match package version")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"version consistency passed for {expected_tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
