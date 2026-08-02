from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.entities import FuzzyMergeRefusedError
from neuroai_workbench.entities.registry import _alias_path, _entity_path, _identifier_path
from neuroai_workbench.util import atomic_write_json, load_json, safe_join
from tests.fixtures.entities.helpers import seed_entity_workspace


def test_entity_path_blocks_parent_segments(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid entity_id"):
        _entity_path(workspace, "..")
    root = workspace / "observatory" / "entities" / "records"
    with pytest.raises(ValueError, match="Path escapes controlled root"):
        safe_join(root, "..", "registry.json")


def test_alias_and_identifier_paths_stay_under_root(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    with pytest.raises(ValueError, match="Invalid alias_id"):
        _alias_path(workspace, "..")
    with pytest.raises(ValueError, match="Invalid identifier_id"):
        _identifier_path(workspace, "..")


def test_registry_status_detects_tampered_index(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    registry_path = workspace / "observatory" / "entities" / "registry.json"
    registry = load_json(registry_path)
    registry["metadata"]["record_count"] = 99
    atomic_write_json(registry_path, registry)
    from neuroai_workbench.entities import registry_status

    with pytest.raises(ValueError, match="hash mismatch"):
        registry_status(workspace)


def test_resolve_exact_rejects_multiple_selectors(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    from neuroai_workbench.entities import resolve_exact

    with pytest.raises(ValueError, match="exactly one"):
        resolve_exact(workspace, entity_id="ENT-SYNTH-ORG-001", alias_id="ALIAS-SYNTH-001", actor="tester")


def test_alias_text_is_not_used_for_resolution(tmp_path: Path) -> None:
    workspace = seed_entity_workspace(tmp_path)
    from neuroai_workbench.entities import resolve_exact

    with pytest.raises(ValueError, match="exactly one"):
        resolve_exact(workspace, actor="tester")
    with pytest.raises(FuzzyMergeRefusedError, match="Normalized-name matching"):
        resolve_exact(workspace, normalized_name="Synthetic Neuro Devices", actor="tester")
