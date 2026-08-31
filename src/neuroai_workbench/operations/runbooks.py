"""Operations, DR, and security runbook hooks (M5 E13/E14).

These are structured hooks and checklists. They do not claim a completed pen-test,
exercised restore, or institutional readiness.
"""

from __future__ import annotations

from typing import Any

from ..util import utc_now

OPS_BOUNDARY = (
    "Operations hooks record runbook invocations and synthetic canary intent. "
    "They do not establish DR readiness, security acceptance, or institutional pilot clearance. "
    "Synthetic canaries must not create canonical observations."
)

RUNBOOK_IDS = frozenset(
    {
        "REGISTRY_CORRUPTION",
        "CREDENTIAL_COMPROMISE",
        "CAPTURE_CONTAMINATION",
        "SOURCE_TAKEOVER",
        "RELEASE_ROLLBACK",
        "BACKUP_RESTORE_EXERCISE",
        "INCIDENT_RESPONSE_EXERCISE",
        "PROTECTED_DATA_SCAN",
    }
)


def invoke_runbook(*, runbook_id: str, actor: str, notes: str) -> dict[str, Any]:
    if runbook_id not in RUNBOOK_IDS:
        raise ValueError(f"Unknown runbook_id {runbook_id!r}")
    return {
        "runbook_id": runbook_id,
        "actor": actor,
        "notes": notes,
        "invoked_at": utc_now(),
        "completed": False,
        "readiness_claimed": False,
        "boundary": OPS_BOUNDARY,
    }


def synthetic_canary(*, name: str, actor: str) -> dict[str, Any]:
    return {
        "canary_name": name,
        "actor": actor,
        "created_at": utc_now(),
        "creates_canonical_observation": False,
        "canonical_write_forbidden": True,
        "boundary": OPS_BOUNDARY,
    }


def security_hardening_checklist() -> dict[str, Any]:
    return {
        "items": [
            {"id": "THREAT_MODEL_COVERAGE", "status": "REQUIRED_HUMAN_REVIEW"},
            {"id": "PEN_TEST", "status": "REQUIRED_INDEPENDENT"},
            {"id": "SUPPLY_CHAIN_REVIEW", "status": "REQUIRED_INDEPENDENT"},
            {"id": "CONTENT_DISARM_MALWARE_PIPELINE", "status": "REQUIRED"},
            {"id": "DPIA_STYLE_INVENTORY", "status": "REQUIRED"},
            {"id": "KEY_ROTATION", "status": "REQUIRED"},
            {"id": "NO_CRITICAL_HIGH_OPEN_FOR_PILOT", "status": "REQUIRED"},
            {"id": "PUBLIC_S2_PROTECTED_DATA_SCAN", "status": "REQUIRED"},
            {
                "id": "HOSTED_CI_EMPTY_STEPS_TRIAGE",
                "status": "REQUIRED_OPS_TRIAGE",
                "note": "steps: [] is INFRASTRUCTURE_FAILURE, not EXECUTED_SUCCESS or EXECUTED_FAILURE",
            },
            {
                "id": "LOCAL_VS_INSTITUTIONAL_MODE",
                "status": "REQUIRED",
                "note": "Do not bind institutional auth to ThreadingHTTPServer",
            },
        ],
        "software_inferred_pass": False,
        "institutional_readiness_claimed": False,
        "boundary": OPS_BOUNDARY,
    }
