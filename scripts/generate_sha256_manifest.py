#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from neuroai_workbench.util import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("SHA256SUMS.txt"))
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path != output and ".git" not in path.parts:
            rows.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"{len(rows)} files -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
