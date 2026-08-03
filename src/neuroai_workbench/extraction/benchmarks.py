from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from .contract import BENCHMARK_MANIFEST_SCHEMA, EXTRACTION_BOUNDARY, _schema_errors

BENCHMARK_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "source_extraction"
DEFAULT_MANIFEST = "MANIFEST.json"


def _manifest_path(path: Path | None = None) -> Path:
    return path or (BENCHMARK_ROOT / DEFAULT_MANIFEST)


def load_benchmark_manifest(path: Path | None = None) -> dict[str, Any]:
    target = _manifest_path(path)
    if not target.is_file():
        raise FileNotFoundError(f"Benchmark manifest not found at {target}")
    return cast(dict[str, Any], json.loads(target.read_text(encoding="utf-8")))


def validate_benchmark_manifest(value: Any) -> dict[str, Any]:
    errors = _schema_errors(value, BENCHMARK_MANIFEST_SCHEMA)
    if isinstance(value, dict) and value.get("status") != "PREREGISTERED":
        errors.append(
            {
                "code": "BENCHMARK_STATUS",
                "path": "status",
                "message": "benchmark manifest must remain PREREGISTERED until evaluation execution",
            }
        )
    return {"valid": not errors, "errors": errors, "boundary": EXTRACTION_BOUNDARY}


def list_benchmark_fixtures(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = manifest or load_benchmark_manifest()
    fixtures = payload.get("fixtures", [])
    if not isinstance(fixtures, list):
        return []
    return [cast(dict[str, Any], item) for item in fixtures if isinstance(item, dict)]


def get_preregistered_metrics(manifest: dict[str, Any] | None = None) -> list[str]:
    payload = manifest or load_benchmark_manifest()
    metrics = payload.get("metrics", [])
    return [str(item) for item in metrics] if isinstance(metrics, list) else []


def get_stop_conditions(manifest: dict[str, Any] | None = None) -> list[str]:
    payload = manifest or load_benchmark_manifest()
    conditions = payload.get("stop_conditions", [])
    return [str(item) for item in conditions] if isinstance(conditions, list) else []


def load_fixture_stub(relative_path: str, *, root: Path | None = None) -> dict[str, Any]:
    """Load a fixture stub path or a corpus-pack virtual stub.

    Virtual stubs use the form ``corpus:<file>#<fixture_id>:capture|annotation``.
    """
    if relative_path.startswith("corpus:"):
        return _load_corpus_virtual_stub(relative_path, root=root)
    target = (root or BENCHMARK_ROOT) / relative_path
    if not target.is_file():
        raise FileNotFoundError(f"Benchmark fixture stub not found at {target}")
    return cast(dict[str, Any], json.loads(target.read_text(encoding="utf-8")))


def _load_corpus_virtual_stub(spec: str, *, root: Path | None = None) -> dict[str, Any]:
    # corpus:CORPUS_PUBLIC_SCALE.json#FIX-...:capture
    body = spec[len("corpus:") :]
    if "#" not in body or ":" not in body.split("#", 1)[1]:
        raise ValueError(f"Invalid corpus stub spec {spec!r}")
    file_part, remainder = body.split("#", 1)
    fixture_id, kind = remainder.rsplit(":", 1)
    if kind not in {"capture", "annotation"}:
        raise ValueError(f"Corpus stub kind must be capture|annotation, got {kind!r}")
    corpus_path = (root or BENCHMARK_ROOT) / file_part
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"Corpus pack {corpus_path} missing cases array")
    for case in cases:
        if isinstance(case, dict) and case.get("fixture_id") == fixture_id:
            fragment = case.get(kind)
            if not isinstance(fragment, dict):
                raise ValueError(f"Corpus case {fixture_id} missing {kind}")
            return cast(dict[str, Any], fragment)
    raise FileNotFoundError(f"Fixture {fixture_id} not found in corpus pack {corpus_path}")


def load_scale_benchmark_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load the ≥150-case scale manifest when present."""
    target = path or (BENCHMARK_ROOT / "MANIFEST_SCALE.json")
    return load_benchmark_manifest(target)
