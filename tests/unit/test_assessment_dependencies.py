from __future__ import annotations

from pathlib import Path

import pytest

from neuroai_workbench.assessment_dependencies import (
    DEPENDENCY_ROLES,
    REFERENCE_MANIFESTS,
    load_all_reference_manifests,
    load_reference_manifest,
    match_dependency,
    reference_manifest_dir,
    summarize_manifest,
    validate_manifest,
    validate_manifest_file,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("assessment_id", sorted(REFERENCE_MANIFESTS))
def test_reference_manifests_validate(assessment_id: str) -> None:
    report = validate_manifest_file(reference_manifest_dir(ROOT) / REFERENCE_MANIFESTS[assessment_id])
    assert report["valid"] is True
    assert report["counts"]["dependencies"] >= 8


def test_all_four_reference_manifests_load() -> None:
    manifests = load_all_reference_manifests(ROOT)
    assert set(manifests) == set(REFERENCE_MANIFESTS)
    for manifest in manifests.values():
        assert validate_manifest(manifest)["valid"] is True


def test_summarize_preserves_unknown_and_inaccessible() -> None:
    manifest = load_reference_manifest("PRIMA-PUBLIC-2026-001", ROOT)
    summary = summarize_manifest(manifest)
    assert summary["by_resolution"]["UNKNOWN"] >= 1
    assert summary["by_resolution"]["INACCESSIBLE"] >= 1
    assert summary["by_role"]["REOPENING_TRIGGER"] >= 2


def test_duplicate_dependency_id_rejected() -> None:
    manifest = load_reference_manifest("PILOT-05-BRAIN2QWERTY-v4.1.3", ROOT)
    mutated = dict(manifest)
    dependencies = [dict(item) for item in manifest["dependencies"]]
    dependencies.append(dict(dependencies[0]))
    mutated["dependencies"] = dependencies
    report = validate_manifest(mutated)
    assert report["valid"] is False
    assert any(item["code"] == "DUPLICATE_IDENTIFIER" for item in report["errors"])


def test_match_dependency_scoped_to_target() -> None:
    prima = load_reference_manifest("PRIMA-PUBLIC-2026-001", ROOT)
    matches = match_dependency(target_kind="REGULATORY_RECORD", target_ref="REG-16-001", manifest=prima)
    assert len(matches) == 1
    assert matches[0]["dependency_role"] == "REOPENING_TRIGGER"
    unrelated = match_dependency(target_kind="MODEL", target_ref="MDL-16-001", manifest=prima)
    assert unrelated == []


def test_unresolved_identity_emits_warning_not_error() -> None:
    manifest = load_reference_manifest("PILOT-05-BRAIN2QWERTY-v4.1.3", ROOT)
    report = validate_manifest(manifest)
    assert report["valid"] is True
    assert report["counts"]["unknown_or_inaccessible"] >= 1


def test_dependency_roles_and_schema_enums_align() -> None:
    assert len(DEPENDENCY_ROLES) == 6
