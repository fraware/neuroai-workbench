from __future__ import annotations

import json
from collections import Counter, defaultdict
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, cast
from uuid import uuid4

from jsonschema import Draft202012Validator

from .events import append_event, load_events, verify_chain
from .governance_opinions import (
    GOVERNANCE_OPINION_BOUNDARY,
    load_governance_reviewer_opinions,
    verify_governance_reviewer_opinions,
)
from .util import atomic_write_json, canonical_json_bytes, ensure_identifier, load_json, sha256_bytes, utc_now
from .workspace import Workspace

OPERATIONS_RESOURCE_PACKAGE = "neuroai_workbench.resources.operations"
DISPOSITION_SCHEMA = "GOVERNANCE_OWNER_DISPOSITION.schema.json"
SCHEMA_VERSION = "1"
RUNTIME_PRIVATE_KEYS = frozenset({"_path"})
PROTECTED_PREFIX = "protected-ref:"

DISPOSITION_STATES = frozenset(
    {
        "ACCEPT",
        "ACCEPT_WITH_ACTION",
        "REJECT",
        "DEFER",
        "REQUEST_FURTHER_REVIEW",
    }
)
CONDITION_PRIORITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})
CONDITION_STATUSES = frozenset({"OPEN", "IN_PROGRESS", "RESOLVED"})
RELEASE_EFFECTS = frozenset({"BLOCKS_RELEASE", "NON_BLOCKING"})
STORAGE_BOUNDARIES = frozenset({"PUBLIC_GIT", "GENERATED_OUTPUT", "PROTECTED_WORKSPACE", "ARCHIVE"})

OWNER_DISPOSITION_BOUNDARY = (
    "Owner dispositions preserve claimed local owner attribution over exact governance-scope and reviewer-opinion "
    "digests. They do not erase reviewer disagreement, convert unresolved evidence into failure, authenticate "
    "institutional delegation, establish release readiness, or authorize publication."
)
CONDITION_REGISTER_BOUNDARY = (
    "The unresolved-condition register preserves condition lineage, ownership, status, closure evidence, and "
    "explicit release effect. Register integrity does not establish substantive closure or release authority."
)


def _schema(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(OPERATIONS_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")),
    )


def _schema_errors(value: Any) -> list[dict[str, Any]]:
    validator = Draft202012Validator(_schema(DISPOSITION_SCHEMA))
    return [
        {
            "code": "SCHEMA_ERROR",
            "path": ".".join(str(part) for part in error.absolute_path),
            "message": error.message,
        }
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _hash_record(value: dict[str, Any], hash_field: str) -> str:
    controlled = {key: item for key, item in value.items() if key != hash_field and key not in RUNTIME_PRIVATE_KEYS}
    return sha256_bytes(canonical_json_bytes(controlled))


def _dispositions_root(workspace: Workspace) -> Path:
    root = workspace.root / "governance" / "owner-dispositions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a 64-character lowercase hexadecimal digest")
    return value


def _validate_locator(storage_boundary: str, locator: str) -> None:
    if storage_boundary not in STORAGE_BOUNDARIES:
        raise ValueError(f"Unsupported evidence storage boundary {storage_boundary!r}")
    if not locator:
        raise ValueError("Evidence locator must not be empty")
    if storage_boundary == "PROTECTED_WORKSPACE":
        if not locator.startswith(PROTECTED_PREFIX):
            raise ValueError("Protected closure evidence requires an opaque protected-ref locator")
        ensure_identifier(locator.removeprefix(PROTECTED_PREFIX), "protected evidence reference")
        return
    if locator.startswith(PROTECTED_PREFIX):
        raise ValueError("Opaque protected-ref locators are reserved for PROTECTED_WORKSPACE evidence")
    if "\\" in locator:
        raise ValueError("Evidence locators must use POSIX separators")
    pure = PurePosixPath(locator)
    if pure.is_absolute() or pure.as_posix() != locator or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Evidence locator must be a normalized relative POSIX path")


def _normalize_evidence_reference(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    label = str(value.get("label", "")).strip()
    if not label:
        raise ValueError(f"{field}.label is required")
    digest = _validate_sha256(value.get("sha256"), f"{field}.sha256")
    storage_boundary = str(value.get("storage_boundary", ""))
    locator = str(value.get("locator", ""))
    _validate_locator(storage_boundary, locator)
    return {
        "label": label,
        "sha256": digest,
        "storage_boundary": storage_boundary,
        "locator": locator,
    }


def load_governance_owner_dispositions(workspace: Workspace) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(_dispositions_root(workspace).glob("*.json")):
        value = load_json(path)
        if isinstance(value, dict):
            record = cast(dict[str, Any], value)
            record["_path"] = str(path)
            records.append(record)
    return records


def _active_opinions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {str(record.get("supersedes_opinion_id")) for record in records if record.get("supersedes_opinion_id")}
    return [record for record in records if str(record.get("opinion_id")) not in superseded]


def _active_dispositions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {
        str(record.get("supersedes_disposition_id")) for record in records if record.get("supersedes_disposition_id")
    }
    return [record for record in records if str(record.get("disposition_id")) not in superseded]


def _disposition_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        disposition_id = str(record.get("disposition_id", ""))
        if disposition_id in index:
            raise ValueError(f"Duplicate governance owner disposition ID {disposition_id}")
        index[disposition_id] = record
    return index


def _opinion_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        opinion_id = str(record.get("opinion_id", ""))
        if opinion_id in index:
            raise ValueError(f"Duplicate governance opinion ID {opinion_id}")
        index[opinion_id] = record
    return index


def _condition_register_hash(register: dict[str, Any]) -> str:
    return _hash_record(register, "register_sha256")


def _disposition_hash(record: dict[str, Any]) -> str:
    return _hash_record(record, "disposition_sha256")


def _normalize_owner_claim(owner_claim: Any) -> dict[str, str]:
    if not isinstance(owner_claim, dict):
        raise ValueError("owner_claim must be an object")
    owner_key = str(owner_claim.get("owner_key", "")).strip()
    ensure_identifier(owner_key, "owner_claim.owner_key")
    for field in ("name_or_role", "accountability_state"):
        if not str(owner_claim.get(field, "")).strip():
            raise ValueError(f"owner_claim.{field} is required")
    normalized = {
        "owner_key": owner_key,
        "name_or_role": str(owner_claim["name_or_role"]).strip(),
        "accountability_state": str(owner_claim["accountability_state"]).strip(),
    }
    if owner_claim.get("organization"):
        normalized["organization"] = str(owner_claim["organization"]).strip()
    return normalized


def _normalize_conditions(
    values: list[dict[str, Any]] | None,
    *,
    predecessor: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    prior_conditions: list[dict[str, Any]] = []
    if predecessor is not None:
        register = predecessor.get("condition_register")
        if isinstance(register, dict) and isinstance(register.get("conditions"), list):
            prior_conditions = [dict(item) for item in register["conditions"] if isinstance(item, dict)]
    prior_by_id = {str(item.get("condition_id")): item for item in prior_conditions}
    normalized_by_id = {condition_id: dict(item) for condition_id, item in prior_by_id.items()}
    seen_input: set[str] = set()

    for index, raw in enumerate(values or []):
        if not isinstance(raw, dict):
            raise ValueError(f"conditions.{index} must be an object")
        condition_id = str(raw.get("condition_id", "")).strip()
        if condition_id:
            ensure_identifier(condition_id, f"conditions.{index}.condition_id")
            if not condition_id.startswith("GOVCOND-"):
                raise ValueError("condition_id must use the GOVCOND- prefix")
        else:
            condition_id = f"GOVCOND-{uuid4().hex}"
        if condition_id in seen_input:
            raise ValueError(f"Duplicate condition_id {condition_id}")
        seen_input.add(condition_id)

        description = str(raw.get("description", "")).strip()
        owner = str(raw.get("owner", "")).strip()
        priority = str(raw.get("priority", ""))
        status = str(raw.get("status", ""))
        release_effect = str(raw.get("release_effect", ""))
        if not description:
            raise ValueError(f"conditions.{index}.description is required")
        ensure_identifier(owner, f"conditions.{index}.owner")
        if priority not in CONDITION_PRIORITIES:
            raise ValueError(f"Unsupported condition priority {priority!r}")
        if status not in CONDITION_STATUSES:
            raise ValueError(f"Unsupported condition status {status!r}")
        if release_effect not in RELEASE_EFFECTS:
            raise ValueError(f"Unsupported condition release effect {release_effect!r}")

        closure_raw = raw.get("closure_evidence_reference")
        if status == "RESOLVED":
            if closure_raw is None:
                raise ValueError("RESOLVED conditions require closure_evidence_reference")
            closure = _normalize_evidence_reference(
                closure_raw,
                f"conditions.{index}.closure_evidence_reference",
            )
        else:
            if closure_raw is not None:
                raise ValueError("Only RESOLVED conditions may contain closure_evidence_reference")
            closure = None

        prior = prior_by_id.get(condition_id)
        if prior is not None:
            for field, observed in (
                ("description", description),
                ("owner", owner),
                ("priority", priority),
                ("release_effect", release_effect),
            ):
                if prior.get(field) != observed:
                    raise ValueError(f"Condition {condition_id} changes immutable field {field}")

        normalized_by_id[condition_id] = {
            "condition_id": condition_id,
            "description": description,
            "owner": owner,
            "priority": priority,
            "status": status,
            "release_effect": release_effect,
            "closure_evidence_reference": closure,
        }

    return [normalized_by_id[key] for key in sorted(normalized_by_id)]


def _addressed_opinion_refs(
    opinions: list[dict[str, Any]],
    *,
    scope_id: str,
    scope_sha256: str,
    opinion_ids: list[str],
) -> list[dict[str, str]]:
    active = _active_opinions(opinions)
    active_index = _opinion_index(active)
    requested = sorted(set(opinion_ids))
    if not requested:
        raise ValueError("At least one active governance opinion must be addressed")
    if len(requested) != len(opinion_ids):
        raise ValueError("Duplicate opinion IDs are not allowed")
    refs: list[dict[str, str]] = []
    for opinion_id in requested:
        ensure_identifier(opinion_id, "opinion_id")
        opinion = active_index.get(opinion_id)
        if opinion is None:
            raise ValueError(f"Governance opinion {opinion_id} is not the current active opinion")
        if opinion.get("scope_id") != scope_id or opinion.get("scope_sha256") != scope_sha256:
            raise ValueError(f"Governance opinion {opinion_id} is outside the declared governance scope")
        reviewer = opinion.get("reviewer_claim")
        reviewer_key = str(reviewer.get("reviewer_key", "")) if isinstance(reviewer, dict) else ""
        refs.append(
            {
                "opinion_id": opinion_id,
                "opinion_sha256": str(opinion.get("opinion_sha256", "")),
                "review_track": str(opinion.get("review_track", "")),
                "opinion_state": str(opinion.get("opinion_state", "")),
                "reviewer_key": reviewer_key,
            }
        )
    return refs


def record_governance_owner_disposition(
    workspace: Workspace,
    *,
    scope_id: str,
    scope_sha256: str,
    opinion_ids: list[str],
    disposition_state: str,
    owner_claim: dict[str, Any],
    rationale: str,
    conditions: list[dict[str, Any]] | None = None,
    supersedes_disposition_id: str | None = None,
    recorded_by: str = "local-user",
    actor: str | None = None,
) -> dict[str, Any]:
    """Record one append-only, non-authorizing owner disposition and condition-register snapshot."""
    ensure_identifier(recorded_by, "recorded_by")
    actor = actor or recorded_by
    ensure_identifier(actor, "actor")
    ensure_identifier(scope_id, "scope_id")
    scope_sha256 = _validate_sha256(scope_sha256, "scope_sha256")
    if disposition_state not in DISPOSITION_STATES:
        raise ValueError(f"Unsupported owner disposition state {disposition_state!r}")
    rationale = rationale.strip()
    if not rationale:
        raise ValueError("Owner disposition rationale must not be empty")
    normalized_owner = _normalize_owner_claim(owner_claim)

    opinion_verification = verify_governance_reviewer_opinions(workspace)
    if not opinion_verification["valid"]:
        raise ValueError(
            "Governance reviewer opinion store failed verification: "
            f"{json.dumps(opinion_verification['errors'], ensure_ascii=False)}"
        )
    opinions = load_governance_reviewer_opinions(workspace)
    refs = _addressed_opinion_refs(
        opinions,
        scope_id=scope_id,
        scope_sha256=scope_sha256,
        opinion_ids=opinion_ids,
    )

    existing = load_governance_owner_dispositions(workspace)
    if existing:
        verification = verify_governance_owner_dispositions(workspace)
        if not verification["valid"]:
            raise ValueError(
                "Existing governance owner disposition store failed verification: "
                f"{json.dumps(verification['errors'], ensure_ascii=False)}"
            )
    index = _disposition_index(existing)
    active = _active_dispositions(existing)
    requested_ids = {item["opinion_id"] for item in refs}

    predecessor: dict[str, Any] | None = None
    if supersedes_disposition_id is not None:
        ensure_identifier(supersedes_disposition_id, "supersedes_disposition_id")
        predecessor = index.get(supersedes_disposition_id)
        if predecessor is None:
            raise ValueError(f"Superseded owner disposition {supersedes_disposition_id} does not exist")
        if predecessor not in active:
            raise ValueError("supersedes_disposition_id must identify the current active disposition")
        predecessor_ids = {
            str(item.get("opinion_id")) for item in predecessor.get("addressed_opinions", []) if isinstance(item, dict)
        }
        if requested_ids != predecessor_ids:
            raise ValueError("A superseding owner disposition must address the exact predecessor opinion set")
        if predecessor.get("scope_id") != scope_id or predecessor.get("scope_sha256") != scope_sha256:
            raise ValueError("A superseding owner disposition cannot change governance scope")
    else:
        for active_record in active:
            active_ids = {
                str(item.get("opinion_id"))
                for item in active_record.get("addressed_opinions", [])
                if isinstance(item, dict)
            }
            overlap = sorted(requested_ids & active_ids)
            if overlap:
                raise ValueError("Active owner disposition already addresses opinion IDs: " + ", ".join(overlap))

    normalized_conditions = _normalize_conditions(conditions, predecessor=predecessor)
    if disposition_state == "ACCEPT_WITH_ACTION" and not normalized_conditions:
        raise ValueError("ACCEPT_WITH_ACTION requires at least one condition")

    disposition_id = f"GOVDISP-{uuid4().hex}"
    register: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "register_id": f"GOVCONDREG-{uuid4().hex}",
        "disposition_id": disposition_id,
        "scope_id": scope_id,
        "scope_sha256": scope_sha256,
        "conditions": normalized_conditions,
        "release_authorization_performed": False,
        "authority_profile": "UNRESOLVED_CONDITION_TRACKING",
        "boundary": CONDITION_REGISTER_BOUNDARY,
    }
    if predecessor is not None:
        predecessor_register = predecessor.get("condition_register")
        if not isinstance(predecessor_register, dict):
            raise ValueError("Superseded owner disposition is missing its condition register")
        register["supersedes_register_id"] = str(predecessor_register.get("register_id", ""))
        register["supersedes_register_sha256"] = str(predecessor_register.get("register_sha256", ""))
    register["register_sha256"] = _condition_register_hash(register)

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "disposition_id": disposition_id,
        "scope_id": scope_id,
        "scope_sha256": scope_sha256,
        "addressed_opinions": refs,
        "disposition_state": disposition_state,
        "owner_claim": normalized_owner,
        "recorded_at": utc_now(),
        "recorded_by": recorded_by,
        "rationale": rationale,
        "condition_register": register,
        "release_authorization_performed": False,
        "authority_profile": "CLAIMED_OWNER_ATTRIBUTION",
        "boundary": OWNER_DISPOSITION_BOUNDARY,
    }
    if predecessor is not None:
        record["supersedes_disposition_id"] = supersedes_disposition_id
        record["supersedes_disposition_sha256"] = str(predecessor.get("disposition_sha256", ""))
    record["disposition_sha256"] = _disposition_hash(record)

    errors = _schema_errors(record)
    if errors:
        raise ValueError(f"Governance owner disposition failed validation: {json.dumps(errors, ensure_ascii=False)}")

    output = _dispositions_root(workspace) / f"{disposition_id}.json"
    if output.exists():
        raise ValueError(f"A governance owner disposition already exists: {disposition_id}")
    atomic_write_json(output, record)
    append_event(
        workspace.root / "events.jsonl",
        "GOVERNANCE_OWNER_DISPOSITION_RECORDED",
        actor,
        {
            "disposition_id": disposition_id,
            "disposition_sha256": record["disposition_sha256"],
            "condition_register_id": register["register_id"],
            "condition_register_sha256": register["register_sha256"],
            "scope_id": scope_id,
            "scope_sha256": scope_sha256,
            "addressed_opinion_ids": [item["opinion_id"] for item in refs],
            "disposition_state": disposition_state,
            "owner_key": normalized_owner["owner_key"],
            "supersedes_disposition_id": supersedes_disposition_id,
            "release_authorization_performed": False,
        },
    )
    return {"disposition": record, "path": str(output)}


def _supersession_errors(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    try:
        index = _disposition_index(records)
    except ValueError as exc:
        return [str(exc)]
    superseders: dict[str, list[str]] = defaultdict(list)
    graph: dict[str, str] = {}

    for record in records:
        disposition_id = str(record.get("disposition_id", ""))
        target_id = record.get("supersedes_disposition_id")
        target_sha = record.get("supersedes_disposition_sha256")
        if target_id is None and target_sha is None:
            continue
        if not isinstance(target_id, str) or not isinstance(target_sha, str):
            errors.append(f"disposition {disposition_id}: incomplete supersession reference")
            continue
        target = index.get(target_id)
        if target is None:
            errors.append(f"disposition {disposition_id}: superseded disposition {target_id} is missing")
            continue
        if target_id == disposition_id:
            errors.append(f"disposition {disposition_id}: a disposition cannot supersede itself")
        if target.get("disposition_sha256") != target_sha:
            errors.append(f"disposition {disposition_id}: superseded disposition hash mismatch")
        for field in ("scope_id", "scope_sha256"):
            if target.get(field) != record.get(field):
                errors.append(f"disposition {disposition_id}: supersession changes {field}")
        target_refs = {
            (str(item.get("opinion_id")), str(item.get("opinion_sha256")))
            for item in target.get("addressed_opinions", [])
            if isinstance(item, dict)
        }
        refs = {
            (str(item.get("opinion_id")), str(item.get("opinion_sha256")))
            for item in record.get("addressed_opinions", [])
            if isinstance(item, dict)
        }
        if refs != target_refs:
            errors.append(f"disposition {disposition_id}: supersession changes addressed opinion set")
        target_register = target.get("condition_register")
        register = record.get("condition_register")
        if isinstance(target_register, dict) and isinstance(register, dict):
            if register.get("supersedes_register_id") != target_register.get("register_id"):
                errors.append(f"disposition {disposition_id}: condition register predecessor ID mismatch")
            if register.get("supersedes_register_sha256") != target_register.get("register_sha256"):
                errors.append(f"disposition {disposition_id}: condition register predecessor hash mismatch")
            prior_conditions = {
                str(item.get("condition_id")): item
                for item in target_register.get("conditions", [])
                if isinstance(item, dict)
            }
            current_conditions = {
                str(item.get("condition_id")): item for item in register.get("conditions", []) if isinstance(item, dict)
            }
            missing = sorted(set(prior_conditions) - set(current_conditions))
            if missing:
                errors.append(
                    f"disposition {disposition_id}: condition IDs removed across supersession: {', '.join(missing)}"
                )
            for condition_id in sorted(set(prior_conditions) & set(current_conditions)):
                prior = prior_conditions[condition_id]
                current_condition = current_conditions[condition_id]
                for field in ("description", "owner", "priority", "release_effect"):
                    if prior.get(field) != current_condition.get(field):
                        errors.append(
                            f"disposition {disposition_id}: condition {condition_id} changes immutable field {field}"
                        )
        superseders[target_id].append(disposition_id)
        graph[disposition_id] = target_id

    for target_id, disposition_ids in sorted(superseders.items()):
        if len(disposition_ids) > 1:
            errors.append(f"disposition {target_id}: branching supersession by {', '.join(sorted(disposition_ids))}")
    for start in sorted(graph):
        seen: set[str] = set()
        cursor = start
        while cursor in graph:
            if cursor in seen:
                errors.append(f"disposition {start}: supersession cycle detected")
                break
            seen.add(cursor)
            cursor = graph[cursor]
    return errors


def _condition_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    disposition_id = str(record.get("disposition_id", ""))
    register = record.get("condition_register")
    if not isinstance(register, dict):
        return [f"disposition {disposition_id}: condition register missing"]
    if register.get("register_sha256") != _condition_register_hash(register):
        errors.append(f"disposition {disposition_id}: condition register hash mismatch")
    for field in ("disposition_id", "scope_id", "scope_sha256"):
        if register.get(field) != record.get(field):
            errors.append(f"disposition {disposition_id}: condition register {field} mismatch")
    if register.get("boundary") != CONDITION_REGISTER_BOUNDARY:
        errors.append(f"disposition {disposition_id}: condition register boundary mismatch")
    if register.get("release_authorization_performed") is not False:
        errors.append(f"disposition {disposition_id}: condition register must remain non-authorizing")

    seen: set[str] = set()
    conditions = register.get("conditions")
    if not isinstance(conditions, list):
        return errors + [f"disposition {disposition_id}: condition register conditions must be a list"]
    for index, condition in enumerate(conditions):
        if not isinstance(condition, dict):
            errors.append(f"disposition {disposition_id}: condition {index} is not an object")
            continue
        condition_id = str(condition.get("condition_id", ""))
        if condition_id in seen:
            errors.append(f"disposition {disposition_id}: duplicate condition ID {condition_id}")
        seen.add(condition_id)
        if not condition_id.startswith("GOVCOND-"):
            errors.append(f"disposition {disposition_id}: invalid condition ID {condition_id}")
        if condition.get("priority") not in CONDITION_PRIORITIES:
            errors.append(f"disposition {disposition_id}: condition {condition_id} has invalid priority")
        status = condition.get("status")
        if status not in CONDITION_STATUSES:
            errors.append(f"disposition {disposition_id}: condition {condition_id} has invalid status")
        if condition.get("release_effect") not in RELEASE_EFFECTS:
            errors.append(f"disposition {disposition_id}: condition {condition_id} has invalid release effect")
        closure = condition.get("closure_evidence_reference")
        if status == "RESOLVED" and closure is None:
            errors.append(f"disposition {disposition_id}: resolved condition {condition_id} lacks closure evidence")
        if status != "RESOLVED" and closure is not None:
            errors.append(f"disposition {disposition_id}: unresolved condition {condition_id} has closure evidence")
        if closure is not None:
            try:
                _normalize_evidence_reference(closure, f"condition {condition_id}.closure_evidence_reference")
            except ValueError as exc:
                errors.append(f"disposition {disposition_id}: invalid closure evidence for {condition_id}: {exc}")
    return errors


def verify_governance_owner_dispositions(workspace: Workspace) -> dict[str, Any]:
    """Verify disposition integrity, opinion bindings, condition lineage, supersession, and events."""
    records = load_governance_owner_dispositions(workspace)
    errors: list[str] = []
    warnings: list[str] = []

    opinion_verification = verify_governance_reviewer_opinions(workspace)
    if not opinion_verification["valid"]:
        errors.append("governance reviewer opinion store is invalid")
    opinions = load_governance_reviewer_opinions(workspace)
    try:
        opinion_index = _opinion_index(opinions)
    except ValueError as exc:
        opinion_index = {}
        errors.append(str(exc))

    try:
        events = load_events(workspace.root / "events.jsonl")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        events = []
        errors.append(f"event log load failed: {exc}")
    disposition_events: Counter[tuple[str, str, str, str, str, str]] = Counter(
        (
            str(event.get("payload", {}).get("disposition_id")),
            str(event.get("payload", {}).get("disposition_sha256")),
            str(event.get("payload", {}).get("condition_register_id")),
            str(event.get("payload", {}).get("condition_register_sha256")),
            str(event.get("payload", {}).get("scope_id")),
            str(event.get("payload", {}).get("scope_sha256")),
        )
        for event in events
        if event.get("action") == "GOVERNANCE_OWNER_DISPOSITION_RECORDED" and isinstance(event.get("payload"), dict)
    )

    seen_ids: set[str] = set()
    for record in records:
        disposition_id = str(record.get("disposition_id", ""))
        if disposition_id in seen_ids:
            errors.append(f"disposition {disposition_id}: duplicate disposition_id")
        seen_ids.add(disposition_id)
        unsupported_private = sorted(key for key in record if key.startswith("_") and key not in RUNTIME_PRIVATE_KEYS)
        if unsupported_private:
            errors.append(f"disposition {disposition_id}: unsupported private fields {unsupported_private}")
        schema_target = {key: value for key, value in record.items() if key not in RUNTIME_PRIVATE_KEYS}
        if record.get("disposition_sha256") != _disposition_hash(record):
            errors.append(f"disposition {disposition_id}: hash mismatch")
        if _schema_errors(schema_target):
            errors.append(f"disposition {disposition_id}: schema invalid")
        if record.get("boundary") != OWNER_DISPOSITION_BOUNDARY:
            errors.append(f"disposition {disposition_id}: authority boundary mismatch")
        if record.get("disposition_state") not in DISPOSITION_STATES:
            errors.append(f"disposition {disposition_id}: unsupported disposition state")
        if record.get("release_authorization_performed") is not False:
            errors.append(f"disposition {disposition_id}: release authorization must remain false")
        if record.get("disposition_state") == "ACCEPT_WITH_ACTION":
            register = record.get("condition_register")
            conditions = register.get("conditions") if isinstance(register, dict) else None
            if not conditions:
                errors.append(f"disposition {disposition_id}: ACCEPT_WITH_ACTION requires conditions")
        errors.extend(_condition_errors(record))

        refs = record.get("addressed_opinions")
        if not isinstance(refs, list) or not refs:
            errors.append(f"disposition {disposition_id}: addressed_opinions must not be empty")
            refs = []
        seen_opinions: set[str] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                errors.append(f"disposition {disposition_id}: addressed opinion reference is not an object")
                continue
            opinion_id = str(ref.get("opinion_id", ""))
            if opinion_id in seen_opinions:
                errors.append(f"disposition {disposition_id}: duplicate addressed opinion {opinion_id}")
            seen_opinions.add(opinion_id)
            opinion = opinion_index.get(opinion_id)
            if opinion is None:
                errors.append(f"disposition {disposition_id}: addressed opinion {opinion_id} is missing")
                continue
            if opinion.get("opinion_sha256") != ref.get("opinion_sha256"):
                errors.append(f"disposition {disposition_id}: opinion {opinion_id} hash mismatch")
            if opinion.get("scope_id") != record.get("scope_id"):
                errors.append(f"disposition {disposition_id}: opinion {opinion_id} scope ID mismatch")
            if opinion.get("scope_sha256") != record.get("scope_sha256"):
                errors.append(f"disposition {disposition_id}: opinion {opinion_id} scope hash mismatch")
            for field in ("review_track", "opinion_state"):
                if opinion.get(field) != ref.get(field):
                    errors.append(f"disposition {disposition_id}: opinion {opinion_id} {field} mismatch")
            reviewer = opinion.get("reviewer_claim")
            reviewer_key = reviewer.get("reviewer_key") if isinstance(reviewer, dict) else None
            if reviewer_key != ref.get("reviewer_key"):
                errors.append(f"disposition {disposition_id}: opinion {opinion_id} reviewer_key mismatch")

        register = record.get("condition_register")
        if isinstance(register, dict):
            event_key = (
                disposition_id,
                str(record.get("disposition_sha256")),
                str(register.get("register_id")),
                str(register.get("register_sha256")),
                str(record.get("scope_id")),
                str(record.get("scope_sha256")),
            )
            event_count = disposition_events[event_key]
            if event_count == 0:
                errors.append(f"disposition {disposition_id}: matching append-only event is missing")
            elif event_count > 1:
                errors.append(f"disposition {disposition_id}: {event_count} matching append-only events were recorded")

    errors.extend(_supersession_errors(records))

    active = _active_dispositions(records)
    addressed_counts: Counter[str] = Counter()
    for record in active:
        for ref in record.get("addressed_opinions", []):
            if isinstance(ref, dict):
                addressed_counts[str(ref.get("opinion_id", ""))] += 1
    for opinion_id, count in sorted(addressed_counts.items()):
        if count > 1:
            errors.append(f"opinion {opinion_id}: addressed by {count} active owner dispositions")

    chain = verify_chain(workspace.root / "events.jsonl")
    if not chain["valid"] or not chain.get("trailer_valid", False):
        errors.extend(f"event chain: {error}" for error in chain["errors"])
        errors.extend(f"event chain trailer: {error}" for error in chain.get("trailer_errors", []))

    active_opinions = _active_opinions(opinions)
    active_opinion_ids = {str(item.get("opinion_id", "")) for item in active_opinions}
    unaddressed = sorted(active_opinion_ids - set(addressed_counts))
    if unaddressed:
        warnings.append("Active reviewer opinions without an owner disposition: " + ", ".join(unaddressed))

    return {
        "valid": not errors,
        "counts": {
            "dispositions": len(records),
            "active_dispositions": len(active),
            "superseded_dispositions": len(records) - len(active),
            "active_opinions": len(active_opinions),
            "unaddressed_active_opinions": len(unaddressed),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
        "event_chain_valid": chain["valid"] and chain.get("trailer_valid", False),
        "release_authorization_performed": False,
        "release_readiness_established": False,
        "boundary": OWNER_DISPOSITION_BOUNDARY,
    }


def summarize_governance_owner_dispositions(workspace: Workspace) -> dict[str, Any]:
    """Summarize active owner dispositions and unresolved conditions without collapsing dissent."""
    verification = verify_governance_owner_dispositions(workspace)
    opinions = load_governance_reviewer_opinions(workspace)
    active_opinions = _active_opinions(opinions)
    active_dispositions = _active_dispositions(load_governance_owner_dispositions(workspace))

    disposition_counts: Counter[str] = Counter()
    addressed_ids: set[str] = set()
    unresolved_conditions: list[dict[str, Any]] = []
    for record in active_dispositions:
        disposition_counts[str(record.get("disposition_state", ""))] += 1
        for ref in record.get("addressed_opinions", []):
            if isinstance(ref, dict):
                addressed_ids.add(str(ref.get("opinion_id", "")))
        register = record.get("condition_register")
        if not isinstance(register, dict):
            continue
        for condition in register.get("conditions", []):
            if not isinstance(condition, dict) or condition.get("status") == "RESOLVED":
                continue
            unresolved_conditions.append(
                {
                    "condition_id": condition.get("condition_id"),
                    "disposition_id": record.get("disposition_id"),
                    "scope_id": record.get("scope_id"),
                    "description": condition.get("description"),
                    "owner": condition.get("owner"),
                    "priority": condition.get("priority"),
                    "status": condition.get("status"),
                    "release_effect": condition.get("release_effect"),
                }
            )

    unaddressed: list[dict[str, Any]] = []
    for opinion in sorted(
        active_opinions,
        key=lambda item: (str(item.get("review_track", "")), str(item.get("opinion_id", ""))),
    ):
        opinion_id = str(opinion.get("opinion_id", ""))
        if opinion_id in addressed_ids:
            continue
        reviewer = opinion.get("reviewer_claim")
        unaddressed.append(
            {
                "opinion_id": opinion_id,
                "opinion_sha256": opinion.get("opinion_sha256"),
                "scope_id": opinion.get("scope_id"),
                "scope_sha256": opinion.get("scope_sha256"),
                "review_track": opinion.get("review_track"),
                "opinion_state": opinion.get("opinion_state"),
                "reviewer_key": reviewer.get("reviewer_key") if isinstance(reviewer, dict) else None,
            }
        )

    unaddressed_counts = Counter(str(item["opinion_state"]) for item in unaddressed)
    blocking_conditions = [item for item in unresolved_conditions if item.get("release_effect") == "BLOCKS_RELEASE"]
    return {
        "integrity_valid": verification["valid"],
        "scope_ids": sorted(
            {str(record.get("scope_id")) for record in active_dispositions}
            | {str(opinion.get("scope_id")) for opinion in active_opinions}
        ),
        "active_disposition_state_counts": dict(sorted(disposition_counts.items())),
        "unaddressed_active_opinions": unaddressed,
        "unaddressed_state_counts": dict(sorted(unaddressed_counts.items())),
        "unaddressed_objection_present": unaddressed_counts["OBJECT"] > 0,
        "unaddressed_abstention_present": unaddressed_counts["ABSTAIN"] > 0,
        "unaddressed_evidence_request_present": unaddressed_counts["REQUEST_EVIDENCE"] > 0,
        "unresolved_conditions": unresolved_conditions,
        "release_blocking_conditions": blocking_conditions,
        "owner_disposition_complete": not unaddressed,
        "release_blocking_condition_present": bool(blocking_conditions),
        "release_authorization_performed": False,
        "release_readiness_established": False,
        "opinion_boundary": GOVERNANCE_OPINION_BOUNDARY,
        "boundary": OWNER_DISPOSITION_BOUNDARY,
    }
