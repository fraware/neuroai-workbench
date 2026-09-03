from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "observatory_v2_migration_proof.py"
    spec = importlib.util.spec_from_file_location("observatory_v2_migration_proof", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _source() -> dict[str, str]:
    return {
        "source_id": "SRC-1",
        "title": "Official source",
        "publisher": "Publisher",
        "url": "https://example.test/source",
        "source_class": "OFFICIAL_PAGE",
        "retrieved": "2026-07-29",
        "claim_boundary": "Retrieval is not substantive truth.",
    }


def test_known_family_is_accounted_without_authority(tmp_path: Path) -> None:
    mod = _module()
    predecessor = _write(
        tmp_path / "v14.json",
        {
            "organizations": [
                {
                    "organization_id": "ORG-1",
                    "canonical_name": "Example",
                    "aliases": [],
                    "organization_type": "COMPANY",
                    "source_ids": ["SRC-1"],
                    "last_verified": "2026-07-29",
                    "claim_boundary": "Presence only.",
                }
            ],
            "sources": [_source()],
        },
    )

    proof = mod.build_proof([("V14", predecessor)])

    assert proof["field_preservation"] == "PASS"
    assert proof["release_authorized"] is False
    assert proof["native_v2_materialization_complete"] is False
    assert proof["reconciliation"]["unmapped_required_field_count"] == 0
    assert proof["reconciliation"]["invented_value_count"] == 0
    assert {record["target_object_class"] for record in proof["records"]} == {"Entity", "Source"}

    source_fields = [field for field in proof["fields"] if field["family"] == "sources"]
    by_source_field = {field["source_field"]: field for field in source_fields}
    assert by_source_field["source_id"]["target_field"] == "source_id"
    assert by_source_field["url"]["target_field"] == "canonical_url_or_reference"
    assert by_source_field["claim_boundary"]["disposition"] == "PRESERVED_LEGACY_FIELD"
    assert by_source_field["retrieved"]["disposition"] == "PRESERVED_LEGACY_FIELD"


def test_unresolved_predecessor_provenance_is_explicit(tmp_path: Path) -> None:
    mod = _module()
    predecessor = _write(
        tmp_path / "v14.json",
        {
            "organizations": [
                {
                    "organization_id": "ORG-LEGACY",
                    "canonical_name": "Legacy only",
                    "verification_state": "LEGACY_ONLY",
                    "source_ids": [],
                    "last_verified": None,
                }
            ]
        },
    )

    proof = mod.build_proof([("V14", predecessor)])
    unresolved = [
        field for field in proof["fields"] if field["disposition"] == "PRESERVED_UNRESOLVED_PREDECESSOR_STATE"
    ]

    assert {field["source_field"] for field in unresolved} == {"source_ids", "last_verified"}
    assert proof["reconciliation"]["preserved_unresolved_state_count"] == 2
    assert proof["reconciliation"]["invented_value_count"] == 0


def test_unknown_family_fails_closed(tmp_path: Path) -> None:
    mod = _module()
    predecessor = _write(tmp_path / "v14.json", {"unreviewed_family": [{"x": 1, "y": 2}]})

    proof = mod.build_proof([("V14", predecessor)])

    assert proof["field_preservation"] == "FAIL"
    assert proof["reconciliation"]["unmapped_required_field_count"] == 2
    assert proof["reconciliation"]["disposition_counts"]["BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE"] == 2


def test_unknown_role_fails_closed(tmp_path: Path) -> None:
    mod = _module()
    predecessor = _write(tmp_path / "unknown.json", [{"source_id": "SRC-X"}])

    proof = mod.build_proof([("UNKNOWN", predecessor)])

    assert proof["field_preservation"] == "FAIL"
    assert proof["reconciliation"]["unmapped_required_field_count"] == 1


def test_proof_is_deterministic_and_content_addressed(tmp_path: Path) -> None:
    mod = _module()
    predecessor = _write(tmp_path / "v14.json", {"sources": [_source()]})

    first = mod.build_proof([("V14", predecessor)])
    second = mod.build_proof([("V14", predecessor)])

    assert first == second
    assert len(first["proof_sha256"]) == 64
    controlled = {key: value for key, value in first.items() if key != "proof_sha256"}
    assert first["proof_sha256"] == mod.sha256_value(controlled)


def test_duplicate_input_role_is_refused(tmp_path: Path) -> None:
    mod = _module()
    first = _write(tmp_path / "a.json", {})
    second = _write(tmp_path / "b.json", {})

    try:
        mod.build_proof([("V14", first), ("V14", second)])
    except ValueError as exc:
        assert "Duplicate input role V14" in str(exc)
    else:
        raise AssertionError("duplicate roles must fail closed")


def test_write_proof_emits_deterministic_ledgers(tmp_path: Path) -> None:
    mod = _module()
    predecessor = _write(tmp_path / "v14.json", {"sources": [_source()]})
    proof = mod.build_proof([("V14", predecessor)])
    output = tmp_path / "out"

    mod.write_proof(proof, output)

    assert (output / "migration-proof.json").is_file()
    assert (output / "input-manifest.json").is_file()
    assert (output / "field-ledger.jsonl").is_file()
    assert (output / "record-ledger.jsonl").is_file()
    rows = [json.loads(line) for line in (output / "field-ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows
    assert any(row["disposition"] == "MAPPED_NATIVE_V2" for row in rows)
    assert any(row["disposition"] == "PRESERVED_LEGACY_FIELD" for row in rows)
