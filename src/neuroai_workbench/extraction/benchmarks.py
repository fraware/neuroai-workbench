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
    target = (root or BENCHMARK_ROOT) / relative_path
    if not target.is_file():
        raise FileNotFoundError(f"Benchmark fixture stub not found at {target}")
    return cast(dict[str, Any], json.loads(target.read_text(encoding="utf-8")))
