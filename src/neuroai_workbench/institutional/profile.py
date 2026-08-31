"""Institutional deployment profile adapters (M5).

OIDC/RBAC/audit/S3 hooks are profile adapters only. Do not add authentication to
the local ThreadingHTTPServer and call it institutional (AGENTS.md prohibited shortcut).
Role assignment alone cannot grant release authority.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from ..util import atomic_write_json, load_json, utc_now

INSTITUTIONAL_BOUNDARY = (
    "Institutional adapters configure authenticated deployment profiles. Local development "
    "mode must not be confused with authenticated mode. Role assignment alone cannot grant "
    "release authority. These adapters are not authentication on ThreadingHTTPServer."
)

RBAC_ROLES = frozenset(
    {
        "OBSERVATORY_READER",
        "EVIDENCE_CUSTODIAN",
        "ASSESSOR",
        "REVIEW_LEAD",
        "RELEASE_ATTESTOR",
        "RELEASE_AUTHORIZER",
        "SECURITY_OPERATOR",
        "BREAK_GLASS_OPERATOR",
    }
)


class DeploymentMode(str, Enum):
    LOCAL = "LOCAL"
    INSTITUTIONAL = "INSTITUTIONAL"


class IdentityProviderAdapter(Protocol):
    mode: str

    def authenticate(self, token: str) -> dict[str, Any]: ...


class LocalDevIdentityAdapter:
    """Explicit local-dev identity. Never reports authenticated institutional mode."""

    mode = DeploymentMode.LOCAL.value

    def authenticate(self, token: str) -> dict[str, Any]:
        return {
            "subject": "local-dev-user",
            "token_present": bool(token),
            "authenticated": False,
            "mode": self.mode,
            "deployment_mode": DeploymentMode.LOCAL.value,
            "institutional": False,
            "fail_closed": True,
            "boundary": INSTITUTIONAL_BOUNDARY,
        }


class OidcProfileAdapter:
    """OIDC profile adapter. Fail-closed: does not claim verified production auth."""

    mode = DeploymentMode.INSTITUTIONAL.value

    def __init__(self, *, issuer: str, audience: str, require_verified_token: bool = True) -> None:
        if not issuer.strip() or not audience.strip():
            raise ValueError("OIDC adapter requires issuer and audience")
        self.issuer = issuer.strip()
        self.audience = audience.strip()
        self.require_verified_token = require_verified_token

    def authenticate(self, token: str) -> dict[str, Any]:
        if not token.strip():
            raise ValueError("OIDC adapter fail-closed: bearer token required")
        # This adapter never performs cryptographic verification; institutional
        # deployments must supply a reviewed verifier before treating subjects as authenticated.
        if self.require_verified_token:
            return {
                "subject": None,
                "issuer": self.issuer,
                "audience": self.audience,
                "authenticated": False,
                "verification_state": "FAIL_CLOSED_UNVERIFIED",
                "mode": self.mode,
                "deployment_mode": DeploymentMode.INSTITUTIONAL.value,
                "institutional": True,
                "binds_to_threading_httpserver": False,
                "fail_closed": True,
                "boundary": INSTITUTIONAL_BOUNDARY,
            }
        return {
            "subject": "OIDC_SUBJECT_UNVERIFIED_STUB",
            "issuer": self.issuer,
            "audience": self.audience,
            "authenticated": False,
            "verification_state": "ADAPTER_STUB_NOT_PRODUCTION_VERIFIER",
            "mode": self.mode,
            "deployment_mode": DeploymentMode.INSTITUTIONAL.value,
            "institutional": True,
            "binds_to_threading_httpserver": False,
            "fail_closed": True,
            "boundary": INSTITUTIONAL_BOUNDARY,
        }


class SamlProfileAdapter:
    """SAML profile adapter stub. Fail-closed; not bound to ThreadingHTTPServer."""

    mode = DeploymentMode.INSTITUTIONAL.value

    def __init__(self, *, entity_id: str, acs_url: str) -> None:
        if not entity_id.strip() or not acs_url.strip():
            raise ValueError("SAML adapter requires entity_id and acs_url")
        if "localhost" in acs_url or "127.0.0.1" in acs_url:
            raise ValueError("SAML ACS must not target the local ThreadingHTTPServer")
        self.entity_id = entity_id.strip()
        self.acs_url = acs_url.strip()

    def authenticate(self, token: str) -> dict[str, Any]:
        if not token.strip():
            raise ValueError("SAML adapter fail-closed: assertion required")
        return {
            "subject": None,
            "entity_id": self.entity_id,
            "acs_url": self.acs_url,
            "authenticated": False,
            "verification_state": "FAIL_CLOSED_UNVERIFIED",
            "mode": self.mode,
            "deployment_mode": DeploymentMode.INSTITUTIONAL.value,
            "institutional": True,
            "binds_to_threading_httpserver": False,
            "fail_closed": True,
            "boundary": INSTITUTIONAL_BOUNDARY,
        }


def assert_deployment_mode_separation(profile: dict[str, Any]) -> None:
    mode = profile.get("deployment_mode") or profile.get("mode")
    if mode == DeploymentMode.LOCAL.value and profile.get("institutional") is True:
        raise ValueError("LOCAL deployment mode cannot be marked institutional")
    if mode == DeploymentMode.INSTITUTIONAL.value and profile.get("binds_to_threading_httpserver") is True:
        raise ValueError("INSTITUTIONAL mode must not bind to ThreadingHTTPServer")
    if profile.get("authenticated") is True and profile.get("verification_state") in {
        "FAIL_CLOSED_UNVERIFIED",
        "ADAPTER_STUB_NOT_PRODUCTION_VERIFIER",
        None,
    }:
        raise ValueError("Fail-closed adapters must not report authenticated=true without a verified token")


def assign_rbac_role(*, subject: str, role: str, actor: str) -> dict[str, Any]:
    if role not in RBAC_ROLES:
        raise ValueError(f"Unsupported RBAC role {role!r}")
    return {
        "subject": subject,
        "role": role,
        "assigned_at": utc_now(),
        "assigned_by": actor,
        "grants_release_authority": False,
        "release_authority_requires_separate_attestation": True,
        "boundary": INSTITUTIONAL_BOUNDARY,
    }


def append_audit_event(
    sink: list[dict[str, Any]] | Path,
    *,
    action: str,
    actor: str,
    resource: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "action": action,
        "actor": actor,
        "resource": resource,
        "details": details or {},
        "recorded_at": utc_now(),
        "immutable_append_only": True,
        "boundary": INSTITUTIONAL_BOUNDARY,
    }
    if isinstance(sink, Path):
        sink.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, Any]] = []
        if sink.is_file():
            loaded = load_json(sink)
            if isinstance(loaded, list):
                existing = [item for item in loaded if isinstance(item, dict)]
            else:
                raise ValueError("Audit sink file must contain a JSON array")
        existing.append(event)
        atomic_write_json(sink, existing)
    else:
        sink.append(event)
    return event


def s3_tenant_boundary(*, tenant_id: str, object_key: str) -> dict[str, Any]:
    if not tenant_id.strip():
        raise ValueError("tenant_id is required")
    if ".." in object_key or object_key.startswith("/") or "\\" in object_key:
        raise ValueError("S3 object key must be relative and non-escaping")
    return {
        "tenant_id": tenant_id,
        "object_key": object_key,
        "prefix": f"tenants/{tenant_id}/",
        "isolated": True,
        "public_s2_distinct_from_protected_s3": True,
        "fail_closed_on_cross_tenant": True,
        "boundary": INSTITUTIONAL_BOUNDARY,
    }


def break_glass_hook(*, actor: str, rationale: str) -> dict[str, Any]:
    if not rationale.strip():
        raise ValueError("Break-glass requires rationale")
    return {
        "actor": actor,
        "rationale": rationale.strip(),
        "opened_at": utc_now(),
        "grants_release_authority": False,
        "requires_post_incident_review": True,
        "boundary": INSTITUTIONAL_BOUNDARY,
    }


def assert_not_local_case_server_auth(profile: dict[str, Any]) -> None:
    if profile.get("binds_to_threading_httpserver") is True:
        raise ValueError("Institutional auth must not bind to local ThreadingHTTPServer")
    assert_deployment_mode_separation(profile)
