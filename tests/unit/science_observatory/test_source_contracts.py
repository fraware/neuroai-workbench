from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from neuroai_workbench.science_observatory.source_contracts import ScienceContractError, load_science_contract_bundle


def _protocol() -> dict:
    return {
        "protocol_id": "SCIENCE-DISCOVERY-PROTOCOL-V0.1",
        "schema_version": "0.1.0",
        "status": "FROZEN_PROTOCOL_NO_PRODUCTION_ACQUISITION_YET",
        "evidence_cutoff": "2026-08-20T00:00:00Z",
        "query_families": [
            {"query_family_id": "QF-NEURAL-INTERFACE", "discovery_terms": ["brain-computer interface"]},
            {"query_family_id": "QF-NEURAL-DECODING", "discovery_terms": ["neural decoding"]},
            {"query_family_id": "QF-CLOSED-LOOP", "discovery_terms": ["closed-loop neurostimulation"]},
            {"query_family_id": "QF-ML-NEURAL-DATA", "discovery_terms": ["machine learning neural data"]},
            {"query_family_id": "QF-NONINVASIVE-DECODING", "discovery_terms": ["EEG decoding"]},
            {"query_family_id": "QF-NEURAL-DATA-INFRA", "discovery_terms": ["neural dataset benchmark"]},
        ],
        "candidate_inclusion": {
            "relevance_adjudication_required": True,
            "automatic_canonical_inclusion": False,
        },
        "deduplication": {
            "exact_identifier_precedence": ["DOI", "PMID", "PMCID", "OPENALEX_WORK"],
            "fuzzy_title_author_matching": "CANDIDATE_ONLY",
            "cross_provider_conflicts": "PRESERVE_AND_ADJUDICATE",
        },
        "provider_policy": {
            "required_for_first_candidate_acquisition": ["CROSSREF", "EUROPE_PMC"],
            "optional_until_credentials_available": ["OPENALEX"],
            "provider_absence_effect": "NONE",
        },
    }


def _compilation() -> dict:
    return {
        "compilation_id": "SCIENCE-QUERY-COMPILATION-V0.2",
        "schema_version": "0.1.0",
        "protocol_id": "SCIENCE-DISCOVERY-PROTOCOL-V0.1",
        "status": "FROZEN_COMPILATION_NO_PRODUCTION_ACQUISITION_YET",
        "supersedes": {
            "compilation_id": "SCIENCE-QUERY-COMPILATION-V0.1",
            "acquisition_state": "NO_PROVIDER_ACQUISITION_EXECUTED",
            "reason": "PRE_ACQUISITION_DATA_MINIMIZATION_AND_RIGHTS_REVIEW",
        },
        "provider_scope": ["CROSSREF", "EUROPE_PMC"],
        "partitioning": {
            "mode": "CALENDAR_YEAR",
            "from": "2015-01-01",
            "through": "2026-08-20",
            "inclusive": True,
        },
        "providers": {
            "CROSSREF": {
                "source_universe_id": "SU-SCI-CROSSREF",
                "endpoint": "https://api.crossref.org/works",
                "fixed_parameters": {"rows": "1000", "select": "DOI,title,published"},
            },
            "EUROPE_PMC": {
                "source_universe_id": "SU-SCI-EUROPEPMC",
                "endpoint": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                "fixed_parameters": {"resultType": "lite", "format": "json", "pageSize": "1000"},
            },
        },
        "data_minimization": {
            "state": "PRE_ACQUISITION_MINIMIZED",
            "crossref_selected_fields": ["DOI", "title", "published"],
            "europe_pmc_result_type": "lite",
        },
        "coverage_semantics": {
            "query_unit_denominator_method": "API_TOTAL",
            "query_unit_completion_claim": "COMPLETE_WITHIN_FROZEN_QUERY_UNIT_ONLY",
            "aggregate_union_denominator": "NOT_CLAIMED_DUE_TO_OVERLAP_ACROSS_TERMS_AND_WINDOWS",
            "deduplicated_union_is_derived": True,
        },
    }


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _bundle(tmp_path: Path, protocol: dict | None = None, compilation: dict | None = None):
    protocol_path = tmp_path / "protocol.json"
    compilation_path = tmp_path / "compilation.json"
    _write(protocol_path, protocol or _protocol())
    _write(compilation_path, compilation or _compilation())
    return load_science_contract_bundle(protocol_path, compilation_path)


def test_valid_external_contract_bundle_is_loaded_without_side_effects(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    assert bundle.protocol_path == (tmp_path / "protocol.json").resolve()
    assert bundle.compilation_path == (tmp_path / "compilation.json").resolve()
    assert len(bundle.protocol_raw_sha256) == 64
    assert len(bundle.compilation_raw_sha256) == 64
    assert len(bundle.protocol_canonical_sha256) == 64
    assert len(bundle.compilation_canonical_sha256) == 64
    assert bundle.protocol["candidate_inclusion"]["automatic_canonical_inclusion"] is False


def test_missing_external_input_fails_closed(tmp_path: Path) -> None:
    compilation_path = tmp_path / "compilation.json"
    _write(compilation_path, _compilation())

    with pytest.raises(ScienceContractError, match="path is not a file"):
        load_science_contract_bundle(tmp_path / "missing.json", compilation_path)


def test_protocol_cannot_enable_automatic_canonical_inclusion(tmp_path: Path) -> None:
    protocol = deepcopy(_protocol())
    protocol["candidate_inclusion"]["automatic_canonical_inclusion"] = True

    with pytest.raises(ScienceContractError, match="automatic canonical inclusion"):
        _bundle(tmp_path, protocol=protocol)


def test_protocol_cannot_disable_relevance_adjudication(tmp_path: Path) -> None:
    protocol = deepcopy(_protocol())
    protocol["candidate_inclusion"]["relevance_adjudication_required"] = False

    with pytest.raises(ScienceContractError, match="relevance adjudication"):
        _bundle(tmp_path, protocol=protocol)


def test_protocol_query_family_identity_and_order_are_frozen(tmp_path: Path) -> None:
    protocol = deepcopy(_protocol())
    protocol["query_families"][0], protocol["query_families"][1] = (
        protocol["query_families"][1],
        protocol["query_families"][0],
    )

    with pytest.raises(ScienceContractError, match="query-family identity or order"):
        _bundle(tmp_path, protocol=protocol)


def test_predecessor_with_provider_acquisition_is_rejected(tmp_path: Path) -> None:
    compilation = deepcopy(_compilation())
    compilation["supersedes"]["acquisition_state"] = "PROVIDER_ACQUISITION_EXECUTED"

    with pytest.raises(ScienceContractError, match="predecessor acquisition state"):
        _bundle(tmp_path, compilation=compilation)


def test_provider_response_minimization_cannot_expand_silently(tmp_path: Path) -> None:
    compilation = deepcopy(_compilation())
    compilation["providers"]["EUROPE_PMC"]["fixed_parameters"]["resultType"] = "core"

    with pytest.raises(ScienceContractError, match="Europe PMC minimization"):
        _bundle(tmp_path, compilation=compilation)


def test_aggregate_literature_denominator_cannot_be_claimed(tmp_path: Path) -> None:
    compilation = deepcopy(_compilation())
    compilation["coverage_semantics"]["aggregate_union_denominator"] = "SUM_OF_API_TOTALS"

    with pytest.raises(ScienceContractError, match="aggregate denominator must remain unclaimed"):
        _bundle(tmp_path, compilation=compilation)
