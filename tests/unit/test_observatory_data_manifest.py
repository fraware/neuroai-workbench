from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD = ROOT / "templates" / "neuroai-observatory-data"
SCRIPTS = SCAFFOLD / "scripts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generate_manifest():
    return _load_module("generate_manifest", SCRIPTS / "generate_manifest.py")


@pytest.fixture(scope="module")
def verify_manifest():
    return _load_module("verify_manifest", SCRIPTS / "verify_manifest.py")


def test_bootstrap_fixture_manifest_verifies(generate_manifest, verify_manifest) -> None:
    fixtures = SCAFFOLD / "fixtures"
    manifest = SCAFFOLD / "releases" / "data-v0.0.1-bootstrap" / "SHA256SUMS.txt"

    assert (
        subprocess.run(
            [sys.executable, str(SCRIPTS / "generate_manifest.py"), str(fixtures), str(manifest)],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )

    ok, errors = verify_manifest.verify_manifest(fixtures, manifest)
    assert ok, errors


def test_generate_and_verify_round_trip_on_temp_tree(generate_manifest, verify_manifest, tmp_path: Path) -> None:
    (tmp_path / "alpha.json").write_text('{"id":"SYN-A"}\n', encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "beta.json").write_text('{"id":"SYN-B"}\n', encoding="utf-8")
    manifest = tmp_path / "SHA256SUMS.txt"

    text = generate_manifest.render_manifest(tmp_path, exclude={manifest.resolve()})
    manifest.write_text(text, encoding="utf-8")

    ok, errors = verify_manifest.verify_manifest(tmp_path, manifest)
    assert ok, errors

    (tmp_path / "nested" / "beta.json").write_text('{"id":"SYN-B-tampered"}\n', encoding="utf-8")
    ok, errors = verify_manifest.verify_manifest(tmp_path, manifest)
    assert not ok
    assert any("digest mismatch" in error for error in errors)


def test_verify_detects_unexpected_file(generate_manifest, verify_manifest, tmp_path: Path) -> None:
    (tmp_path / "only.json").write_text("{}\n", encoding="utf-8")
    manifest = tmp_path / "SHA256SUMS.txt"
    manifest.write_text(generate_manifest.render_manifest(tmp_path, exclude={manifest.resolve()}), encoding="utf-8")

    (tmp_path / "extra.json").write_text("{}\n", encoding="utf-8")
    ok, errors = verify_manifest.verify_manifest(tmp_path, manifest)
    assert not ok
    assert any("unexpected file" in error for error in errors)


def test_release_descriptor_matches_schema_and_manifest_hash() -> None:
    descriptor_path = SCAFFOLD / "releases" / "data-v0.0.1-bootstrap" / "release-descriptor.json"
    manifest_path = SCAFFOLD / "releases" / "data-v0.0.1-bootstrap" / "SHA256SUMS.txt"
    schema_path = SCAFFOLD / "schemas" / "release-descriptor.schema.json"

    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    assert descriptor["manifest_sha256"] == manifest_sha256
    assert descriptor["workbench_version"] == (SCAFFOLD / "WORKBENCH_VERSION").read_text(encoding="utf-8").strip()

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(descriptor, schema)


def test_workbench_version_matches_package() -> None:
    from neuroai_workbench import __version__

    pinned = (SCAFFOLD / "WORKBENCH_VERSION").read_text(encoding="utf-8").strip()
    assert pinned == __version__
