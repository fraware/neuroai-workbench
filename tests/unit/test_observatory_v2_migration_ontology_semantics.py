from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _proof_module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "observatory_v2_migration_proof.py"
    spec = importlib.util.spec_from_file_location("observatory_v2_migration_proof_ontology", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_predecessor_organization_type_is_preserved_not_used_as_entity_type(tmp_path: Path) -> None:
    module = _proof_module()
    path = tmp_path / "v14.json"
    path.write_text(
        json.dumps(
            {
                "organizations": [
                    {
                        "organization_id": "ORG-1",
                        "canonical_name": "Example",
                        "aliases": [],
                        "organization_type": "COMPANY",
                        "current_status": "CURRENT",
                        "verification_state": "CURRENT_VERIFIED",
                        "source_ids": ["SRC-1"],
                        "last_verified": "2026-07-29",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    proof = module.build_proof([("V14", path)])
    organization_type_fields = [
        field
        for field in proof["fields"]
        if field["family"] == "organizations" and field["source_field"] == "organization_type"
    ]

    assert len(organization_type_fields) == 1
    assert organization_type_fields[0]["disposition"] == "PRESERVED_LEGACY_FIELD"
    assert organization_type_fields[0]["target_object_class"] is None
    assert organization_type_fields[0]["target_field"] is None

    mapped = {
        field["source_field"]: (field["target_object_class"], field["target_field"])
        for field in proof["fields"]
        if field["family"] == "organizations" and field["disposition"] == "MAPPED_NATIVE_V2"
    }
    assert mapped["organization_id"] == ("Entity", "entity_id")
    assert mapped["canonical_name"] == ("Entity", "canonical_label")
    assert "organization_type" not in mapped
