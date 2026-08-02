from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent


def seed_entity_workspace(tmp_path: Path) -> Path:
    from neuroai_workbench.entities import initialize_registry

    workspace = tmp_path / "workspace"
    seed = json.loads((FIXTURES / "ENTITY_REGISTRY_SYNTHETIC.json").read_text(encoding="utf-8"))
    initialize_registry(workspace, seed=seed, actor="tester")
    for name in ("ENT-SYNTH-ORG-001.json", "ENT-SYNTH-SYS-001.json"):
        shutil.copy(FIXTURES / name, workspace / "observatory" / "entities" / "records" / name)
    shutil.copy(FIXTURES / "ALIAS-SYNTH-001.json", workspace / "observatory" / "entities" / "aliases" / "ALIAS-SYNTH-001.json")
    shutil.copy(FIXTURES / "ID-SYNTH-DOMAIN-001.json", workspace / "observatory" / "entities" / "identifiers" / "ID-SYNTH-DOMAIN-001.json")
    return workspace
