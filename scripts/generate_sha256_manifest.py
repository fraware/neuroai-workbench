#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from neuroai_workbench.util import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    rows: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.resolve() != output and ".git" not in path.parts:
            rows.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"{len(rows)} files -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
