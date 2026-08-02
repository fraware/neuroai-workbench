from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from .resolver import propose_resolution

BENCHMARK_RESOURCE = "neuroai_workbench.resources.entities"
BLINDED_BENCHMARK_STUB = "RESOLUTION_BENCHMARK_BLINDED.json"
PUBLIC_ANNOTATED_SUBSET = "RESOLUTION_BENCHMARK_PUBLIC_SUBSET.json"


def load_blinded_benchmark_stub() -> dict[str, Any]:
    payload = json.loads(files(BENCHMARK_RESOURCE).joinpath(BLINDED_BENCHMARK_STUB).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Blinded benchmark stub must be an object")
    return cast(dict[str, Any], payload)


def load_public_annotated_subset() -> dict[str, Any]:
    """Load the public redistribution-safe annotated subset (≥20 cases) for CI metrics."""
    try:
        payload = json.loads(files(BENCHMARK_RESOURCE).joinpath(PUBLIC_ANNOTATED_SUBSET).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing public annotated subset resource {PUBLIC_ANNOTATED_SUBSET}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Public annotated subset must be an object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 20:
        raise ValueError("Public annotated subset must include at least 20 cases")
    return cast(dict[str, Any], payload)


def load_benchmark_document(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        return load_blinded_benchmark_stub()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Benchmark document must be an object")
    return cast(dict[str, Any], payload)


def _annotation_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute precision/recall-style rates when expected entity annotations are present."""
    true_pos = 0
    false_pos = 0
    false_neg = 0
    abstentions = 0
    false_merge = 0
    false_split = 0
    top_k_hits = 0
    annotated = 0

    for item in results:
        expected = item.get("expected")
        observed = item.get("observed")
        if not isinstance(expected, dict) or not isinstance(observed, dict):
            continue
        expected_entity = expected.get("entity_id")
        has_abstain_label = expected.get("resolution_state") == "ABSTAIN" or expected.get("abstain") is True
        if expected_entity is None and not has_abstain_label:
            continue
        annotated += 1
        observed_state = observed.get("resolution_state")
        observed_entity = observed.get("entity_id")
        candidates = observed.get("candidate_entity_ids") or []

        if has_abstain_label:
            if observed_state == "ABSTAIN" or observed.get("auto_confirmed") is False and not observed_entity:
                abstentions += 1
                true_pos += 1
            else:
                false_pos += 1
            continue

        if observed_state == "ABSTAIN":
            abstentions += 1
            false_neg += 1
            continue

        if expected_entity and observed_entity == expected_entity:
            true_pos += 1
            if expected_entity in candidates or not candidates:
                top_k_hits += 1
        elif expected_entity and observed_entity and observed_entity != expected_entity:
            false_pos += 1
            false_merge += 1
        elif expected_entity and not observed_entity:
            false_neg += 1
            false_split += 1
        elif item.get("passed"):
            true_pos += 1
        else:
            false_pos += 1

    precision = round(true_pos / (true_pos + false_pos), 4) if (true_pos + false_pos) else None
    recall = round(true_pos / (true_pos + false_neg), 4) if (true_pos + false_neg) else None
    top_k = round(top_k_hits / annotated, 4) if annotated else None
    return {
        "annotated_cases": annotated,
        "precision": precision,
        "recall": recall,
        "top_k_hit_rate": top_k,
        "abstention_count": abstentions,
        "false_merge_count": false_merge,
        "false_split_count": false_split,
        "true_positives": true_pos,
        "false_positives": false_pos,
        "false_negatives": false_neg,
    }


def run_blinded_benchmark(
    workspace: Path,
    *,
    actor: str = "benchmark-runner",
    benchmark_path: Path | None = None,
) -> dict[str, Any]:
    """Run blinded resolution benchmark cases against a prepared workspace."""
    stub = load_benchmark_document(benchmark_path)
    cases = stub.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Blinded benchmark missing cases array")

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
        if "entity_id" in expected:
            checks["entity_id"] = proposal.get("entity_id") == expected.get("entity_id")
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
                    "entity_id": proposal.get("entity_id"),
                    "candidate_entity_ids": [
                        item.get("entity_id") for item in proposal.get("candidates", []) if isinstance(item, dict)
                    ],
                },
                "checks": checks,
            }
        )

    total = len(results)
    case_pass_rate = round(passed / total, 4) if total else 0.0
    annotation_metrics = _annotation_metrics(results)
    has_annotations = annotation_metrics["annotated_cases"] > 0 and (
        annotation_metrics["precision"] is not None or annotation_metrics["recall"] is not None
    )
    metrics = {
        "case_pass_rate": case_pass_rate,
        "precision": annotation_metrics["precision"] if has_annotations else None,
        "recall": annotation_metrics["recall"] if has_annotations else None,
        "top_k_hit_rate": annotation_metrics["top_k_hit_rate"] if has_annotations else None,
        "abstention_count": annotation_metrics["abstention_count"],
        "false_merge_count": annotation_metrics["false_merge_count"],
        "false_split_count": annotation_metrics["false_split_count"],
        "note": (
            "Measured precision/recall from annotated expected.entity_id / abstain labels."
            if has_annotations
            else "Precision and recall require annotated expected.entity_id fields; case pass rate only otherwise."
        ),
    }
    return {
        "benchmark_id": stub.get("benchmark_id", "ENTITY-RES-BENCH"),
        "version": stub.get("version", "1.0"),
        "blinding": stub.get("blinding"),
        "status": stub.get("status"),
        "passed": passed == total and total > 0,
        "counts": {"passed": passed, "failed": total - passed, "total": total},
        "metrics": metrics,
        "metrics_stub": metrics,  # backward-compatible alias
        "cases": results,
        "boundary": (
            "Benchmark outcomes are engineering behavioral checks. "
            "They do not establish substantive entity-resolution accuracy, regulatory authorization, or conformance."
        ),
    }
