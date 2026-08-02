#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "artifacts",
    "workspaces",
}
PROHIBITED_SUFFIXES = {".pyc", ".pyo", ".whl", ".zip", ".bundle", ".docx", ".xlsx"}
PROHIBITED_TRACKED_PREFIXES = ("bootstrap/", ".cursor/")
PROHIBITED_TRACKED_FILES = {
    ".github/workflows/bootstrap-canonical-history.yml",
}
REQUIRED = {
    "AGENTS.md",
    "README.md",
    "SECURITY.md",
    "THREAT_MODEL.md",
    "DATA_GOVERNANCE.md",
    ".github/CODEOWNERS",
    "src/neuroai_workbench/resources/v4_2/KERNEL_REQUIREMENTS_v4.2.json",
}
REQUIRED_GITIGNORE_ENTRIES = {
    ".cursor/",
}
EXECUTABLES = {
    "scripts/create_demo_workspace.py",
    "scripts/docker-entrypoint.sh",
    "scripts/generate_sbom.py",
    "scripts/generate_sha256_manifest.py",
    "scripts/verify_release.py",
    "scripts/check_repository_hygiene.py",
    "scripts/check_version_consistency.py",
}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, text=True, capture_output=True)
    return [line for line in result.stdout.splitlines() if line]


def executable_paths() -> set[str]:
    result = subprocess.run(["git", "ls-files", "--stage"], cwd=ROOT, check=True, text=True, capture_output=True)
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        mode, _, _, path = line.split(maxsplit=3)
        if mode == "100755":
            paths.add(path)
    return paths


def main() -> int:
    files = tracked_files()
    errors: list[str] = []
    for rel in files:
        path = Path(rel)
        if any(part in PROHIBITED_PARTS for part in path.parts):
            errors.append(f"generated path is tracked: {rel}")
        if path.suffix.lower() in PROHIBITED_SUFFIXES:
            errors.append(f"prohibited generated or binary artifact is tracked: {rel}")
        if rel in PROHIBITED_TRACKED_FILES or any(rel.startswith(prefix) for prefix in PROHIBITED_TRACKED_PREFIXES):
            if rel.startswith(".cursor/") or rel in {".cursor"}:
                errors.append(f"local Cursor IDE path must not be tracked: {rel}")
            else:
                errors.append(f"stale bootstrap scaffolding must not ship on product branches: {rel}")
        absolute = ROOT / rel
        if absolute.is_file() and absolute.stat().st_size > 5 * 1024 * 1024:
            errors.append(f"tracked file exceeds 5 MiB source limit: {rel}")
    for rel in sorted(REQUIRED - set(files)):
        errors.append(f"required source file is missing: {rel}")
    gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    gitignore_lines = {line.strip() for line in gitignore_text.splitlines()}
    for entry in sorted(REQUIRED_GITIGNORE_ENTRIES):
        if entry not in gitignore_lines:
            errors.append(f"required .gitignore entry is missing: {entry}")
    executable = executable_paths()
    for rel in sorted(EXECUTABLES):
        if rel in files and rel not in executable:
            errors.append(f"script is not executable in Git: {rel}")

    static_root = ROOT / "src/neuroai_workbench/static"
    for path in static_root.glob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            if "https://" in lowered or "http://" in lowered or "//cdn" in lowered:
                errors.append(f"remote asset reference found in {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"repository hygiene passed for {len(files)} tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
