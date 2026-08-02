from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from neuroai_workbench.monitoring import initialize_monitoring, monitoring_status
from neuroai_workbench.observatory import import_release
from neuroai_workbench.util import atomic_write_json, sha256_file
from neuroai_workbench.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap a controlled NeuroAI observatory operations workspace")
    parser.add_argument("workspace")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--successor", required=True)
    parser.add_argument("--name", default="NeuroAI observatory operations")
    parser.add_argument("--actor", default="bootstrap-operator")
    parser.add_argument("--manifest", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace_path = Path(args.workspace)
    workspace = (
        Workspace.open(workspace_path)
        if (workspace_path / "workspace.json").is_file()
        else Workspace.initialize(workspace_path, name=args.name)
    )
    monitoring = initialize_monitoring(workspace.root, Path(args.registry), actor=args.actor)
    baseline = import_release(workspace.root, Path(args.baseline))
    successor = import_release(workspace.root, Path(args.successor))
    manifest: dict[str, Any] = {
        "workspace": str(workspace.root),
        "workspace_metadata": workspace.metadata,
        "monitoring": monitoring,
        "observatory": {
            "baseline": baseline,
            "successor": successor,
        },
        "inputs": {
            "registry": {"path": args.registry, "sha256": sha256_file(Path(args.registry))},
            "baseline": {"path": args.baseline, "sha256": sha256_file(Path(args.baseline))},
            "successor": {"path": args.successor, "sha256": sha256_file(Path(args.successor))},
        },
        "status": monitoring_status(workspace.root),
        "boundary": (
            "Bootstrap establishes controlled software state and byte provenance only. It does not establish "
            "substantive evidence validity, assessment conformance, regulatory authorization, or UNESCO endorsement."
        ),
    }
    output = Path(args.manifest)
    atomic_write_json(output, manifest)
    print(json.dumps({"manifest": str(output), "sha256": sha256_file(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
