"""Institutional pilot profile adapters. Not local case-server authentication."""

from .profile import (
    INSTITUTIONAL_BOUNDARY,
    RBAC_ROLES,
    DeploymentMode,
    LocalDevIdentityAdapter,
    OidcProfileAdapter,
    SamlProfileAdapter,
    append_audit_event,
    assert_deployment_mode_separation,
    assert_not_local_case_server_auth,
    assign_rbac_role,
    break_glass_hook,
    s3_tenant_boundary,
)

__all__ = [
    "INSTITUTIONAL_BOUNDARY",
    "RBAC_ROLES",
    "DeploymentMode",
    "LocalDevIdentityAdapter",
    "OidcProfileAdapter",
    "SamlProfileAdapter",
    "append_audit_event",
    "assert_deployment_mode_separation",
    "assert_not_local_case_server_auth",
    "assign_rbac_role",
    "break_glass_hook",
    "s3_tenant_boundary",
]
