from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_PROTOCOL_ID = "SCIENCE-DISCOVERY-PROTOCOL-V0.1"
EXPECTED_PROTOCOL_STATUS = "FROZEN_PROTOCOL_NO_PRODUCTION_ACQUISITION_YET"
EXPECTED_COMPILATION_ID = "SCIENCE-QUERY-COMPILATION-V0.2"
EXPECTED_COMPILATION_STATUS = "FROZEN_COMPILATION_NO_PRODUCTION_ACQUISITION_YET"
EXPECTED_PROVIDER_SCOPE = ("CROSSREF", "EUROPE_PMC")
EXPECTED_QUERY_FAMILIES = (
    "QF-NEURAL-INTERFACE",
    "QF-NEURAL-DECODING",
    "QF-CLOSED-LOOP",
    "QF-ML-NEURAL-DATA",
    "QF-NONINVASIVE-DECODING",
    "QF-NEURAL-DATA-INFRA",
)


class ScienceContractError(ValueError):
    """Raised when frozen S2 science-discovery inputs violate the runtime contract."""


@dataclass(frozen=True)
class ScienceContractBundle:
    protocol_path: Path
    compilation_path: Path
    protocol_raw_sha256: str
    compilation_raw_sha256: str
    protocol_canonical_sha256: str
    compilation_canonical_sha256: str
    protocol: dict[str, Any]
    compilation: dict[str, Any]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json_object(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    path = path.resolve()
    if not path.is_file():
        raise ScienceContractError(f"{label} path is not a file: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScienceContractError(f"{label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ScienceContractError(f"{label} JSON root must be an object: {path}")
    return raw, value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScienceContractError(message)


def _validate_protocol(protocol: dict[str, Any]) -> None:
    _require(protocol.get("protocol_id") == EXPECTED_PROTOCOL_ID, "unexpected discovery protocol id")
    _require(protocol.get("status") == EXPECTED_PROTOCOL_STATUS, "discovery protocol is not in the frozen pre-acquisition state")
    _require(protocol.get("evidence_cutoff") == "2026-08-20T00:00:00Z", "unexpected discovery evidence cutoff")

    families = protocol.get("query_families")
    _require(isinstance(families, list), "query_families must be a list")
    observed_ids: list[str] = []
    observed_terms: set[str] = set()
    for family in families:
        _require(isinstance(family, dict), "query family must be an object")
        family_id = family.get("query_family_id")
        terms = family.get("discovery_terms")
        _require(isinstance(family_id, str) and family_id, "query family id must be non-empty")
        _require(isinstance(terms, list) and terms, f"{family_id}: discovery_terms must be non-empty")
        observed_ids.append(family_id)
        for term in terms:
            _require(isinstance(term, str) and term.strip(), f"{family_id}: discovery term must be non-empty")
            normalized = term.strip().casefold()
            _require(normalized not in observed_terms, f"duplicate discovery term across frozen protocol: {term!r}")
            observed_terms.add(normalized)
    _require(tuple(observed_ids) == EXPECTED_QUERY_FAMILIES, "frozen query-family identity or order changed")

    inclusion = protocol.get("candidate_inclusion")
    _require(isinstance(inclusion, dict), "candidate_inclusion must be an object")
    _require(inclusion.get("relevance_adjudication_required") is True, "relevance adjudication must remain required")
    _require(inclusion.get("automatic_canonical_inclusion") is False, "automatic canonical inclusion must remain disabled")

    dedup = protocol.get("deduplication")
    _require(isinstance(dedup, dict), "deduplication must be an object")
    _require(
        dedup.get("exact_identifier_precedence") == ["DOI", "PMID", "PMCID", "OPENALEX_WORK"],
        "exact identifier precedence changed",
    )
    _require(dedup.get("fuzzy_title_author_matching") == "CANDIDATE_ONLY", "fuzzy matching must remain candidate-only")
    _require(dedup.get("cross_provider_conflicts") == "PRESERVE_AND_ADJUDICATE", "provider conflicts must remain explicit")

    provider_policy = protocol.get("provider_policy")
    _require(isinstance(provider_policy, dict), "provider_policy must be an object")
    _require(
        provider_policy.get("required_for_first_candidate_acquisition") == list(EXPECTED_PROVIDER_SCOPE),
        "first acquisition provider set changed",
    )
    _require(provider_policy.get("provider_absence_effect") == "NONE", "provider absence must have no canonical effect")


def _validate_compilation(protocol: dict[str, Any], compilation: dict[str, Any]) -> None:
    _require(compilation.get("compilation_id") == EXPECTED_COMPILATION_ID, "unexpected query compilation id")
    _require(
        compilation.get("status") == EXPECTED_COMPILATION_STATUS,
        "query compilation is not in the frozen pre-acquisition state",
    )
    _require(compilation.get("protocol_id") == protocol.get("protocol_id"), "query compilation protocol binding mismatch")
    _require(compilation.get("provider_scope") == list(EXPECTED_PROVIDER_SCOPE), "query compilation provider scope changed")

    supersedes = compilation.get("supersedes")
    _require(isinstance(supersedes, dict), "query compilation must record predecessor state")
    _require(supersedes.get("compilation_id") == "SCIENCE-QUERY-COMPILATION-V0.1", "unexpected compilation predecessor")
    _require(supersedes.get("acquisition_state") == "NO_PROVIDER_ACQUISITION_EXECUTED", "predecessor acquisition state is not clean")
    _require(
        supersedes.get("reason") == "PRE_ACQUISITION_DATA_MINIMIZATION_AND_RIGHTS_REVIEW",
        "unexpected query-compilation supersession reason",
    )

    partitioning = compilation.get("partitioning")
    _require(isinstance(partitioning, dict), "partitioning must be an object")
    _require(partitioning.get("mode") == "CALENDAR_YEAR", "unexpected acquisition partition mode")
    _require(partitioning.get("from") == "2015-01-01", "unexpected partition start")
    _require(partitioning.get("through") == "2026-08-20", "unexpected partition end")
    _require(partitioning.get("inclusive") is True, "partition interval must remain inclusive")

    providers = compilation.get("providers")
    _require(isinstance(providers, dict), "providers must be an object")
    _require(tuple(providers) == EXPECTED_PROVIDER_SCOPE, "provider definitions changed or reordered")

    crossref = providers.get("CROSSREF")
    europe_pmc = providers.get("EUROPE_PMC")
    _require(isinstance(crossref, dict) and isinstance(europe_pmc, dict), "both provider contracts are required")
    _require(crossref.get("source_universe_id") == "SU-SCI-CROSSREF", "Crossref source-universe binding mismatch")
    _require(crossref.get("endpoint") == "https://api.crossref.org/works", "Crossref endpoint changed")
    _require(crossref.get("fixed_parameters") == {"rows": "1000", "select": "DOI,title,published"}, "Crossref minimization changed")
    _require(europe_pmc.get("source_universe_id") == "SU-SCI-EUROPEPMC", "Europe PMC source-universe binding mismatch")
    _require(
        europe_pmc.get("endpoint") == "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        "Europe PMC endpoint changed",
    )
    _require(
        europe_pmc.get("fixed_parameters") == {"resultType": "lite", "format": "json", "pageSize": "1000"},
        "Europe PMC minimization changed",
    )

    minimization = compilation.get("data_minimization")
    _require(isinstance(minimization, dict), "data_minimization must be an object")
    _require(minimization.get("state") == "PRE_ACQUISITION_MINIMIZED", "unexpected data-minimization state")
    _require(minimization.get("crossref_selected_fields") == ["DOI", "title", "published"], "Crossref field declaration changed")
    _require(minimization.get("europe_pmc_result_type") == "lite", "Europe PMC result type changed")

    coverage = compilation.get("coverage_semantics")
    _require(isinstance(coverage, dict), "coverage_semantics must be an object")
    _require(coverage.get("query_unit_denominator_method") == "API_TOTAL", "query-unit denominator method changed")
    _require(
        coverage.get("query_unit_completion_claim") == "COMPLETE_WITHIN_FROZEN_QUERY_UNIT_ONLY",
        "query-unit completion boundary changed",
    )
    _require(
        coverage.get("aggregate_union_denominator") == "NOT_CLAIMED_DUE_TO_OVERLAP_ACROSS_TERMS_AND_WINDOWS",
        "aggregate denominator must remain unclaimed",
    )
    _require(coverage.get("deduplicated_union_is_derived") is True, "deduplicated union must remain derived")


def load_science_contract_bundle(protocol_path: Path, compilation_path: Path) -> ScienceContractBundle:
    """Load and fail-closed validate frozen S2 discovery inputs.

    This function performs no network access, writes no files, and produces no
    acquisition or canonical-data side effects.
    """

    protocol_path = Path(protocol_path).resolve()
    compilation_path = Path(compilation_path).resolve()
    protocol_raw, protocol = _read_json_object(protocol_path, "discovery protocol")
    compilation_raw, compilation = _read_json_object(compilation_path, "query compilation")

    _validate_protocol(protocol)
    _validate_compilation(protocol, compilation)

    return ScienceContractBundle(
        protocol_path=protocol_path,
        compilation_path=compilation_path,
        protocol_raw_sha256=_sha256(protocol_raw),
        compilation_raw_sha256=_sha256(compilation_raw),
        protocol_canonical_sha256=_sha256(_canonical_bytes(protocol)),
        compilation_canonical_sha256=_sha256(_canonical_bytes(compilation)),
        protocol=protocol,
        compilation=compilation,
    )
