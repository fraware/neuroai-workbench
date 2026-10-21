"""CLI for the offline R1.7 literature pilot.

Usage:
  python -m scripts.r1_7_literature_pilot catalog
  python -m scripts.r1_7_literature_pilot pilot --count 3
  python -m scripts.r1_7_literature_pilot ingest --decision capture.json --snapshot page.html
  python -m scripts.r1_7_literature_pilot combine bundle1.json bundle2.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from neuroai_workbench.release_a_r1_literature_pilot import (
    combine_bundles,
    import_snapshot,
    literature_worklist,
    select_distinct_pilots,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    pilot = sub.add_parser("pilot")
    pilot.add_argument("--count", type=int, default=3)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--decision", type=Path, required=True)
    ingest.add_argument("--snapshot", type=Path, required=True)
    combine = sub.add_parser("combine")
    combine.add_argument("bundles", nargs="+", type=Path)
    args = parser.parse_args(argv)
    result: dict[str, Any]
    if args.command == "catalog":
        rows = literature_worklist()
        result = {"status": "FROZEN_PENDING_EXECUTION", "work_item_count": len(rows), "unique_pmids": len({r["pmid"] for r in rows}), "work_items": rows}
    elif args.command == "pilot":
        rows = select_distinct_pilots(args.count)
        result = {"status": "PENDING_NEW_SOURCE_EVIDENCE", "selected_distinct_papers": len(rows), "work_items": rows}
    elif args.command == "ingest":
        decision = json.loads(args.decision.read_text(encoding="utf-8"))
        if not isinstance(decision, dict):
            parser.error("decision must be a JSON object")
        result = import_snapshot(args.snapshot.read_bytes(), decision)
    else:
        bundles = [json.loads(path.read_text(encoding="utf-8")) for path in args.bundles]
        result = combine_bundles(bundles)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
