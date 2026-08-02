from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_cursor_directory_is_gitignored_and_untracked() -> None:
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert ".cursor/" in {line.strip() for line in gitignore.splitlines()}

    tracked = subprocess.run(
        ["git", "ls-files", "--", ".cursor"],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )
    assert tracked.stdout.strip() == ""

    hygiene = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check_repository_hygiene.py")],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert hygiene.returncode == 0, hygiene.stderr or hygiene.stdout
    assert "local Cursor IDE path must not be tracked" not in (hygiene.stderr or "")
