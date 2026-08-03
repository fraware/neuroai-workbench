"""Deterministic public/synthetic entity-resolution scale corpus (≥200 cases).

Redistribution-safe synthetic strings only. Does not encode private neural data,
protected captures, or substantive entity truth.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

SCALE_RESOURCE = "RESOLUTION_BENCHMARK_PUBLIC_SCALE.json"
SCALE_CASE_TARGET = 200
PARTITION_COUNTS = {"train": 140, "dev": 30, "test": 30}
BOUNDARY = (
    "Public/synthetic redistribution-safe annotated corpus for engineering metrics only. "
    "Partitions are frozen for reproducible evaluation. Metrics do not establish substantive "
    "entity identity. Ops ≥60 protected annotations remain ops-gated and are not committed here. "
    "#37 layers 5–6 (relationship ranking / model-assisted suggestions) remain deferred."
)

# Category templates: (category, raw_mention_template, expected_state, match_layer, flags)
_TEMPLATES: list[tuple[str, str, str, str, dict[str, Any]]] = [
    (
        "exact_id",
        "Synthetic Neuro Devices Inc.",
        "EXISTING_ENTITY",
        "EXACT_ENTITY_ID",
        {"entity_id": "ENT-SYNTH-ORG-001"},
    ),
    ("alias", "Synthetic Neuro", "EXISTING_ENTITY", "EXACT_ALIAS_ID", {"alias_id": "ALIAS-SYNTH-001"}),
    (
        "domain",
        "synthetic-neuro.example.org",
        "EXISTING_ENTITY",
        "EXACT_IDENTIFIER",
        {
            "identifier_scheme": "DOMAIN",
            "identifier_value": "synthetic-neuro.example.org",
        },
    ),
    (
        "normalized_org",
        "Synthetic Neuro Devices Inc.",
        "DUPLICATE_CANDIDATE",
        "NORMALIZED_NAME",
        {
            "entity_id": "ENT-SYNTH-ORG-001",
        },
    ),
    (
        "system_exact",
        "Synthetic Closed-Loop DBS Platform",
        "DUPLICATE_CANDIDATE",
        "NORMALIZED_NAME",
        {
            "entity_id": "ENT-SYNTH-SYS-001",
        },
    ),
    ("rename", "Synthetic Neuro Devices Holdings {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("acquisition", "Synthetic Neuro Devices acquired unit {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("parent_sub", "Synthetic Neuro Devices Research Lab {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("lab_collision", "Synthetic Neuro Lab {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("product_vs_company", "Synthetic Neuro Implant System {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("sponsor_vs_site", "Synthetic Neuro University Trial Site {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("abbr", "SND-{n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("historical_id", "Legacy Synthetic Neuro Devices {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("cjk", "合成神经组织{n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("arabic", "منظمة ألفا العصبية {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("scripts_mixed", "Synthetic Νeuro Devices {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("false_merge_guard", "Unrelated Beta Devices Cohort {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("funding_vehicle", "Synthetic Neuro Fund {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("regulator_office", "Synthetic Device Review Office {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("supplier", "Synthetic Component Supplier GmbH {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("hospital", "Synthetic University Hospital BCI Unit {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("relationship_ambiguity", "Synthetic Neuro Devices partner clinic {n}", "NEW_ENTITY", "NO_MATCH", {}),
    ("adversarial_near_collision", "Synthetic Neuro Devicez Inc {n}", "NEW_ENTITY", "NO_MATCH", {}),
    (
        "adversarial_whitespace",
        "  Synthetic Neuro Devices Inc.  ",
        "DUPLICATE_CANDIDATE",
        "NORMALIZED_NAME",
        {
            "entity_id": "ENT-SYNTH-ORG-001",
        },
    ),
    (
        "abstain_relationship_ambiguity",
        "Synthetic Neuro Devices affiliate clinic {n}",
        "NEW_ENTITY",
        "NO_MATCH",
        {"abstain": True},
    ),
]


def _partition_for_index(index: int) -> str:
    if index < PARTITION_COUNTS["train"]:
        return "train"
    if index < PARTITION_COUNTS["train"] + PARTITION_COUNTS["dev"]:
        return "dev"
    return "test"


def build_public_scale_cases(*, case_count: int = SCALE_CASE_TARGET) -> list[dict[str, Any]]:
    """Build deterministic annotated cases covering multilingual/adversarial/relationship ambiguity."""
    if case_count < 20:
        raise ValueError("Scale corpus must include at least 20 cases")
    cases: list[dict[str, Any]] = []
    for index in range(case_count):
        category, mention_tmpl, state, layer, flags = _TEMPLATES[index % len(_TEMPLATES)]
        n = index + 1
        mention = mention_tmpl.replace("{n}", str(n))
        case_input: dict[str, Any] = {
            "raw_mention": mention,
            "source_capture_ref": f"CAP-SCALE-{n:04d}",
            "category": category,
            "partition": _partition_for_index(index),
        }
        if category == "exact_id":
            case_input["entity_id"] = flags["entity_id"]
        elif category == "alias":
            case_input["alias_id"] = flags["alias_id"]
        elif category == "domain":
            case_input["identifier_scheme"] = flags["identifier_scheme"]
            case_input["identifier_value"] = flags["identifier_value"]

        expected: dict[str, Any] = {
            "resolution_state": state,
            "match_layer": layer,
            "auto_confirmed": category == "exact_id",
            "requires_human_confirmation": category != "exact_id",
        }
        if "entity_id" in flags and not flags.get("abstain"):
            expected["entity_id"] = flags["entity_id"]
        if flags.get("abstain"):
            expected["abstain"] = True

        cases.append(
            {
                "case_id": f"SCALE-{n:04d}",
                "input": case_input,
                "expected": expected,
            }
        )
    return cases


def build_public_scale_document(*, case_count: int = SCALE_CASE_TARGET) -> dict[str, Any]:
    cases = build_public_scale_cases(case_count=case_count)
    partitions = {
        name: [case["case_id"] for case in cases if case["input"]["partition"] == name]
        for name in ("train", "dev", "test")
    }
    return {
        "benchmark_id": "ENTITY-RES-BENCH-PUBLIC-SCALE-001",
        "version": "1.0",
        "status": "PUBLIC_REDISTRIBUTION_SAFE_SCALE",
        "case_count": len(cases),
        "partitions": {
            "frozen": True,
            "counts": {name: len(ids) for name, ids in partitions.items()},
            "case_ids": partitions,
        },
        "blinding": (
            "Synthetic public mentions only; multilingual and adversarial variants use "
            "redistribution-safe strings. No private participant or protected registry strings."
        ),
        "boundary": BOUNDARY,
        "cases": cases,
    }


def load_public_scale_corpus() -> dict[str, Any]:
    payload = json.loads(
        files("neuroai_workbench.resources.entities").joinpath(SCALE_RESOURCE).read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise ValueError("Public scale corpus must be an object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < SCALE_CASE_TARGET:
        raise ValueError(f"Public scale corpus must include at least {SCALE_CASE_TARGET} cases")
    return cast(dict[str, Any], payload)


def filter_corpus_by_partition(document: dict[str, Any], partition: str | None) -> dict[str, Any]:
    if partition is None:
        return document
    if partition not in {"train", "dev", "test"}:
        raise ValueError(f"Unsupported partition {partition!r}; expected train|dev|test")
    cases = [
        case
        for case in document.get("cases", [])
        if isinstance(case, dict)
        and isinstance(case.get("input"), dict)
        and case["input"].get("partition") == partition
    ]
    filtered = dict(document)
    filtered["cases"] = cases
    filtered["case_count"] = len(cases)
    filtered["active_partition"] = partition
    return filtered


def write_public_scale_resource(path: Path | None = None) -> Path:
    """Regenerate the committed scale resource (deterministic)."""
    target = path or (Path(__file__).resolve().parents[1] / "resources" / "entities" / SCALE_RESOURCE)
    document = build_public_scale_document()
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
