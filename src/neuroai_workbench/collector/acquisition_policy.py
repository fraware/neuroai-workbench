"""Digest-bound operational acquisition policy for the online-first migration.

This module is additive. A valid acquisition policy scopes an operational
acquisition attempt; it does not replace the live-collection authorization
packet or ``NEUROAI_LIVE_COLLECTION=1`` gate enforced by ``authorization.py``.
"""

from __future__ import annotations

import copy
import ipaddress
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import SplitResult, urlsplit

from ..util import canonical_json_bytes, ensure_identifier, sha256_bytes

POLICY_SCHEMA_VERSION = "1"
POLICY_BOUNDARY = (
    "An acquisition policy scopes operational acquisition attempts. It is not institutional authority, "
    "legal authorization, source authenticity, substantive evidence adjudication, assessment mutation, "
    "canonical S2 admission, release authorization, or publication."
)
ONLINE_REQUIRED = "ONLINE_REQUIRED"
ONLINE_PREFERRED = "ONLINE_PREFERRED"
REPLAY_ONLY = "REPLAY_ONLY"
EXECUTION_MODES = frozenset({ONLINE_REQUIRED, ONLINE_PREFERRED, REPLAY_ONLY})
FALLBACK_FORBID = "FORBID"
FALLBACK_PRIOR_CAPTURE = "EXPLICIT_PRIOR_CAPTURE_ALLOWED"
FALLBACK_POLICIES = frozenset({FALLBACK_FORBID, FALLBACK_PRIOR_CAPTURE})
_ONLINE_MODES = frozenset({ONLINE_REQUIRED, ONLINE_PREFERRED})
_POLICY_KEYS = frozenset(
    {
        "policy_schema_version",
        "policy_id",
        "programme_id",
        "approved_by",
        "approved_at",
        "expires_at",
        "source_rules",
        "boundary",
        "policy_sha256",
    }
)
_SOURCE_RULE_KEYS = frozenset({"source_id", "execution_modes", "allowed_origins", "fallback_policy"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
MAX_SOURCE_RULES = 10_000
MAX_ORIGINS_PER_SOURCE = 64


class AcquisitionPolicyError(PermissionError):
    """Raised when an acquisition policy is invalid or does not permit an attempt."""


def _parse_timestamp(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AcquisitionPolicyError(f"{field} must be a non-empty timestamp string")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise AcquisitionPolicyError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AcquisitionPolicyError(f"{field} must include an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _canonical_timestamp(value: str, *, field: str) -> str:
    parsed = _parse_timestamp(value, field=field)
    if parsed.microsecond != 0:
        raise AcquisitionPolicyError(f"{field} must use whole-second precision")
    return parsed.isoformat().replace("+00:00", "Z")


def _normalize_host(hostname: str) -> str:
    if not hostname:
        raise AcquisitionPolicyError("origin host must be non-empty")
    if "%" in hostname:
        raise AcquisitionPolicyError("origin host must not contain an IPv6 zone or percent escape")
    if hostname.endswith("."):
        raise AcquisitionPolicyError("origin host must not use a trailing dot")
    if "*" in hostname:
        raise AcquisitionPolicyError("wildcard origins are not supported")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            normalized = hostname.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise AcquisitionPolicyError("origin host is not valid IDNA") from exc
        if len(normalized) > 253:
            raise AcquisitionPolicyError("origin host exceeds the DNS name length limit")
        labels = normalized.split(".")
        if not labels or any(not _DNS_LABEL_RE.fullmatch(label) for label in labels):
            raise AcquisitionPolicyError("origin host contains a malformed DNS label")
        return normalized
    return address.compressed.lower()


def _parsed_port(parsed: SplitResult) -> int | None:
    try:
        return parsed.port
    except ValueError as exc:
        raise AcquisitionPolicyError("origin port is malformed") from exc


def _canonical_origin_from_split(parsed: SplitResult) -> str:
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise AcquisitionPolicyError("origin scheme must be http or https")
    if parsed.username is not None or parsed.password is not None:
        raise AcquisitionPolicyError("origin must not contain user-info")
    hostname = parsed.hostname
    if hostname is None:
        raise AcquisitionPolicyError("origin must include a host")
    host = _normalize_host(hostname)
    port = _parsed_port(parsed)
    if port is not None and not 1 <= port <= 65535:
        raise AcquisitionPolicyError("origin port must be between 1 and 65535")
    default_port = 443 if scheme == "https" else 80
    rendered_host = f"[{host}]" if ":" in host else host
    suffix = f":{port}" if port is not None and port != default_port else ""
    return f"{scheme}://{rendered_host}{suffix}"


def _split_url(value: str, *, field: str) -> SplitResult:
    try:
        return urlsplit(value)
    except ValueError as exc:
        raise AcquisitionPolicyError(f"{field} is malformed") from exc


def canonicalize_policy_origin(value: str) -> str:
    """Return the deterministic scheme/host/port representation for one policy origin."""
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise AcquisitionPolicyError("allowed origin must be a non-empty trimmed string")
    parsed = _split_url(value, field="allowed origin")
    if parsed.query or parsed.fragment:
        raise AcquisitionPolicyError("policy origin must not contain query or fragment components")
    if parsed.path not in {"", "/"}:
        raise AcquisitionPolicyError("policy origin must not contain a non-root path")
    return _canonical_origin_from_split(parsed)


def canonicalize_requested_origin(value: str) -> str:
    """Extract the deterministic origin from one requested network URL."""
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise AcquisitionPolicyError("requested_url must be a non-empty trimmed string")
    parsed = _split_url(value, field="requested_url")
    if parsed.fragment:
        raise AcquisitionPolicyError("requested_url must not contain a fragment")
    return _canonical_origin_from_split(parsed)


def _canonical_values(
    values: Iterable[str],
    *,
    field: str,
    allowed: frozenset[str] | None = None,
    identifier: bool = False,
    canonicalizer: Callable[[str], str] | None = None,
    maximum: int | None = None,
) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise AcquisitionPolicyError(f"{field} must be an iterable of strings, not a scalar string")
    normalized: list[str] = []
    for raw in values:
        if not isinstance(raw, str) or not raw.strip() or raw != raw.strip():
            raise AcquisitionPolicyError(f"{field} entries must be non-empty trimmed strings")
        value = raw
        if allowed is not None and value not in allowed:
            raise AcquisitionPolicyError(f"Unsupported {field} entry {value!r}")
        if identifier:
            try:
                ensure_identifier(value, field=field)
            except ValueError as exc:
                raise AcquisitionPolicyError(str(exc)) from exc
        if canonicalizer is not None:
            value = canonicalizer(value)
        normalized.append(value)
        if maximum is not None and len(normalized) > maximum:
            raise AcquisitionPolicyError(f"{field} exceeds the maximum of {maximum} entries")
    if not normalized:
        raise AcquisitionPolicyError(f"{field} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise AcquisitionPolicyError(f"{field} must not contain duplicate entries")
    return sorted(normalized)


def _canonical_source_rule(rule: Mapping[str, Any], *, require_canonical: bool) -> dict[str, Any]:
    if not isinstance(rule, Mapping):
        raise AcquisitionPolicyError("Each source_rules entry must be an object")
    keys = set(rule)
    if keys != _SOURCE_RULE_KEYS:
        missing = sorted(_SOURCE_RULE_KEYS - keys)
        unknown = sorted(str(key) for key in keys - _SOURCE_RULE_KEYS)
        raise AcquisitionPolicyError(f"Source rule fields differ from schema; missing={missing}, unknown={unknown}")

    source_id = rule["source_id"]
    if not isinstance(source_id, str):
        raise AcquisitionPolicyError("source_id must be a string")
    try:
        ensure_identifier(source_id, field="source_id")
    except ValueError as exc:
        raise AcquisitionPolicyError(str(exc)) from exc

    modes = rule["execution_modes"]
    if isinstance(modes, (str, bytes)) or not isinstance(modes, Iterable):
        raise AcquisitionPolicyError("execution_modes must be an iterable of strings")
    canonical_modes = _canonical_values(modes, field="execution_modes", allowed=EXECUTION_MODES)

    origins = rule["allowed_origins"]
    if isinstance(origins, (str, bytes)) or not isinstance(origins, Iterable):
        raise AcquisitionPolicyError("allowed_origins must be an iterable of strings")
    origin_values = list(origins)
    canonical_origins = (
        _canonical_values(
            origin_values,
            field="allowed_origins",
            canonicalizer=canonicalize_policy_origin,
            maximum=MAX_ORIGINS_PER_SOURCE,
        )
        if origin_values
        else []
    )

    has_online_mode = bool(set(canonical_modes) & _ONLINE_MODES)
    if has_online_mode and not canonical_origins:
        raise AcquisitionPolicyError("online-capable source rule requires at least one allowed origin")
    if not has_online_mode and canonical_origins:
        raise AcquisitionPolicyError("replay-only source rule must not authorize network origins")

    fallback_policy = rule["fallback_policy"]
    if not isinstance(fallback_policy, str) or fallback_policy not in FALLBACK_POLICIES:
        raise AcquisitionPolicyError(f"Unsupported fallback_policy {fallback_policy!r}")
    if fallback_policy == FALLBACK_PRIOR_CAPTURE and ONLINE_PREFERRED not in canonical_modes:
        raise AcquisitionPolicyError("prior-capture fallback requires ONLINE_PREFERRED in execution_modes")

    canonical = {
        "source_id": source_id,
        "execution_modes": canonical_modes,
        "allowed_origins": canonical_origins,
        "fallback_policy": fallback_policy,
    }
    if require_canonical and dict(rule) != canonical:
        raise AcquisitionPolicyError("source rule must use canonical sorted execution_modes and allowed_origins")
    return canonical


def _canonical_source_rules(
    rules: Iterable[Mapping[str, Any]],
    *,
    require_canonical: bool,
) -> list[dict[str, Any]]:
    if isinstance(rules, (str, bytes)) or not isinstance(rules, Iterable):
        raise AcquisitionPolicyError("source_rules must be an iterable of objects")
    canonical: list[dict[str, Any]] = []
    for rule in rules:
        canonical.append(_canonical_source_rule(rule, require_canonical=require_canonical))
        if len(canonical) > MAX_SOURCE_RULES:
            raise AcquisitionPolicyError(f"source_rules exceeds the maximum of {MAX_SOURCE_RULES} entries")
    if not canonical:
        raise AcquisitionPolicyError("source_rules must not be empty")
    source_ids = [rule["source_id"] for rule in canonical]
    if len(set(source_ids)) != len(source_ids):
        raise AcquisitionPolicyError("source_rules must contain each source_id exactly once")
    canonical.sort(key=lambda rule: str(rule["source_id"]))
    return canonical


def acquisition_policy_digest(packet: dict[str, Any]) -> str:
    """Compute the digest over every policy field except ``policy_sha256``."""
    controlled = {key: value for key, value in packet.items() if key != "policy_sha256"}
    return sha256_bytes(canonical_json_bytes(controlled))


def validate_acquisition_policy(packet: Any) -> dict[str, Any]:
    """Validate a canonical, digest-bound acquisition policy and return a copy."""
    if not isinstance(packet, dict):
        raise AcquisitionPolicyError("Acquisition policy must be an object")
    keys = set(packet)
    if keys != _POLICY_KEYS:
        missing = sorted(_POLICY_KEYS - keys)
        unknown = sorted(str(key) for key in keys - _POLICY_KEYS)
        raise AcquisitionPolicyError(
            f"Acquisition policy fields differ from schema; missing={missing}, unknown={unknown}"
        )
    if packet["policy_schema_version"] != POLICY_SCHEMA_VERSION:
        raise AcquisitionPolicyError(
            f"Unsupported policy_schema_version {packet['policy_schema_version']!r}; expected {POLICY_SCHEMA_VERSION!r}"
        )
    for field in ("policy_id", "programme_id"):
        value = packet[field]
        if not isinstance(value, str):
            raise AcquisitionPolicyError(f"{field} must be a string")
        try:
            ensure_identifier(value, field=field)
        except ValueError as exc:
            raise AcquisitionPolicyError(str(exc)) from exc
    approved_by = packet["approved_by"]
    if (
        not isinstance(approved_by, str)
        or not approved_by.strip()
        or approved_by != approved_by.strip()
        or len(approved_by) > 256
    ):
        raise AcquisitionPolicyError(
            "approved_by must be a non-empty trimmed claimed local identity of at most 256 characters"
        )

    approved_at = packet["approved_at"]
    if not isinstance(approved_at, str) or approved_at != _canonical_timestamp(approved_at, field="approved_at"):
        raise AcquisitionPolicyError("approved_at must use canonical UTC whole-second form")
    expires_at = packet["expires_at"]
    if expires_at is not None:
        if not isinstance(expires_at, str) or expires_at != _canonical_timestamp(expires_at, field="expires_at"):
            raise AcquisitionPolicyError("expires_at must be null or canonical UTC whole-second form")
        if _parse_timestamp(expires_at, field="expires_at") <= _parse_timestamp(approved_at, field="approved_at"):
            raise AcquisitionPolicyError("expires_at must be later than approved_at")

    source_rules = packet["source_rules"]
    if not isinstance(source_rules, list):
        raise AcquisitionPolicyError("source_rules must be a canonical list")
    canonical_rules = _canonical_source_rules(source_rules, require_canonical=True)
    if source_rules != canonical_rules:
        raise AcquisitionPolicyError("source_rules must be sorted by source_id")

    if packet["boundary"] != POLICY_BOUNDARY:
        raise AcquisitionPolicyError("Acquisition policy boundary is invalid")
    digest = packet["policy_sha256"]
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise AcquisitionPolicyError("policy_sha256 must be a 64-character lowercase hexadecimal digest")
    if digest != acquisition_policy_digest(packet):
        raise AcquisitionPolicyError("Acquisition policy digest mismatch")
    return copy.deepcopy(packet)


def build_acquisition_policy(
    *,
    policy_id: str,
    programme_id: str,
    approved_by: str,
    source_rules: Iterable[Mapping[str, Any]],
    approved_at: str,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Build one deterministic policy object from set-like source-rule inputs."""
    rules = _canonical_source_rules(source_rules, require_canonical=False)
    packet: dict[str, Any] = {
        "policy_schema_version": POLICY_SCHEMA_VERSION,
        "policy_id": policy_id,
        "programme_id": programme_id,
        "approved_by": approved_by,
        "approved_at": _canonical_timestamp(approved_at, field="approved_at"),
        "expires_at": _canonical_timestamp(expires_at, field="expires_at") if expires_at is not None else None,
        "source_rules": rules,
        "boundary": POLICY_BOUNDARY,
    }
    packet["policy_sha256"] = acquisition_policy_digest(packet)
    return validate_acquisition_policy(packet)


def require_acquisition_policy(
    policy: dict[str, Any],
    *,
    programme_id: str,
    source_id: str,
    execution_mode: str,
    requested_url: str | None = None,
    fallback_to_prior_capture: bool = False,
    at: str,
) -> dict[str, Any]:
    """Require one policy to permit the exact operational acquisition attempt.

    This check is intentionally independent of the live authorization gate. Code
    that performs network I/O must still satisfy ``require_network_authorization``.
    """
    validated = validate_acquisition_policy(policy)
    try:
        ensure_identifier(programme_id, field="programme_id")
        ensure_identifier(source_id, field="source_id")
    except ValueError as exc:
        raise AcquisitionPolicyError(str(exc)) from exc
    if not isinstance(execution_mode, str) or execution_mode not in EXECUTION_MODES:
        raise AcquisitionPolicyError(f"Unsupported execution_mode {execution_mode!r}")
    if validated["programme_id"] != programme_id:
        raise AcquisitionPolicyError("Acquisition policy programme_id does not match the attempted programme")

    source_rule = next((rule for rule in validated["source_rules"] if rule["source_id"] == source_id), None)
    if source_rule is None:
        raise AcquisitionPolicyError("Acquisition policy does not include the attempted source_id")
    if execution_mode not in source_rule["execution_modes"]:
        raise AcquisitionPolicyError("Source rule does not include the attempted execution_mode")

    now = _parse_timestamp(at, field="at")
    approved_at = _parse_timestamp(validated["approved_at"], field="approved_at")
    if now < approved_at:
        raise AcquisitionPolicyError("Acquisition policy is not active before approved_at")
    expires_at = validated["expires_at"]
    if expires_at is not None and now >= _parse_timestamp(expires_at, field="expires_at"):
        raise AcquisitionPolicyError("Acquisition policy has expired")

    if execution_mode == REPLAY_ONLY:
        if requested_url is not None:
            raise AcquisitionPolicyError("REPLAY_ONLY execution must not supply a requested_url")
        if fallback_to_prior_capture:
            raise AcquisitionPolicyError("REPLAY_ONLY is an explicit replay mode, not a live-fallback state")
        return validated

    if requested_url is None:
        raise AcquisitionPolicyError(f"{execution_mode} execution requires a requested_url")
    origin = canonicalize_requested_origin(requested_url)
    if origin not in source_rule["allowed_origins"]:
        raise AcquisitionPolicyError(f"Requested origin {origin!r} is outside the source rule")
    if fallback_to_prior_capture:
        if execution_mode != ONLINE_PREFERRED:
            raise AcquisitionPolicyError("Prior-capture fallback is permitted only for ONLINE_PREFERRED execution")
        if source_rule["fallback_policy"] != FALLBACK_PRIOR_CAPTURE:
            raise AcquisitionPolicyError("Source rule forbids prior-capture fallback")
    return validated
