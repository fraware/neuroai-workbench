from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from ..events import append_event
from ..util import (
    atomic_write_json,
    canonical_json_bytes,
    ensure_identifier,
    load_json,
    safe_join,
    sha256_bytes,
    utc_now,
)
from .errors import AmbiguousResolutionError
from .registry import (
    _append_registry_event,
    _entities_root,
    _events_path,
    load_entity,
    refuse_fuzzy_merge,
    resolve_exact,
)
from .schemas import validate_resolution_disposition, validate_resolution_proposal

RESOLVER_BOUNDARY = (
    "Layered entity resolution proposals identify likely record correspondence only. "
    "They do not establish technical capability, ownership control beyond cited evidence, "
    "regulatory status, clinical benefit, or system conformance. Only exact entity_id matches "
    "may auto-confirm; every other match remains a proposal until a human records disposition."
)

MATCH_LAYERS = frozenset({"EXACT_ENTITY_ID", "EXACT_ALIAS_ID", "EXACT_IDENTIFIER", "NORMALIZED_NAME", "NO_MATCH"})
PROPOSAL_STATES = frozenset({"NEW_ENTITY", "EXISTING_ENTITY", "AMBIGUOUS", "DUPLICATE_CANDIDATE"})
DISPOSITION_DECISIONS = frozenset({"ACCEPT", "REJECT", "DEFER", "DUPLICATE", "NEEDS_EVIDENCE"})
CONFIDENCE_LEVELS = frozenset({"CERTAIN", "HIGH", "MEDIUM", "LOW", "NONE"})

_NORMALIZE_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_mention(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = _NORMALIZE_RE.sub(" ", cleaned)
    return _SPACE_RE.sub(" ", cleaned).strip()


def _proposals_root(workspace: Path) -> Path:
    return _entities_root(workspace) / "proposals"


def _dispositions_root(workspace: Path) -> Path:
    return _entities_root(workspace) / "dispositions"


def _proposal_path(workspace: Path, proposal_id: str) -> Path:
    ensure_identifier(proposal_id, "proposal_id")
    return safe_join(_proposals_root(workspace), f"{proposal_id}.json")


def _disposition_path(workspace: Path, disposition_id: str) -> Path:
    ensure_identifier(disposition_id, "disposition_id")
    return safe_join(_dispositions_root(workspace), f"{disposition_id}.json")


def _require_valid(result: list[dict[str, Any]], label: str) -> None:
    if result:
        raise ValueError(f"{label} failed validation: {json.dumps(result, ensure_ascii=False)}")


def _load_alias_records(workspace: Path) -> list[dict[str, Any]]:
    directory = _entities_root(workspace) / "aliases"
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict) and value.get("status") == "ACTIVE":
            records.append(cast(dict[str, Any], value))
    return records


def _load_identifier_records(workspace: Path) -> list[dict[str, Any]]:
    directory = _entities_root(workspace) / "identifiers"
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict) and value.get("status") == "ACTIVE":
            records.append(cast(dict[str, Any], value))
    return records


def _scan_normalized_name_matches(workspace: Path, normalized_form: str) -> tuple[list[str], list[dict[str, Any]]]:
    matches: list[str] = []
    alias_evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    records_dir = _entities_root(workspace) / "records"
    if records_dir.is_dir():
        for entity_id in sorted(p.stem for p in records_dir.glob("*.json")):
            entity = load_entity(workspace, entity_id)
            if entity.get("status") != "ACTIVE":
                continue
            display_normalized = normalize_mention(str(entity.get("display_name", "")))
            if display_normalized == normalized_form and entity_id not in seen:
                matches.append(entity_id)
                seen.add(entity_id)
                alias_evidence.append(
                    {
                        "entity_id": entity_id,
                        "alias_id": None,
                        "alias_kind": "DISPLAY_NAME",
                        "alias_text": entity.get("display_name"),
                    }
                )
    for alias in _load_alias_records(workspace):
        alias_normalized = normalize_mention(str(alias.get("alias_text", "")))
        if alias_normalized != normalized_form:
            continue
        entity_id = str(alias["entity_id"])
        if entity_id in seen:
            continue
        matches.append(entity_id)
        seen.add(entity_id)
        alias_evidence.append(
            {
                "entity_id": entity_id,
                "alias_id": alias.get("alias_id"),
                "alias_kind": alias.get("alias_kind"),
                "alias_text": alias.get("alias_text"),
            }
        )
    return matches, alias_evidence


def _confidence_for_layer(match_layer: str, candidate_count: int) -> str:
    if match_layer == "EXACT_ENTITY_ID" and candidate_count == 1:
        return "CERTAIN"
    if match_layer in {"EXACT_ALIAS_ID", "EXACT_IDENTIFIER"} and candidate_count == 1:
        return "HIGH"
    if match_layer == "NORMALIZED_NAME" and candidate_count == 1:
        return "MEDIUM"
    if candidate_count > 1:
        return "LOW"
    return "NONE"


def _build_proposal(
    *,
    raw_mention: str,
    normalized_form: str,
    source_capture_ref: str | None,
    resolution_state: str,
    match_layer: str,
    candidate_entity_ids: list[str],
    candidate_identifiers: list[dict[str, Any]],
    alias_evidence: list[dict[str, Any]],
    ambiguity_reason: str | None,
    model_provenance: dict[str, Any] | None,
    auto_confirmed: bool,
    actor: str,
) -> dict[str, Any]:
    proposal_id = f"RES-{uuid4().hex}"
    confidence = _confidence_for_layer(match_layer, len(candidate_entity_ids))
    return {
        "proposal_id": proposal_id,
        "created_at": utc_now(),
        "created_by": actor,
        "raw_mention": raw_mention,
        "normalized_form": normalized_form,
        "source_capture_ref": source_capture_ref,
        "resolution_state": resolution_state,
        "match_layer": match_layer,
        "candidate_entity_ids": candidate_entity_ids,
        "candidate_identifiers": candidate_identifiers,
        "alias_evidence": alias_evidence,
        "confidence": confidence,
        "ambiguity_reason": ambiguity_reason,
        "model_provenance": model_provenance,
        "auto_confirmed": auto_confirmed,
        "automatic_mutation_performed": False,
        "status": "AUTO_CONFIRMED" if auto_confirmed else "PENDING_HUMAN_DISPOSITION",
        "boundary": RESOLVER_BOUNDARY,
    }


def _persist_proposal(workspace: Path, proposal: dict[str, Any], actor: str) -> dict[str, Any]:
    _require_valid(validate_resolution_proposal(proposal), "Resolution proposal")
    _proposals_root(workspace).mkdir(parents=True, exist_ok=True)
    atomic_write_json(_proposal_path(workspace, proposal["proposal_id"]), proposal)
    _append_registry_event(
        workspace,
        "RESOLUTION_PROPOSED",
        proposal["candidate_entity_ids"][0] if len(proposal["candidate_entity_ids"]) == 1 else "UNRESOLVED",
        actor,
        {
            "proposal_id": proposal["proposal_id"],
            "resolution_state": proposal["resolution_state"],
            "match_layer": proposal["match_layer"],
            "auto_confirmed": proposal["auto_confirmed"],
        },
    )
    return proposal


def propose_resolution(
    workspace: Path,
    *,
    raw_mention: str,
    source_capture_ref: str | None = None,
    entity_id: str | None = None,
    alias_id: str | None = None,
    identifier_scheme: str | None = None,
    identifier_value: str | None = None,
    normalized_name: str | None = None,
    similarity_threshold: float | None = None,
    match_mode: str | None = None,
    model_provenance: dict[str, Any] | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    clean_mention = raw_mention.strip()
    if not clean_mention:
        raise ValueError("raw_mention must not be empty")
    if normalized_name is not None:
        refuse_fuzzy_merge(
            workspace,
            reason="Normalized-name override is not supported; use raw_mention for deterministic normalized-name layer",
            actor=actor,
            context={"normalized_name": normalized_name},
        )
    if similarity_threshold is not None:
        refuse_fuzzy_merge(
            workspace,
            reason="Similarity thresholds are not supported; layered resolver never fuzzy-merges automatically",
            actor=actor,
            context={"similarity_threshold": similarity_threshold},
        )
    if match_mode is not None and match_mode not in {"ENTITY_ID", "ALIAS_ID", "IDENTIFIER", "NORMALIZED_NAME"}:
        refuse_fuzzy_merge(
            workspace,
            reason=f"Unsupported or non-exact match_mode {match_mode!r}",
            actor=actor,
            context={"match_mode": match_mode},
        )

    normalized_form = normalize_mention(clean_mention)
    selectors = [entity_id, alias_id, (identifier_scheme, identifier_value)]
    active_selectors = sum(1 for item in selectors if item not in (None, (None, None)))
    if active_selectors > 1:
        raise ValueError("Provide at most one of entity_id, alias_id, or identifier_scheme+identifier_value")

    if entity_id is not None:
        try:
            load_entity(workspace, entity_id)
        except ValueError:
            proposal = _build_proposal(
                raw_mention=clean_mention,
                normalized_form=normalized_form,
                source_capture_ref=source_capture_ref,
                resolution_state="NEW_ENTITY",
                match_layer="EXACT_ENTITY_ID",
                candidate_entity_ids=[],
                candidate_identifiers=[],
                alias_evidence=[],
                ambiguity_reason=f"Explicit entity_id {entity_id!r} not found in registry",
                model_provenance=model_provenance,
                auto_confirmed=False,
                actor=actor,
            )
            return _persist_proposal(workspace, proposal, actor)
        proposal = _build_proposal(
            raw_mention=clean_mention,
            normalized_form=normalized_form,
            source_capture_ref=source_capture_ref,
            resolution_state="EXISTING_ENTITY",
            match_layer="EXACT_ENTITY_ID",
            candidate_entity_ids=[entity_id],
            candidate_identifiers=[],
            alias_evidence=[],
            ambiguity_reason=None,
            model_provenance=model_provenance,
            auto_confirmed=True,
            actor=actor,
        )
        return _persist_proposal(workspace, proposal, actor)

    if alias_id is not None:
        exact = resolve_exact(workspace, alias_id=alias_id, actor=actor)
        if exact["state"] == "UNRESOLVED":
            proposal = _build_proposal(
                raw_mention=clean_mention,
                normalized_form=normalized_form,
                source_capture_ref=source_capture_ref,
                resolution_state="NEW_ENTITY",
                match_layer="EXACT_ALIAS_ID",
                candidate_entity_ids=[],
                candidate_identifiers=[],
                alias_evidence=[],
                ambiguity_reason=f"Alias {alias_id!r} not found in registry",
                model_provenance=model_provenance,
                auto_confirmed=False,
                actor=actor,
            )
            return _persist_proposal(workspace, proposal, actor)
        resolved_id = str(exact["entity_id"])
        alias = cast(dict[str, Any], exact.get("alias", {}))
        proposal = _build_proposal(
            raw_mention=clean_mention,
            normalized_form=normalized_form,
            source_capture_ref=source_capture_ref,
            resolution_state="EXISTING_ENTITY",
            match_layer="EXACT_ALIAS_ID",
            candidate_entity_ids=[resolved_id],
            candidate_identifiers=[],
            alias_evidence=[
                {
                    "entity_id": resolved_id,
                    "alias_id": alias.get("alias_id"),
                    "alias_kind": alias.get("alias_kind"),
                    "alias_text": alias.get("alias_text"),
                }
            ],
            ambiguity_reason=None,
            model_provenance=model_provenance,
            auto_confirmed=False,
            actor=actor,
        )
        return _persist_proposal(workspace, proposal, actor)

    if identifier_scheme is not None or identifier_value is not None:
        if identifier_scheme is None or identifier_value is None:
            raise ValueError("identifier_scheme and identifier_value must be supplied together")
        try:
            exact = resolve_exact(
                workspace,
                identifier_scheme=identifier_scheme,
                identifier_value=identifier_value,
                actor=actor,
            )
        except AmbiguousResolutionError as exc:
            identifier_records = _load_identifier_records(workspace)
            candidate_ids = sorted(
                {
                    str(item["entity_id"])
                    for item in identifier_records
                    if item.get("scheme") == identifier_scheme and item.get("value") == identifier_value.strip()
                }
            )
            proposal = _build_proposal(
                raw_mention=clean_mention,
                normalized_form=normalized_form,
                source_capture_ref=source_capture_ref,
                resolution_state="AMBIGUOUS",
                match_layer="EXACT_IDENTIFIER",
                candidate_entity_ids=candidate_ids,
                candidate_identifiers=[
                    item for item in identifier_records if str(item.get("entity_id")) in candidate_ids
                ],
                alias_evidence=[],
                ambiguity_reason=str(exc),
                model_provenance=model_provenance,
                auto_confirmed=False,
                actor=actor,
            )
            return _persist_proposal(workspace, proposal, actor)
        if exact["state"] == "UNRESOLVED":
            proposal = _build_proposal(
                raw_mention=clean_mention,
                normalized_form=normalized_form,
                source_capture_ref=source_capture_ref,
                resolution_state="NEW_ENTITY",
                match_layer="EXACT_IDENTIFIER",
                candidate_entity_ids=[],
                candidate_identifiers=[],
                alias_evidence=[],
                ambiguity_reason=f"No active identifier {identifier_scheme}={identifier_value.strip()!r}",
                model_provenance=model_provenance,
                auto_confirmed=False,
                actor=actor,
            )
            return _persist_proposal(workspace, proposal, actor)
        resolved_id = str(exact["entity_id"])
        identifier = cast(dict[str, Any], exact.get("identifier", {}))
        proposal = _build_proposal(
            raw_mention=clean_mention,
            normalized_form=normalized_form,
            source_capture_ref=source_capture_ref,
            resolution_state="EXISTING_ENTITY",
            match_layer="EXACT_IDENTIFIER",
            candidate_entity_ids=[resolved_id],
            candidate_identifiers=[identifier],
            alias_evidence=[],
            ambiguity_reason=None,
            model_provenance=model_provenance,
            auto_confirmed=False,
            actor=actor,
        )
        return _persist_proposal(workspace, proposal, actor)

    name_matches, alias_evidence = _scan_normalized_name_matches(workspace, normalized_form)
    if len(name_matches) > 1:
        proposal = _build_proposal(
            raw_mention=clean_mention,
            normalized_form=normalized_form,
            source_capture_ref=source_capture_ref,
            resolution_state="AMBIGUOUS",
            match_layer="NORMALIZED_NAME",
            candidate_entity_ids=name_matches,
            candidate_identifiers=[],
            alias_evidence=alias_evidence,
            ambiguity_reason="Multiple normalized-name matches; human disposition required",
            model_provenance=model_provenance,
            auto_confirmed=False,
            actor=actor,
        )
        return _persist_proposal(workspace, proposal, actor)
    if len(name_matches) == 1:
        proposal = _build_proposal(
            raw_mention=clean_mention,
            normalized_form=normalized_form,
            source_capture_ref=source_capture_ref,
            resolution_state="DUPLICATE_CANDIDATE",
            match_layer="NORMALIZED_NAME",
            candidate_entity_ids=name_matches,
            candidate_identifiers=[],
            alias_evidence=alias_evidence,
            ambiguity_reason="Deterministic normalized-name match; never auto-merged",
            model_provenance=model_provenance,
            auto_confirmed=False,
            actor=actor,
        )
        return _persist_proposal(workspace, proposal, actor)

    proposal = _build_proposal(
        raw_mention=clean_mention,
        normalized_form=normalized_form,
        source_capture_ref=source_capture_ref,
        resolution_state="NEW_ENTITY",
        match_layer="NO_MATCH",
        candidate_entity_ids=[],
        candidate_identifiers=[],
        alias_evidence=[],
        ambiguity_reason=None,
        model_provenance=model_provenance,
        auto_confirmed=False,
        actor=actor,
    )
    return _persist_proposal(workspace, proposal, actor)


def load_resolution_proposal(workspace: Path, proposal_id: str) -> dict[str, Any]:
    path = _proposal_path(workspace, proposal_id)
    if not path.is_file():
        raise ValueError(f"Unknown resolution proposal {proposal_id!r}")
    proposal = cast(dict[str, Any], load_json(path))
    _require_valid(validate_resolution_proposal(proposal), "Stored resolution proposal")
    return proposal


def record_resolution_disposition(
    workspace: Path,
    proposal_id: str,
    decision: str,
    *,
    rationale: str,
    selected_entity_id: str | None = None,
    actor: str = "local-user",
) -> dict[str, Any]:
    if decision not in DISPOSITION_DECISIONS:
        raise ValueError(f"Unsupported disposition decision {decision!r}")
    if not rationale.strip():
        raise ValueError("Disposition rationale is required")
    proposal = load_resolution_proposal(workspace, proposal_id)
    if proposal.get("status") == "DISPOSITION_RECORDED":
        raise ValueError("Resolution proposal already has a recorded disposition")
    if decision == "ACCEPT" and proposal["resolution_state"] == "AMBIGUOUS" and not selected_entity_id:
        raise ValueError("Ambiguous proposals require selected_entity_id on ACCEPT")
    if selected_entity_id is not None:
        ensure_identifier(selected_entity_id, "selected_entity_id")
        if selected_entity_id not in proposal.get("candidate_entity_ids", []):
            raise ValueError("selected_entity_id must be one of the proposal candidate_entity_ids")
    disposition_id = f"RESDIS-{proposal_id.removeprefix('RES-')}"
    disposition = {
        "disposition_id": disposition_id,
        "proposal_id": proposal_id,
        "proposal_sha256": sha256_bytes(canonical_json_bytes(proposal)),
        "decided_at": utc_now(),
        "decided_by": actor,
        "decision": decision,
        "selected_entity_id": selected_entity_id,
        "rationale": rationale.strip(),
        "registry_mutation_performed": False,
        "boundary": RESOLVER_BOUNDARY,
    }
    _require_valid(validate_resolution_disposition(disposition), "Resolution disposition")
    disposition_path = _disposition_path(workspace, disposition_id)
    if disposition_path.exists():
        raise ValueError("A resolution disposition is immutable and already exists")
    _dispositions_root(workspace).mkdir(parents=True, exist_ok=True)
    atomic_write_json(disposition_path, disposition)
    updated_proposal = {**proposal, "status": "DISPOSITION_RECORDED"}
    atomic_write_json(_proposal_path(workspace, proposal_id), updated_proposal)
    append_event(
        _events_path(workspace),
        "RESOLUTION_DISPOSITION_RECORDED",
        actor,
        {"proposal_id": proposal_id, "disposition_id": disposition_id, "decision": decision},
    )
    return disposition


def resolver_status(workspace: Path) -> dict[str, Any]:
    proposals = sorted(_proposals_root(workspace).glob("*.json")) if _proposals_root(workspace).is_dir() else []
    dispositions = (
        sorted(_dispositions_root(workspace).glob("*.json")) if _dispositions_root(workspace).is_dir() else []
    )
    pending = 0
    auto_confirmed = 0
    for path in proposals:
        value = cast(dict[str, Any], load_json(path))
        if value.get("status") == "PENDING_HUMAN_DISPOSITION":
            pending += 1
        if value.get("auto_confirmed") is True:
            auto_confirmed += 1
    return {
        "proposal_count": len(proposals),
        "disposition_count": len(dispositions),
        "pending_disposition_count": pending,
        "auto_confirmed_count": auto_confirmed,
        "boundary": RESOLVER_BOUNDARY,
    }
