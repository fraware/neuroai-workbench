from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from ..collector.adapters.clinicaltrials import ClinicalTrialsGovAdapter
from .clinicaltrials import project_search_pages
from .errors import DiscoveryError
from .universe_projection import UNIVERSE_PROJECTION_META, project_universe_pages
from .workflow import execute_discovery_query

DISCOVERY_RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"
PROGRAMME_SCHEMA = "SOURCE_UNIVERSE_PROGRAMME.schema.json"
SU_TRIAL_RESOURCE = "SU_TRIAL.programme.json"
SU_TRIAL_ID = "SU-TRIAL"
SU_TRIAL_DOC_ALIAS = "SU-TRIALS"
PRIMA_RECALL_ANCHOR_NCT = "NCT03333954"
PROGRAMME_BOUNDARY = (
    "Source-universe programmes emit discovery candidates and coverage reports only. "
    "They do not mutate S2, live monitor registries, assessments, or canonical graph state."
)
EXECUTION_MODES = frozenset({"OFFLINE_FIXTURE", "OFFLINE_REPLAY", "AUTHORIZED_NETWORK"})

PROGRAMME_RESOURCES: dict[str, str] = {
    "SU-TRIAL": "SU_TRIAL.programme.json",
    "SU-PUBS": "SU_PUBS.programme.json",
    "SU-REG": "SU_REG.programme.json",
    "SU-GRANTS": "SU_GRANTS.programme.json",
    "SU-MODEL": "SU_MODEL.programme.json",
}
# SU-TRIAL remains the reference; other first-wave universes support offline fixture/replay only.
EXECUTABLE_UNIVERSE_IDS = frozenset({SU_TRIAL_ID})
OFFLINE_EXECUTABLE_UNIVERSE_IDS = frozenset(UNIVERSE_PROJECTION_META)
DOCUMENTATION_ALIASES: dict[str, str] = {
    SU_TRIAL_ID: SU_TRIAL_DOC_ALIAS,
    "SU-PUBS": "SU-PUBLICATIONS",
    "SU-REG": "SU-REGULATION",
    "SU-GRANTS": "SU-FUNDING",
    "SU-MODEL": "SU-MODELS-DATASETS",
}
ALIAS_TO_STABLE_ID = {alias: stable for stable, alias in DOCUMENTATION_ALIASES.items()}


def _load_resource(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(DISCOVERY_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def load_programme_schema() -> dict[str, Any]:
    return _load_resource(PROGRAMME_SCHEMA)


def load_su_trial_programme() -> dict[str, Any]:
    return validate_programme(_load_resource(SU_TRIAL_RESOURCE))


def list_programme_ids() -> list[str]:
    return sorted(PROGRAMME_RESOURCES)


def load_programme(universe_id: str) -> dict[str, Any]:
    resource = PROGRAMME_RESOURCES.get(universe_id)
    if resource is None:
        alias_target = ALIAS_TO_STABLE_ID.get(universe_id)
        if alias_target is not None:
            raise DiscoveryError(
                f"Universe id {universe_id!r} is a documentation alias only; stable id is {alias_target!r}"
            )
        raise DiscoveryError(f"Unknown source-universe programme {universe_id!r}")
    return validate_programme(_load_resource(resource))


def load_first_wave_programmes() -> list[dict[str, Any]]:
    return [load_programme(universe_id) for universe_id in list_programme_ids()]


def programme_maturity(programme: Mapping[str, Any]) -> str:
    evaluation = programme.get("evaluation")
    if isinstance(evaluation, Mapping):
        maturity = evaluation.get("maturity")
        if isinstance(maturity, str) and maturity.strip():
            return maturity.strip()
    universe_id = str(programme.get("universe_id"))
    if universe_id in EXECUTABLE_UNIVERSE_IDS:
        return "EXECUTABLE_REFERENCE"
    if universe_id in OFFLINE_EXECUTABLE_UNIVERSE_IDS:
        return "OFFLINE_EXECUTABLE"
    return "SCAFFOLD_NOT_COMPLETE"


def validate_programme(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DiscoveryError("Source-universe programme must be an object")
    validator = Draft202012Validator(load_programme_schema())
    errors = sorted(
        f"{'.'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in validator.iter_errors(value)
    )
    if errors:
        raise DiscoveryError(f"Source-universe programme is invalid: {'; '.join(errors)}")
    universe_id = str(value["universe_id"])
    if universe_id in ALIAS_TO_STABLE_ID:
        raise DiscoveryError(
            f"Universe id {universe_id!r} is a documentation alias only; "
            f"stable id is {ALIAS_TO_STABLE_ID[universe_id]!r}"
        )
    return value


def documentation_alias_for(universe_id: str) -> str | None:
    return DOCUMENTATION_ALIASES.get(universe_id)


def _identity_pattern(programme: Mapping[str, Any]) -> re.Pattern[str]:
    pattern = str(programme["identity_key"]["pattern"])
    return re.compile(pattern)


def _run_offline_universe(
    contract: dict[str, Any],
    *,
    execution_mode: str,
    pages: Sequence[Mapping[str, Any]],
    workspace: Path | None,
    actor: str,
    query_id: str | None,
    query_text: str | None,
    known_identities: Mapping[str, str] | None,
) -> dict[str, Any]:
    universe_id = str(contract["universe_id"])
    stream_id = query_id or str(contract["query_streams"][0])
    projection = project_universe_pages(
        universe_id=universe_id,
        query_id=stream_id,
        query_text=query_text or str(contract["purpose"]),
        pages=pages,
        identity_pattern=str(contract["identity_key"]["pattern"]),
        known_identities=known_identities,
    )
    identity_re = _identity_pattern(contract)
    for record in projection["result_records"]:
        key = str(record["record_key"])
        if not identity_re.fullmatch(key):
            raise DiscoveryError(f"Projected identity {key!r} does not match programme identity_key")

    coverage = {
        **projection["coverage"],
        "universe_id": universe_id,
        "universe_version": contract["universe_version"],
        "execution_mode": execution_mode,
        "documentation_alias": documentation_alias_for(universe_id),
        "maturity": programme_maturity(contract),
        "s2_mutated": False,
        "monitor_registry_mutated": False,
        "boundary": PROGRAMME_BOUNDARY,
    }

    workflow: dict[str, Any] | None = None
    if workspace is not None:
        discovery_mode = "OPT_IN_NETWORK" if execution_mode == "AUTHORIZED_NETWORK" else execution_mode
        if execution_mode == "OFFLINE_FIXTURE":
            discovery_mode = "OFFLINE_FIXTURE"
        workflow = execute_discovery_query(
            workspace,
            stream_id,
            actor=actor,
            execution_mode=discovery_mode,
            result_records=projection["result_records"],
        )
        if workflow["run"].get("automatic_registry_mutation_performed") is not False:
            raise DiscoveryError("Programme execution refused because a registry mutation was recorded")

    return {
        "programme": {
            "universe_id": universe_id,
            "universe_version": contract["universe_version"],
            "documentation_aliases": list(contract.get("documentation_aliases") or []),
            "maturity": programme_maturity(contract),
        },
        "projection": projection,
        "coverage": coverage,
        "workflow": workflow,
        "candidates_only": True,
        "boundary": PROGRAMME_BOUNDARY,
    }


def run_source_universe(
    *,
    programme: Mapping[str, Any],
    execution_mode: str,
    pages: Sequence[Mapping[str, Any]] | None = None,
    workspace: Path | None = None,
    actor: str = "local-user",
    query_id: str | None = None,
    query_text: str | None = None,
    known_nct_sources: Mapping[str, str] | None = None,
    known_identities: Mapping[str, str] | None = None,
    adapter: ClinicalTrialsGovAdapter | None = None,
) -> dict[str, Any]:
    """Execute a source-universe programme into candidates only.

    AUTHORIZED_NETWORK here means caller-supplied pages from a separately authorized
    capture. This function still has no embedded HTTP client.
    """
    contract = validate_programme(dict(programme))
    if execution_mode not in EXECUTION_MODES:
        raise DiscoveryError(f"Unsupported programme execution_mode {execution_mode!r}")
    if execution_mode == "AUTHORIZED_NETWORK":
        from .network import require_network_discovery_allowed

        require_network_discovery_allowed()

    universe_id = str(contract["universe_id"])
    if universe_id in OFFLINE_EXECUTABLE_UNIVERSE_IDS:
        if not pages:
            raise DiscoveryError(f"{universe_id} execution requires caller-supplied pages")
        if execution_mode == "AUTHORIZED_NETWORK":
            raise DiscoveryError(
                f"{universe_id} supports OFFLINE_FIXTURE and OFFLINE_REPLAY only in this slice; "
                "live network capture remains separately authorized outside discovery"
            )
        return _run_offline_universe(
            contract,
            execution_mode=execution_mode,
            pages=pages,
            workspace=workspace,
            actor=actor,
            query_id=query_id,
            query_text=query_text,
            known_identities=known_identities,
        )

    if universe_id != SU_TRIAL_ID:
        raise DiscoveryError(f"No executable adapter is registered for universe_id {universe_id!r} in this slice")
    if not pages:
        raise DiscoveryError("SU-TRIAL execution requires caller-supplied ClinicalTrials.gov search pages")

    stream_id = query_id or str(contract["query_streams"][0])
    projection = project_search_pages(
        adapter or ClinicalTrialsGovAdapter.__new__(ClinicalTrialsGovAdapter),
        query_id=stream_id,
        query_text=query_text or str(contract["purpose"]),
        pages=pages,
        required_study_types=["INTERVENTIONAL"]
        if "interventional" in " ".join(contract["inclusion"]).lower()
        else None,
        known_nct_sources=known_nct_sources,
    )
    identity_re = _identity_pattern(contract)
    for record in projection["result_records"]:
        key = str(record["record_key"])
        if not identity_re.fullmatch(key):
            raise DiscoveryError(f"Projected identity {key!r} does not match programme identity_key")

    coverage = {
        **projection["coverage"],
        "universe_id": contract["universe_id"],
        "universe_version": contract["universe_version"],
        "execution_mode": execution_mode,
        "documentation_alias": documentation_alias_for(str(contract["universe_id"])),
        "prima_query_hardcoded": False,
        "recall_anchor_nct": PRIMA_RECALL_ANCHOR_NCT,
        "recall_anchor_role": "EXTERNAL_RECALL_ANCHOR_ONLY",
        "maturity": "EXECUTABLE_REFERENCE",
        "s2_mutated": False,
        "monitor_registry_mutated": False,
        "boundary": PROGRAMME_BOUNDARY,
    }

    workflow: dict[str, Any] | None = None
    if workspace is not None:
        discovery_mode = "OPT_IN_NETWORK" if execution_mode == "AUTHORIZED_NETWORK" else execution_mode
        if execution_mode == "OFFLINE_FIXTURE":
            discovery_mode = "OFFLINE_FIXTURE"
        workflow = execute_discovery_query(
            workspace,
            stream_id,
            actor=actor,
            execution_mode=discovery_mode,
            result_records=projection["result_records"],
        )
        if workflow["run"].get("automatic_registry_mutation_performed") is not False:
            raise DiscoveryError("Programme execution refused because a registry mutation was recorded")

    return {
        "programme": {
            "universe_id": contract["universe_id"],
            "universe_version": contract["universe_version"],
            "documentation_aliases": list(contract.get("documentation_aliases") or []),
            "maturity": "EXECUTABLE_REFERENCE",
        },
        "projection": projection,
        "coverage": coverage,
        "workflow": workflow,
        "candidates_only": True,
        "boundary": PROGRAMME_BOUNDARY,
    }
