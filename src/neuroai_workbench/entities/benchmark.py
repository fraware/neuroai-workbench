from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from .resolver import propose_resolution

BENCHMARK_RESOURCE = "neuroai_workbench.resources.entities"
BLINDED_BENCHMARK_STUB = "RESOLUTION_BENCHMARK_BLINDED.json"


def load_blinded_benchmark_stub() -> dict[str, Any]:
    payload = json.loads(files(BENCHMARK_RESOURCE).joinpath(BLINDED_BENCHMARK_STUB).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Blinded benchmark stub must be an object")
    return cast(dict[str, Any], payload)


def run_blinded_benchmark(workspace: Path, *, actor: str = "benchmark-runner") -> dict[str, Any]:
    """Run blinded resolution benchmark cases against a prepared workspace."""
    stub = load_blinded_benchmark_stub()
    cases = stub.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Blinded benchmark stub missing cases array")

    results: list[dict[str, Any]] = []
    passed = 0
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id", f"case-{index}"))
        case_input = case.get("input")
        expected = case.get("expected")
        if not isinstance(case_input, dict) or not isinstance(expected, dict):
            results.append({"case_id": case_id, "passed": False, "detail": "Invalid case structure"})
            continue
        proposal = propose_resolution(
            workspace,
            raw_mention=str(case_input.get("raw_mention", "")),
            source_capture_ref=cast(str | None, case_input.get("source_capture_ref")),
            entity_id=cast(str | None, case_input.get("entity_id")),
            alias_id=cast(str | None, case_input.get("alias_id")),
            identifier_scheme=cast(str | None, case_input.get("identifier_scheme")),
            identifier_value=cast(str | None, case_input.get("identifier_value")),
            actor=actor,
        )
        checks = {
            "resolution_state": proposal["resolution_state"] == expected.get("resolution_state"),
            "match_layer": proposal["match_layer"] == expected.get("match_layer"),
            "auto_confirmed": proposal["auto_confirmed"] is expected.get("auto_confirmed"),
        }
        case_passed = all(checks.values())
        if case_passed:
            passed += 1
        results.append(
            {
                "case_id": case_id,
                "passed": case_passed,
                "expected": expected,
                "observed": {
                    "resolution_state": proposal["resolution_state"],
                    "match_layer": proposal["match_layer"],
                    "auto_confirmed": proposal["auto_confirmed"],
                },
                "checks": checks,
            }
        )

    total = len(results)
    precision_stub = round(passed / total, 4) if total else 0.0
    return {
        "benchmark_id": stub.get("benchmark_id", "ENTITY-RES-BENCH-STUB"),
        "version": stub.get("version", "1.0"),
        "blinding": stub.get("blinding"),
        "passed": passed == total and total > 0,
        "counts": {"passed": passed, "failed": total - passed, "total": total},
        "metrics_stub": {
            "case_pass_rate": precision_stub,
            "precision": None,
            "recall": None,
            "note": "Precision and recall require a fully annotated blinded sample; this stub reports case pass rate only.",
        },
        "cases": results,
        "boundary": (
            "Benchmark outcomes are engineering behavioral checks on synthetic blinded fixtures only. "
            "They do not establish substantive entity-resolution accuracy, regulatory authorization, or conformance."
        ),
    }
