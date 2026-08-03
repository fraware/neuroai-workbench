from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..util import utc_now
from .boundary import DISCOVERY_BOUNDARY
from .errors import (
    DiscoveryAdjudicationRequiredError,
    DiscoveryError,
    DiscoveryOverwriteRefusedError,
)
from .ids import new_adjudication_id, new_proposal_id, new_run_id, new_successor_id
from .network import require_network_discovery_allowed, validate_discovery_url
from .store import (
    get_fixture_query,
    get_offline_result_set,
    load_proposal,
    load_query,
    load_run,
    store_adjudication,
    store_proposal,
    store_run,
    store_successor,
)

DECISION_TO_STATUS = {
    "ACCEPT": "ACCEPTED",
    "REJECT": "REJECTED",
    "DEFER": "DEFERRED",
    "EXCLUDE": "EXCLUDED",
}


def _execution_date(executed_at: str) -> str:
    return executed_at[:10]


def _known_source_index(
    known_sources: list[Mapping[str, Any]] | None,
) -> dict[str, str]:
    """Map normalized URL or source_id → source_id for duplicate detection."""
    index: dict[str, str] = {}
    for source in known_sources or []:
        source_id = str(source.get("source_id", "")).strip()
        url = str(source.get("url", "")).strip().rstrip("/").lower()
        if source_id:
            index[f"id:{source_id}"] = source_id
        if url:
            index[f"url:{url}"] = source_id or url
    return index


def _classify_record(
    record: Mapping[str, Any],
    known: dict[str, str],
) -> dict[str, Any]:
    hint = str(record.get("classification_hint", "NEW")).upper()
    url = record.get("url")
    url_norm = str(url).strip().rstrip("/").lower() if url else ""
    suggested = str(record.get("suggested_source_id", "")).strip()

    if hint == "EXCLUDED" or record.get("exclusion_reason"):
        return {
            "record_key": str(record["record_key"]),
            "classification": "EXCLUDED",
            "title": str(record["title"]),
            "url": url if isinstance(url, str) else None,
            "exclusion_reason": str(record.get("exclusion_reason") or "Excluded by discovery classification"),
            "duplicate_of_source_id": None,
        }

    duplicate_of = record.get("duplicate_of_source_id")
    if hint == "DUPLICATE" or (url_norm and f"url:{url_norm}" in known) or (suggested and f"id:{suggested}" in known):
        resolved = str(duplicate_of) if duplicate_of else known.get(f"url:{url_norm}") or known.get(f"id:{suggested}")
        return {
            "record_key": str(record["record_key"]),
            "classification": "DUPLICATE",
            "title": str(record["title"]),
            "url": url if isinstance(url, str) else None,
            "exclusion_reason": None,
            "duplicate_of_source_id": resolved,
        }

    return {
        "record_key": str(record["record_key"]),
        "classification": "NEW",
        "title": str(record["title"]),
        "url": url if isinstance(url, str) else None,
        "exclusion_reason": None,
        "duplicate_of_source_id": None,
    }


def _proposal_from_record(
    *,
    run_id: str,
    query_id: str,
    record: Mapping[str, Any],
    classification: Mapping[str, Any],
    actor: str,
    created_at: str,
) -> dict[str, Any]:
    status = "EXCLUDED" if classification["classification"] == "EXCLUDED" else "PENDING_HUMAN_ACCEPTANCE"
    return {
        "proposal_id": new_proposal_id(),
        "run_id": run_id,
        "query_id": query_id,
        "created_at": created_at,
        "created_by": actor,
        "classification": classification["classification"],
        "proposed_source": {
            "record_key": str(record["record_key"]),
            "title": str(record["title"]),
            "url": classification.get("url"),
            "publisher": str(record.get("publisher") or "UNKNOWN_PUBLISHER"),
            "source_class": str(record.get("source_class") or "CONTROLLED_DISCOVERY_RECORD"),
            "suggested_source_id": str(record.get("suggested_source_id") or record["record_key"]),
            "notes": None,
        },
        "duplicate_of_source_id": classification.get("duplicate_of_source_id"),
        "exclusion_reason": classification.get("exclusion_reason"),
        "status": status,
        "adjudication_id": None,
        "automatic_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }


def execute_discovery_query(
    workspace: Path,
    query_id: str,
    *,
    actor: str = "local-user",
    execution_mode: str = "OFFLINE_FIXTURE",
    result_records: list[Mapping[str, Any]] | None = None,
    known_sources: list[Mapping[str, Any]] | None = None,
    executed_at: str | None = None,
) -> dict[str, Any]:
    """Execute a discovery query into a run + candidate proposals.

    Default mode is offline fixture/replay. Opt-in network mode requires
    ``NEUROAI_LIVE_DISCOVERY=1`` and validates every result URL with the collector SSRF policy.
    Never mutates a live monitor registry.
    """
    try:
        query = load_query(workspace, query_id)
    except ValueError:
        query = get_fixture_query(query_id)

    when = executed_at or utc_now()
    network_gate: dict[str, object] | None = None

    if execution_mode == "OFFLINE_FIXTURE":
        records = list(result_records) if result_records is not None else get_offline_result_set(query_id)
    elif execution_mode == "OPT_IN_NETWORK":
        network_gate = require_network_discovery_allowed()
        if result_records is None:
            raise DiscoveryError(
                "OPT_IN_NETWORK execution requires caller-supplied result_records; "
                "this package does not embed live HTTP clients (collector transport remains separate)."
            )
        records = list(result_records)
        for record in records:
            url = record.get("url")
            if isinstance(url, str) and url.strip():
                validate_discovery_url(url)
    else:
        raise DiscoveryError(f"Unsupported execution_mode {execution_mode!r}")

    known = _known_source_index(known_sources)
    run_id = new_run_id()
    classifications: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    for record in records:
        classification = _classify_record(record, known)
        classifications.append(classification)
        proposal = _proposal_from_record(
            run_id=run_id,
            query_id=query_id,
            record=record,
            classification=classification,
            actor=actor,
            created_at=when,
        )
        store_proposal(workspace, proposal)
        proposals.append(proposal)

    counts = {
        "total": len(classifications),
        "new": sum(1 for item in classifications if item["classification"] == "NEW"),
        "duplicate": sum(1 for item in classifications if item["classification"] == "DUPLICATE"),
        "excluded": sum(1 for item in classifications if item["classification"] == "EXCLUDED"),
    }

    pending_count = sum(1 for item in proposals if item["status"] == "PENDING_HUMAN_ACCEPTANCE")
    if not proposals or pending_count == 0:
        initial_adjudication_status = "COMPLETE"
    else:
        initial_adjudication_status = "PENDING_HUMAN_REVIEW"

    run = {
        "run_id": run_id,
        "query_id": query_id,
        "executed_at": when,
        "executed_by": actor,
        "execution_mode": execution_mode,
        "execution_date": _execution_date(when),
        "source_system": query["source_system"],
        "result_counts": counts,
        "record_classifications": classifications,
        "proposal_ids": [item["proposal_id"] for item in proposals],
        "adjudication_status": initial_adjudication_status,
        "network_gate": network_gate,
        "automatic_registry_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }
    store_run(workspace, run)
    return {
        "run": run,
        "proposals": proposals,
        "query": query,
    }


def adjudicate_candidate_source(
    workspace: Path,
    proposal_id: str,
    decision: str,
    *,
    rationale: str,
    actor: str = "local-user",
    create_successor: bool = True,
    base_registry_version: str = "unversioned-base",
    proposed_registry_version: str | None = None,
    adjudicated_at: str | None = None,
) -> dict[str, Any]:
    """Record human disposition. ACCEPT may draft an append-only registry successor; never overwrites."""
    proposal = load_proposal(workspace, proposal_id)
    if proposal["status"] != "PENDING_HUMAN_ACCEPTANCE":
        raise DiscoveryError(
            f"Proposal {proposal_id} status is {proposal['status']!r}; "
            "only PENDING_HUMAN_ACCEPTANCE proposals may be adjudicated"
        )
    if decision not in DECISION_TO_STATUS:
        raise DiscoveryError(f"Unsupported decision {decision!r}")

    when = adjudicated_at or utc_now()
    adjudication_id = new_adjudication_id()
    successor_id: str | None = None
    successor: dict[str, Any] | None = None

    if decision == "ACCEPT" and create_successor:
        if proposal["classification"] != "NEW":
            raise DiscoveryError("Only NEW candidate sources may be accepted into a registry successor")
        url = proposal["proposed_source"].get("url")
        if not isinstance(url, str) or not url.strip():
            raise DiscoveryError("Accepted proposals require a non-empty public URL")
        validate_discovery_url(url)
        successor_id = new_successor_id()
        version = proposed_registry_version or f"successor-{successor_id[-8:]}"
        successor = {
            "successor_id": successor_id,
            "created_at": when,
            "created_by": actor,
            "base_registry_version": base_registry_version,
            "proposed_registry_version": version,
            "accepted_proposal_ids": [proposal_id],
            "added_sources": [
                {
                    "source_id": proposal["proposed_source"]["suggested_source_id"],
                    "url": url,
                    "publisher": proposal["proposed_source"]["publisher"],
                    "source_class": proposal["proposed_source"]["source_class"],
                    "from_proposal_id": proposal_id,
                    "title": proposal["proposed_source"]["title"],
                }
            ],
            "status": "DRAFT_SUCCESSOR",
            "overwrite_refused": True,
            "automatic_mutation_performed": False,
            "boundary": DISCOVERY_BOUNDARY,
        }
        store_successor(workspace, successor)

    adjudication = {
        "adjudication_id": adjudication_id,
        "proposal_id": proposal_id,
        "run_id": proposal["run_id"],
        "decision": decision,
        "rationale": rationale,
        "adjudicated_at": when,
        "adjudicated_by": actor,
        "identity_boundary": "LOCAL_UNAUTHENTICATED_ATTRIBUTION",
        "registry_successor_id": successor_id,
        "automatic_mutation_performed": False,
        "boundary": DISCOVERY_BOUNDARY,
    }
    store_adjudication(workspace, adjudication)

    updated_proposal = {
        **proposal,
        "status": DECISION_TO_STATUS[decision],
        "adjudication_id": adjudication_id,
        "automatic_mutation_performed": False,
    }
    store_proposal(workspace, updated_proposal)
    _refresh_run_adjudication_status(workspace, proposal["run_id"])

    return {
        "adjudication": adjudication,
        "proposal": updated_proposal,
        "successor": successor,
    }


def refuse_registry_overwrite(
    *,
    target_path: str | None = None,
    message: str | None = None,
) -> None:
    """Explicit refusal of in-place registry mutation."""
    detail = message or "Discovery never silently overwrites a monitor registry; use append-only successors."
    if target_path:
        detail = f"{detail} Refused path: {target_path}"
    raise DiscoveryOverwriteRefusedError(detail)


def require_accepted_proposals_for_successor(proposal_ids: list[str], workspace: Path) -> None:
    if not proposal_ids:
        raise DiscoveryAdjudicationRequiredError("At least one accepted proposal is required")
    for proposal_id in proposal_ids:
        proposal = load_proposal(workspace, proposal_id)
        if proposal["status"] != "ACCEPTED":
            raise DiscoveryAdjudicationRequiredError(
                f"Proposal {proposal_id} is {proposal['status']!r}; human ACCEPT required before succession"
            )


def _refresh_run_adjudication_status(workspace: Path, run_id: str) -> None:
    run = load_run(workspace, run_id)
    statuses = [load_proposal(workspace, pid)["status"] for pid in run["proposal_ids"]]
    pending = sum(1 for status in statuses if status == "PENDING_HUMAN_ACCEPTANCE")
    if pending == len(statuses):
        status = "PENDING_HUMAN_REVIEW"
    elif pending == 0:
        status = "COMPLETE"
    else:
        status = "PARTIALLY_ADJUDICATED"
    store_run(workspace, {**run, "adjudication_status": status})
