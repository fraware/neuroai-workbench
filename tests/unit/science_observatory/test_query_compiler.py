from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from neuroai_workbench.science_observatory.query_compiler import (
    EXPECTED_FROZEN_PLAN_ID,
    EXPECTED_FROZEN_PLAN_SHA256,
    compile_from_paths,
    write_plan,
)
from neuroai_workbench.science_observatory.source_contracts import ScienceContractError

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "science_observatory" / "external_s2"
PROTOCOL = FIXTURES / "discovery-protocol-v0.1.json"
COMPILATION = FIXTURES / "query-compilation-v0.2.json"


def test_exact_frozen_plan_is_reproduced_from_external_s2_fixture() -> None:
    first = compile_from_paths(PROTOCOL, COMPILATION)
    second = compile_from_paths(PROTOCOL, COMPILATION)

    assert first == second
    assert first["plan_id"] == EXPECTED_FROZEN_PLAN_ID
    assert first["plan_sha256"] == EXPECTED_FROZEN_PLAN_SHA256
    assert first["unit_count"] == 768
    assert first["provider_counts"] == {"CROSSREF": 384, "EUROPE_PMC": 384}
    assert first["status"] == "FROZEN_QUERY_PLAN_NO_ACQUISITION_EXECUTED"


def test_first_crossref_unit_preserves_minimized_request_identity() -> None:
    plan = compile_from_paths(PROTOCOL, COMPILATION)
    unit = plan["query_units"][0]

    assert unit["query_unit_id"] == "QUNIT-CROSSREF-4A10006D6D32E6E889D5"
    assert unit["provider"] == "CROSSREF"
    assert unit["query_family_id"] == "QF-NEURAL-INTERFACE"
    assert unit["term"] == "brain-computer interface"
    assert unit["window"] == {"from": "2015-01-01", "through": "2015-12-31"}
    assert unit["parameters"] == {
        "query.title": "brain-computer interface",
        "filter": "from-pub-date:2015-01-01,until-pub-date:2015-12-31",
        "rows": "1000",
        "select": "DOI,title,published",
        "cursor": "*",
    }
    assert unit["coverage_denominator_method"] == "API_TOTAL"
    assert unit["canonical_effect"] == "NONE_DISCOVERY_QUERY_ONLY"


def test_first_europe_pmc_unit_preserves_minimized_request_identity() -> None:
    plan = compile_from_paths(PROTOCOL, COMPILATION)
    unit = next(row for row in plan["query_units"] if row["provider"] == "EUROPE_PMC")

    assert unit["query_unit_id"] == "QUNIT-EUROPE_PMC-109422C08331E6C38F9D"
    assert unit["parameters"] == {
        "query": '(TITLE:"brain-computer interface" OR ABSTRACT:"brain-computer interface") '
        "AND FIRST_PDATE:[2015-01-01 TO 2015-12-31]",
        "resultType": "lite",
        "format": "json",
        "pageSize": "1000",
        "cursorMark": "*",
    }


def test_query_unit_ids_are_unique() -> None:
    plan = compile_from_paths(PROTOCOL, COMPILATION)
    identities = [row["query_unit_id"] for row in plan["query_units"]]
    assert len(identities) == len(set(identities)) == 768


def test_compilation_window_drift_fails_before_plan_creation(tmp_path: Path) -> None:
    value = json.loads(COMPILATION.read_text(encoding="utf-8"))
    value["partitioning"]["through"] = "2026-08-19"
    mutated = tmp_path / "compilation.json"
    mutated.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ScienceContractError, match="unexpected partition end"):
        compile_from_paths(PROTOCOL, mutated)


def test_provider_order_drift_fails_before_plan_creation(tmp_path: Path) -> None:
    value = deepcopy(json.loads(COMPILATION.read_text(encoding="utf-8")))
    value["provider_scope"] = ["EUROPE_PMC", "CROSSREF"]
    mutated = tmp_path / "compilation.json"
    mutated.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ScienceContractError, match="provider scope changed"):
        compile_from_paths(PROTOCOL, mutated)


def test_plan_write_is_explicit_and_does_not_change_authority(tmp_path: Path) -> None:
    plan = compile_from_paths(PROTOCOL, COMPILATION)
    output = tmp_path / "plan.json"
    write_plan(plan, output)

    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == plan
    assert "proves no provider request was sent" in written["authority_boundary"]
    assert (
        written["coverage_semantics"]["aggregate_union_denominator"]
        == "NOT_CLAIMED_DUE_TO_OVERLAP_ACROSS_TERMS_AND_WINDOWS"
    )
