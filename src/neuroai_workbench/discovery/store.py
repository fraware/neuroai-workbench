from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ..util import atomic_write_json, ensure_identifier, load_json, safe_join
from .boundary import DISCOVERY_BOUNDARY
from .schemas import (
    ADJUDICATION_SCHEMA,
    PROPOSAL_SCHEMA,
    QUERY_SCHEMA,
    RUN_SCHEMA,
    SUCCESSOR_SCHEMA,
    load_fixture_bundle,
    validate_or_raise,
)

EXPECTED_FIXTURE_QUERY_IDS = (
    "DISCOVERY-CLINICAL-TRIALS-BCI",
    "DISCOVERY-FDA-NEURAL-INTERFACE",
    "DISCOVERY-PUBMED-NEUROAI",
    "DISCOVERY-PATENTS-IMPLANTABLE-BCI",
    "DISCOVERY-GRANTS-NEURAL-DECODING",
    "DISCOVERY-DATASETS-EEG-FOUNDATION-MODEL",
)


def discovery_root(workspace: Path) -> Path:
    return safe_join(workspace, "discovery")


def _queries_dir(workspace: Path) -> Path:
    return discovery_root(workspace) / "queries"


def _runs_dir(workspace: Path) -> Path:
    return discovery_root(workspace) / "runs"


def _proposals_dir(workspace: Path) -> Path:
    return discovery_root(workspace) / "proposals"


def _adjudications_dir(workspace: Path) -> Path:
    return discovery_root(workspace) / "adjudications"


def _successors_dir(workspace: Path) -> Path:
    return discovery_root(workspace) / "registry_successors"


def initialize_discovery_workspace(workspace: Path) -> Path:
    root = discovery_root(workspace)
    for path in (
        _queries_dir(workspace),
        _runs_dir(workspace),
        _proposals_dir(workspace),
        _adjudications_dir(workspace),
        _successors_dir(workspace),
    ):
        path.mkdir(parents=True, exist_ok=True)
    marker = {
        "status": "INITIALIZED",
        "boundary": DISCOVERY_BOUNDARY,
    }
    atomic_write_json(safe_join(root, "workspace.json"), marker)
    return root


def list_fixture_queries() -> list[dict[str, Any]]:
    bundle = load_fixture_bundle()
    queries = cast(list[dict[str, Any]], bundle["queries"])
    for query in queries:
        validate_or_raise(query, QUERY_SCHEMA)
    return queries


def get_fixture_query(query_id: str) -> dict[str, Any]:
    ensure_identifier(query_id, "query_id")
    for query in list_fixture_queries():
        if query["query_id"] == query_id:
            return query
    raise ValueError(f"Unknown fixture discovery query {query_id!r}")


def get_offline_result_set(query_id: str) -> list[dict[str, Any]]:
    ensure_identifier(query_id, "query_id")
    bundle = load_fixture_bundle()
    offline = cast(dict[str, Any], bundle.get("offline_result_sets", {}))
    if query_id not in offline:
        raise ValueError(f"No offline fixture result set for {query_id!r}")
    return cast(list[dict[str, Any]], offline[query_id])


def store_query(workspace: Path, query: dict[str, Any]) -> dict[str, Any]:
    validate_or_raise(query, QUERY_SCHEMA)
    initialize_discovery_workspace(workspace)
    path = safe_join(_queries_dir(workspace), f"{query['query_id']}.json")
    atomic_write_json(path, query)
    return query


def load_query(workspace: Path, query_id: str) -> dict[str, Any]:
    ensure_identifier(query_id, "query_id")
    path = safe_join(_queries_dir(workspace), f"{query_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown discovery query {query_id!r}")
    query = cast(dict[str, Any], load_json(path))
    validate_or_raise(query, QUERY_SCHEMA)
    return query


def store_run(workspace: Path, run: dict[str, Any]) -> dict[str, Any]:
    validate_or_raise(run, RUN_SCHEMA)
    initialize_discovery_workspace(workspace)
    path = safe_join(_runs_dir(workspace), f"{run['run_id']}.json")
    atomic_write_json(path, run)
    return run


def load_run(workspace: Path, run_id: str) -> dict[str, Any]:
    ensure_identifier(run_id, "run_id")
    path = safe_join(_runs_dir(workspace), f"{run_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown discovery run {run_id!r}")
    run = cast(dict[str, Any], load_json(path))
    validate_or_raise(run, RUN_SCHEMA)
    return run


def store_proposal(workspace: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    validate_or_raise(proposal, PROPOSAL_SCHEMA)
    initialize_discovery_workspace(workspace)
    path = safe_join(_proposals_dir(workspace), f"{proposal['proposal_id']}.json")
    atomic_write_json(path, proposal)
    return proposal


def load_proposal(workspace: Path, proposal_id: str) -> dict[str, Any]:
    ensure_identifier(proposal_id, "proposal_id")
    path = safe_join(_proposals_dir(workspace), f"{proposal_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown candidate source proposal {proposal_id!r}")
    proposal = cast(dict[str, Any], load_json(path))
    validate_or_raise(proposal, PROPOSAL_SCHEMA)
    return proposal


def store_adjudication(workspace: Path, adjudication: dict[str, Any]) -> dict[str, Any]:
    validate_or_raise(adjudication, ADJUDICATION_SCHEMA)
    initialize_discovery_workspace(workspace)
    path = safe_join(_adjudications_dir(workspace), f"{adjudication['adjudication_id']}.json")
    atomic_write_json(path, adjudication)
    return adjudication


def load_adjudication(workspace: Path, adjudication_id: str) -> dict[str, Any]:
    ensure_identifier(adjudication_id, "adjudication_id")
    path = safe_join(_adjudications_dir(workspace), f"{adjudication_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown discovery adjudication {adjudication_id!r}")
    adjudication = cast(dict[str, Any], load_json(path))
    validate_or_raise(adjudication, ADJUDICATION_SCHEMA)
    return adjudication


def store_successor(workspace: Path, successor: dict[str, Any]) -> dict[str, Any]:
    validate_or_raise(successor, SUCCESSOR_SCHEMA)
    initialize_discovery_workspace(workspace)
    path = safe_join(_successors_dir(workspace), f"{successor['successor_id']}.json")
    atomic_write_json(path, successor)
    return successor


def load_successor(workspace: Path, successor_id: str) -> dict[str, Any]:
    ensure_identifier(successor_id, "successor_id")
    path = safe_join(_successors_dir(workspace), f"{successor_id}.json")
    if not path.is_file():
        raise ValueError(f"Unknown registry successor proposal {successor_id!r}")
    successor = cast(dict[str, Any], load_json(path))
    validate_or_raise(successor, SUCCESSOR_SCHEMA)
    return successor


def seed_fixture_queries(workspace: Path) -> list[dict[str, Any]]:
    stored = [store_query(workspace, query) for query in list_fixture_queries()]
    return stored
