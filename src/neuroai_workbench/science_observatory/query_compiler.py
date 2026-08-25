from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from .source_contracts import ScienceContractBundle, load_science_contract_bundle

PLAN_STATUS = "FROZEN_QUERY_PLAN_NO_ACQUISITION_EXECUTED"
EXPECTED_FROZEN_PLAN_ID = "SCIENCE-QUERY-PLAN-A9B8B8999861882C4BC7"
EXPECTED_FROZEN_PLAN_SHA256 = "a9b8b8999861882c4bc78b27f40f48e476f7cafbbb347b00a0a6cd897406db56"
EXPECTED_UNIT_COUNT = 768
EXPECTED_PROVIDER_COUNTS = {"CROSSREF": 384, "EUROPE_PMC": 384}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _year_windows(start: str, through: str) -> list[tuple[str, str]]:
    first = date.fromisoformat(start)
    last = date.fromisoformat(through)
    if last < first:
        raise ValueError("partition through date precedes from date")

    windows: list[tuple[str, str]] = []
    year = first.year
    while year <= last.year:
        window_start = max(first, date(year, 1, 1))
        window_end = min(last, date(year, 12, 31))
        windows.append((window_start.isoformat(), window_end.isoformat()))
        year += 1
    return windows


def _escape_europe_pmc_phrase(term: str) -> str:
    return term.replace("\\", "\\\\").replace('"', '\\"')


def _query_unit(
    *,
    provider: str,
    provider_spec: dict[str, Any],
    family_id: str,
    term_index: int,
    term: str,
    window_from: str,
    window_through: str,
) -> dict[str, Any]:
    if provider == "CROSSREF":
        date_filters = provider_spec["date_filter_parameters"]
        filter_value = (
            f"{date_filters['from']}:{window_from},"
            f"{date_filters['through']}:{window_through}"
        )
        parameters = {
            provider_spec["term_parameter"]: term,
            provider_spec["filter_parameter"]: filter_value,
            **provider_spec["fixed_parameters"],
            provider_spec["cursor_parameter"]: provider_spec["initial_cursor"],
        }
    elif provider == "EUROPE_PMC":
        escaped = _escape_europe_pmc_phrase(term)
        query = provider_spec["query_template"].format(
            term=escaped,
            **{"from": window_from, "through": window_through},
        )
        parameters = {
            provider_spec["query_parameter"]: query,
            **provider_spec["fixed_parameters"],
            provider_spec["cursor_parameter"]: provider_spec["initial_cursor"],
        }
    else:
        raise ValueError(f"unsupported provider: {provider}")

    request_basis = {
        "provider": provider,
        "endpoint": provider_spec["endpoint"],
        "parameters": parameters,
        "client_identity": provider_spec["client_identity"],
        "query_family_id": family_id,
        "term_index": term_index,
        "term": term,
        "window": {"from": window_from, "through": window_through},
        "adapter_id": provider_spec["adapter_id"],
        "source_universe_id": provider_spec["source_universe_id"],
    }
    request_sha = _sha256(request_basis)
    return {
        "query_unit_id": f"QUNIT-{provider}-{request_sha[:20].upper()}",
        **request_basis,
        "request_identity_sha256": request_sha,
        "coverage_denominator_method": "API_TOTAL",
        "canonical_effect": "NONE_DISCOVERY_QUERY_ONLY",
    }


def compile_plan(bundle: ScienceContractBundle) -> dict[str, Any]:
    """Compile the exact frozen S2 request contract into deterministic query units."""

    protocol = bundle.protocol
    compilation = bundle.compilation
    partition = compilation["partitioning"]
    windows = _year_windows(partition["from"], partition["through"])

    query_units: list[dict[str, Any]] = []
    for provider in compilation["provider_scope"]:
        provider_spec = compilation["providers"][provider]
        for family in protocol["query_families"]:
            family_id = family["query_family_id"]
            for term_index, term in enumerate(family["discovery_terms"], start=1):
                for window_from, window_through in windows:
                    query_units.append(
                        _query_unit(
                            provider=provider,
                            provider_spec=provider_spec,
                            family_id=family_id,
                            term_index=term_index,
                            term=term,
                            window_from=window_from,
                            window_through=window_through,
                        )
                    )

    ids = [unit["query_unit_id"] for unit in query_units]
    if len(ids) != len(set(ids)):
        raise ValueError("query-unit identity collision")

    provider_counts = {
        provider: sum(unit["provider"] == provider for unit in query_units)
        for provider in compilation["provider_scope"]
    }
    plan_basis = {
        "protocol_id": protocol["protocol_id"],
        "compilation_id": compilation["compilation_id"],
        "evidence_cutoff": protocol["evidence_cutoff"],
        "priority_window": protocol["baseline_strategy"]["priority_window"],
        "query_units": query_units,
    }
    plan_sha = _sha256(plan_basis)
    plan = {
        "plan_id": f"SCIENCE-QUERY-PLAN-{plan_sha[:20].upper()}",
        "schema_version": "0.1.0",
        "status": PLAN_STATUS,
        **plan_basis,
        "unit_count": len(query_units),
        "provider_counts": provider_counts,
        "plan_sha256": plan_sha,
        "coverage_semantics": compilation["coverage_semantics"],
        "authority_boundary": (
            "This file is a deterministic request plan only. It proves no provider request "
            "was sent, no cursor was exhausted, no record was retrieved, and no coverage or "
            "scientific claim was established."
        ),
    }
    validate_frozen_plan_identity(plan)
    return plan


def validate_frozen_plan_identity(plan: dict[str, Any]) -> None:
    expected = {
        "plan_id": EXPECTED_FROZEN_PLAN_ID,
        "plan_sha256": EXPECTED_FROZEN_PLAN_SHA256,
        "unit_count": EXPECTED_UNIT_COUNT,
        "provider_counts": EXPECTED_PROVIDER_COUNTS,
    }
    for key, value in expected.items():
        if plan.get(key) != value:
            raise ValueError(
                f"frozen query plan mismatch for {key}: expected {value!r}, observed {plan.get(key)!r}"
            )


def write_plan(plan: dict[str, Any], output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    output.write_text(rendered, encoding="utf-8")


def compile_from_paths(protocol_path: Path, compilation_path: Path) -> dict[str, Any]:
    return compile_plan(load_science_contract_bundle(protocol_path, compilation_path))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile externally supplied frozen science-discovery contracts into exact provider query units."
    )
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--compilation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = compile_from_paths(args.protocol, args.compilation)
    write_plan(plan, args.output)
    print(
        f"PASS query compilation: {plan['unit_count']} units; "
        f"compilation={plan['compilation_id']}; plan_sha256={plan['plan_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
