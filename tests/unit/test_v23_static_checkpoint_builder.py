from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "build_v23_static_canonical_checkpoint.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_v23_static_canonical_checkpoint", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_governing_mapping_covers_required_programme_families() -> None:
    module = _load_script()
    mappings = module.governing_mappings()

    assert len(mappings) == 19
    families = {family for _, _, family in mappings}
    assert families == {"PROGRAMME", "OBSERVATORY", "NORMATIVE", "ASSESSMENT", "COMPARISON"}
    targets = [target for _, target, _ in mappings]
    assert len(targets) == len(set(targets))
    assert "observatory/releases/v1.4/full_release.json" in targets
    assert "observatory/releases/v1.7/successor_snapshot.json" in targets
    assert "assessments/prima/v4.2.1/assessment.json" in targets


def test_assessment_counts_supports_legacy_and_prima_shapes() -> None:
    module = _load_script()
    legacy = {
        "assessment_metadata": {},
        "requirement_findings": [{}] * 78,
        "claim_register": [{}] * 8,
        "evidence_register": [{}] * 10,
        "endpoint_register": [{}] * 6,
        "gap_register": [{}] * 12,
    }
    prima = {
        "metadata": {},
        "requirement_findings": [{}] * 78,
        "claims": [{}] * 14,
        "evidence_register": [{}] * 15,
        "endpoints": [{}] * 11,
        "gaps_and_requests": [{}] * 22,
    }

    assert module.assessment_counts(legacy) == {
        "findings": 78,
        "claims": 8,
        "evidence": 10,
        "endpoints": 6,
        "gaps": 12,
    }
    assert module.assessment_counts(prima) == {
        "findings": 78,
        "claims": 14,
        "evidence": 15,
        "endpoints": 11,
        "gaps": 22,
    }


def test_status_counts_preserves_distinct_statuses() -> None:
    module = _load_script()
    document = {
        "requirement_findings": [
            {"normalized_status": "PASS"},
            {"finding_status": "PARTIAL"},
            {"status": "NOT ASSESSED"},
            {},
        ]
    }

    assert module.status_counts(document) == {
        "NOT ASSESSED": 1,
        "PARTIAL": 1,
        "PASS": 1,
        "UNRESOLVED": 1,
    }
