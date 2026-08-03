"""Deterministic public/synthetic extraction scale corpus (≥150 cases).

Uses synthetic redistribution-safe excerpts only. CapturedResponseReplayProvider
remains the primary accuracy lane; fake-offline stays CONTRACT_FIXTURE_NON_ACCURACY.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from .benchmarks import BENCHMARK_ROOT

SCALE_CASE_TARGET = 150
SCALE_CORPUS_NAME = "CORPUS_PUBLIC_SCALE.json"
SCALE_MANIFEST_NAME = "MANIFEST_SCALE.json"
CONCRETE_FIXTURE_DIR = "fixtures/scale"
BOUNDARY = (
    "Public/synthetic redistribution-safe annotated extraction corpus for offline evaluation only. "
    "Capture proves retrieval of the fixture text; extraction proposals require human disposition "
    "and do not establish substantive truth. No private neural data or protected capture bodies."
)

_CATEGORY_SPECS: list[tuple[str, str, str, list[dict[str, str]], list[dict[str, str]]]] = [
    (
        "REGULATORY_RECORD",
        "REGULATORY_RECORD",
        "Example regulator published notice {n} referencing trial NCT{n:08d} on 2026-02-{day:02d}.",
        [
            {"field_type": "EVENT_TYPE", "value": "REGULATORY_NOTICE"},
            {"field_type": "DATE", "value": "DATE_PLACEHOLDER"},
        ],
        [],
    ),
    (
        "CLINICAL_TRIAL",
        "CLINICAL_TRIAL_REGISTRY",
        "Registry status for NCT{n:08d}: Recruiting as of 2026-03-{day:02d}; sponsor SynthTrial Org {n}.",
        [
            {"field_type": "ENTITY_MENTION", "value": "SPONSOR_PLACEHOLDER"},
            {"field_type": "DATE", "value": "DATE_PLACEHOLDER"},
        ],
        [],
    ),
    (
        "PUBLICATION",
        "PEER_REVIEWED_PUBLICATION",
        "Peer-reviewed note {n}: SynthPub Lab {n} reported bounded outcomes for population P-{n} on 2026-01-{day:02d}.",
        [
            {"field_type": "ENTITY_MENTION", "value": "ORG_PLACEHOLDER"},
            {"field_type": "DATE", "value": "DATE_PLACEHOLDER"},
        ],
        [],
    ),
    (
        "COMPANY_ANNOUNCEMENT",
        "OFFICIAL_COMPANY_PAGE",
        "SynthDevice Corp {n} announced a limited feasibility study on 2026-03-{day:02d}. Not a regulatory authorization.",
        [
            {"field_type": "ENTITY_MENTION", "value": "ORG_PLACEHOLDER"},
            {"field_type": "DATE", "value": "DATE_PLACEHOLDER"},
        ],
        [],
    ),
    (
        "OWNERSHIP_FUNDING",
        "OFFICIAL_COMPANY_PAGE",
        "Funding note {n}: SynthCapital Fund {n} disclosed a minority stake update on 2026-04-{day:02d}.",
        [
            {"field_type": "ENTITY_MENTION", "value": "ORG_PLACEHOLDER"},
            {"field_type": "DATE", "value": "DATE_PLACEHOLDER"},
        ],
        [],
    ),
    (
        "SAFETY_WITHDRAWAL",
        "REGULATORY_RECORD",
        "Safety bulletin {n}: SynthSafety Board reported voluntary withdrawal review dated 2026-05-{day:02d}.",
        [{"field_type": "EVENT_TYPE", "value": "SAFETY_BULLETIN"}, {"field_type": "DATE", "value": "DATE_PLACEHOLDER"}],
        [],
    ),
    (
        "CONTRADICTORY_SOURCE",
        "PUBLICATION",
        "Source A for case {n} reports improved throughput. Source B in the same capture states throughput was unchanged.",
        [],
        [{"field_type": "CHANGE_CLASS", "reason": "Contradictory excerpts require human adjudication."}],
    ),
]


def _fixture_id(index: int) -> str:
    digest = hashlib.sha256(f"extraction-scale-fixture-{index}".encode()).hexdigest()
    return f"FIX-{digest[:32]}"


def _content_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_scale_cases(*, case_count: int = SCALE_CASE_TARGET) -> list[dict[str, Any]]:
    if case_count < 1:
        raise ValueError("Scale corpus must include at least one case")
    cases: list[dict[str, Any]] = []
    for index in range(case_count):
        category, source_class, text_tmpl, fields_tmpl, abstentions_tmpl = _CATEGORY_SPECS[index % len(_CATEGORY_SPECS)]
        n = index + 1
        day = (n % 28) + 1
        date_value = f"2026-{(n % 12) + 1:02d}-{day:02d}"
        # Keep dates consistent with template family month where template embeds month.
        if "2026-02-" in text_tmpl:
            date_value = f"2026-02-{day:02d}"
        elif "2026-03-" in text_tmpl:
            date_value = f"2026-03-{day:02d}"
        elif "2026-01-" in text_tmpl:
            date_value = f"2026-01-{day:02d}"
        elif "2026-04-" in text_tmpl:
            date_value = f"2026-04-{day:02d}"
        elif "2026-05-" in text_tmpl:
            date_value = f"2026-05-{day:02d}"

        public_text = text_tmpl.format(n=n, day=day)
        org_placeholders = {
            "CLINICAL_TRIAL": f"SynthTrial Org {n}",
            "PUBLICATION": f"SynthPub Lab {n}",
            "COMPANY_ANNOUNCEMENT": f"SynthDevice Corp {n}",
            "OWNERSHIP_FUNDING": f"SynthCapital Fund {n}",
        }
        expected_fields: list[dict[str, str]] = []
        for field in fields_tmpl:
            value = field["value"]
            if value == "DATE_PLACEHOLDER":
                value = date_value
            elif value == "SPONSOR_PLACEHOLDER":
                value = org_placeholders["CLINICAL_TRIAL"]
            elif value == "ORG_PLACEHOLDER":
                value = org_placeholders[category]
            expected_fields.append({"field_type": field["field_type"], "value": value})

        fixture_id = _fixture_id(index)
        capture = {
            "capture_id": f"CAP-SCALE-{n:04d}",
            "content_sha256": _content_sha(public_text),
            "source_class": source_class,
            "public_text": public_text,
            "boundary": "Synthetic public fixture for preregistered extraction evaluation only.",
        }
        annotation: dict[str, Any] = {
            "fixture_id": fixture_id,
            "boundary": "Annotation stub for blinded benchmark review; not an authoritative ground-truth record.",
        }
        if expected_fields:
            annotation["expected_fields"] = expected_fields
        if abstentions_tmpl:
            annotation["expected_abstentions"] = list(abstentions_tmpl)

        cases.append(
            {
                "fixture_id": fixture_id,
                "category": category,
                "source_class": source_class,
                "capture": capture,
                "annotation": annotation,
                "blinded": True,
            }
        )
    return cases


def build_scale_corpus_document(*, case_count: int = SCALE_CASE_TARGET) -> dict[str, Any]:
    cases = build_scale_cases(case_count=case_count)
    by_category: dict[str, int] = {}
    for case in cases:
        by_category[str(case["category"])] = by_category.get(str(case["category"]), 0) + 1
    return {
        "corpus_id": "EXTRACTION-PUBLIC-SCALE-001",
        "version": "1.0",
        "status": "OFFLINE_ANNOTATED_SCALE",
        "case_count": len(cases),
        "category_counts": by_category,
        "evaluation_lanes": {
            "primary": "captured-response-replay",
            "contract_only": "fake-offline",
            "contract_label": "CONTRACT_FIXTURE_NON_ACCURACY",
        },
        "boundary": BOUNDARY,
        "cases": cases,
    }


def build_scale_manifest(*, case_count: int = SCALE_CASE_TARGET, concrete_limit: int | None = None) -> dict[str, Any]:
    """Build a PREREGISTERED manifest. concrete_limit materializes individual fixture stubs."""
    cases = build_scale_cases(case_count=case_count)
    limit = len(cases) if concrete_limit is None else concrete_limit
    fixtures = []
    for case in cases[:limit]:
        fixture_id = str(case["fixture_id"])
        stem = fixture_id.lower()
        fixtures.append(
            {
                "fixture_id": fixture_id,
                "category": case["category"],
                "capture_stub": f"{CONCRETE_FIXTURE_DIR}/{stem}.capture.json",
                "annotation_stub": f"{CONCRETE_FIXTURE_DIR}/{stem}.annotation.json",
                "blinded": True,
            }
        )
    return {
        "schema_version": "1",
        "benchmark_id": "BENCH-EXT-" + hashlib.sha256(b"extraction-public-scale-v1").hexdigest()[:32],
        "status": "PREREGISTERED",
        "preregistered_at": "2026-08-03T00:00:00Z",
        "categories": [
            "COMPANY_ANNOUNCEMENT",
            "REGULATORY_RECORD",
            "CLINICAL_TRIAL",
            "PUBLICATION",
            "OWNERSHIP_FUNDING",
            "SAFETY_WITHDRAWAL",
            "CONTRADICTORY_SOURCE",
        ],
        "metrics": [
            "field_precision",
            "field_recall",
            "citation_accuracy",
            "unsupported_attribution_rate",
            "entity_resolution_precision",
            "abstention_rate",
            "reviewer_time_saved",
        ],
        "stop_conditions": [
            "unsupported_attribution_rate exceeds preregistered threshold",
            "citation_accuracy below preregistered threshold",
            "protected disclosure not preventable by default-deny controls",
            "provider configuration selected solely on aggregate score",
        ],
        "fixtures": fixtures,
        "boundary": BOUNDARY,
    }


def load_scale_corpus(path: Path | None = None) -> dict[str, Any]:
    target = path or (BENCHMARK_ROOT / SCALE_CORPUS_NAME)
    if not target.is_file():
        raise FileNotFoundError(f"Extraction scale corpus not found at {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Scale corpus must be an object")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < SCALE_CASE_TARGET:
        raise ValueError(f"Scale corpus must include at least {SCALE_CASE_TARGET} cases")
    return cast(dict[str, Any], payload)


def materialize_scale_corpus(
    root: Path | None = None,
    *,
    case_count: int = SCALE_CASE_TARGET,
    concrete_fixture_count: int = 28,
) -> dict[str, Path]:
    """Write compact corpus pack plus a concrete fixture subset for classic stub loading."""
    base = root or BENCHMARK_ROOT
    corpus_path = base / SCALE_CORPUS_NAME
    manifest_path = base / SCALE_MANIFEST_NAME
    fixture_dir = base / CONCRETE_FIXTURE_DIR
    fixture_dir.mkdir(parents=True, exist_ok=True)

    corpus = build_scale_corpus_document(case_count=case_count)
    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    concrete = min(concrete_fixture_count, case_count)
    # Prefer balanced coverage across the four primary classes + contradiction.
    preferred = [
        "REGULATORY_RECORD",
        "CLINICAL_TRIAL",
        "PUBLICATION",
        "COMPANY_ANNOUNCEMENT",
        "CONTRADICTORY_SOURCE",
        "OWNERSHIP_FUNDING",
        "SAFETY_WITHDRAWAL",
    ]
    selected: list[dict[str, Any]] = []
    by_cat: dict[str, list[dict[str, Any]]] = {name: [] for name in preferred}
    for case in corpus["cases"]:
        by_cat.setdefault(str(case["category"]), []).append(case)
    while len(selected) < concrete:
        progressed = False
        for name in preferred:
            bucket = by_cat.get(name) or []
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            progressed = True
            if len(selected) >= concrete:
                break
        if not progressed:
            break

    for case in selected:
        fixture_id = str(case["fixture_id"])
        stem = fixture_id.lower()
        (fixture_dir / f"{stem}.capture.json").write_text(
            json.dumps(case["capture"], ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        (fixture_dir / f"{stem}.annotation.json").write_text(
            json.dumps(case["annotation"], ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    # Scale manifest lists all 150 via corpus-relative synthetic stubs plus concrete subset paths.
    # Classic schema requires capture_stub paths; for non-materialized cases use corpus pack refs.
    manifest = build_scale_manifest(case_count=case_count, concrete_limit=0)
    fixtures = []
    selected_ids = {str(case["fixture_id"]) for case in selected}
    for case in corpus["cases"]:
        fixture_id = str(case["fixture_id"])
        stem = fixture_id.lower()
        if fixture_id in selected_ids:
            capture_stub = f"{CONCRETE_FIXTURE_DIR}/{stem}.capture.json"
            annotation_stub = f"{CONCRETE_FIXTURE_DIR}/{stem}.annotation.json"
        else:
            # Corpus-pack virtual stubs resolved by load_fixture_stub_or_corpus.
            capture_stub = f"corpus:{SCALE_CORPUS_NAME}#{fixture_id}:capture"
            annotation_stub = f"corpus:{SCALE_CORPUS_NAME}#{fixture_id}:annotation"
        fixtures.append(
            {
                "fixture_id": fixture_id,
                "category": case["category"],
                "capture_stub": capture_stub,
                "annotation_stub": annotation_stub,
                "blinded": True,
            }
        )
    manifest["fixtures"] = fixtures
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "corpus": corpus_path,
        "manifest": manifest_path,
        "fixture_dir": fixture_dir,
    }
