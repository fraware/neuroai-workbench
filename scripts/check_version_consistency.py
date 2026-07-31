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

_DEV_VERSION = re.compile(r"^\d+\.\d+\.\d+\.dev\d+$")
_RELEASE_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def _is_dev(version: str) -> bool:
    return bool(_DEV_VERSION.match(version))


def _check_released(errors: list[str], expected_tag: str) -> None:
    status_path = ROOT / f"CONTROLLED_STATUS_{expected_tag}.json"
    notes_path = ROOT / f"RELEASE_NOTES_{expected_tag}.md"
    if not status_path.is_file():
        errors.append(f"missing {status_path.name}")
    else:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("release") != expected_tag:
            errors.append("controlled status release does not match package version")
        if status.get("state") == "unreleased":
            errors.append("released version must not declare unreleased state")
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


def _check_dev(errors: list[str], expected_tag: str) -> None:
    status_path = ROOT / f"CONTROLLED_STATUS_{expected_tag}.json"
    notes_path = ROOT / f"RELEASE_NOTES_{expected_tag}.md"
    if notes_path.is_file():
        errors.append(f"dev versions must not ship {notes_path.name}")
    if not status_path.is_file():
        errors.append(f"missing {status_path.name}")
    else:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("release") != expected_tag:
            errors.append("controlled status release does not match package version")
        if status.get("state") != "unreleased":
            errors.append("dev controlled status must declare state unreleased")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "`0.3.0.dev0`" not in readme and f"`{__version__}`" not in readme:
        errors.append("README must state the unreleased package version")
    if "`v0.2.1`" not in readme:
        errors.append("README must state that published stabilization remains v0.2.1")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased_names_version = re.search(
        rf"^## Unreleased\b.*{re.escape(__version__)}",
        changelog,
        flags=re.MULTILINE,
    )
    dedicated_heading = re.search(
        rf"^## {re.escape(__version__)}\b.*unreleased",
        changelog,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if not unreleased_names_version and not dedicated_heading:
        errors.append(
            f"CHANGELOG Unreleased section must name the current .dev version (or use '## {__version__} — unreleased')"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    args = parser.parse_args()
    expected_tag = f"v{__version__}"
    errors: list[str] = []

    if not (_is_dev(__version__) or _RELEASE_VERSION.match(__version__)):
        errors.append(f"unsupported package version shape: {__version__!r}")

    if args.tag:
        if _is_dev(__version__):
            errors.append(f"refusing to release development version {expected_tag!r}; tag only real vX.Y.Z releases")
        elif args.tag != expected_tag:
            errors.append(f"tag {args.tag!r} does not match {expected_tag!r}")
        elif ".dev" in args.tag:
            errors.append(f"refusing development tag {args.tag!r} as a release")

    if _is_dev(__version__):
        _check_dev(errors, expected_tag)
    elif _RELEASE_VERSION.match(__version__):
        _check_released(errors, expected_tag)

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
