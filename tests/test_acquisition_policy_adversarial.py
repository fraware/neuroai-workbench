from __future__ import annotations

import copy

import pytest

import neuroai_workbench.collector.acquisition_policy as ap

APPROVED_AT = "2026-09-04T09:00:00Z"
ACTIVE_AT = "2026-09-04T10:00:00Z"
EXPIRES_AT = "2026-09-05T09:00:00Z"


def rule(
    source_id: str = "SRC-0001",
    *,
    modes: object | None = None,
    origins: object | None = None,
    fallback_policy: object = ap.FALLBACK_FORBID,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "execution_modes": [ap.ONLINE_REQUIRED] if modes is None else modes,
        "allowed_origins": ["https://api.example.org"] if origins is None else origins,
        "fallback_policy": fallback_policy,
    }


def policy(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "policy_id": "ACP-ADVERSARIAL",
        "programme_id": "SU-TRIAL",
        "approved_by": "local-operator",
        "approved_at": APPROVED_AT,
        "expires_at": EXPIRES_AT,
        "source_rules": [rule()],
    }
    values.update(overrides)
    return ap.build_acquisition_policy(**values)  # type: ignore[arg-type]


def rebound(value: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(value)
    changed["policy_sha256"] = ap.acquisition_policy_digest(changed)
    return changed


@pytest.mark.parametrize(
    ("approved_at", "message"),
    [
        ("", "non-empty timestamp"),
        ("not-a-timestamp", "ISO-8601"),
        ("2026-09-04T09:00:00", "explicit timezone"),
    ],
)
def test_builder_rejects_invalid_approval_timestamps(approved_at: str, message: str) -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match=message):
        policy(approved_at=approved_at)


def test_builder_rejects_non_string_timestamp_runtime_input() -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match="non-empty timestamp"):
        policy(approved_at=123)


@pytest.mark.parametrize(
    "origin",
    [
        "https:///",
        "https://api.example.org:abc",
        "https://_service.example.org",
        "https://\ud800.example.org",
    ],
)
def test_origin_parser_fail_closed_on_host_and_port_edge_cases(origin: str) -> None:
    with pytest.raises(ap.AcquisitionPolicyError):
        ap.canonicalize_policy_origin(origin)


def test_idna_hostname_is_canonicalized_to_ascii() -> None:
    assert ap.canonicalize_policy_origin("https://bücher.example") == "https://xn--bcher-kva.example"


@pytest.mark.parametrize("value", [None, 1, b"https://api.example.org", " https://api.example.org"])
def test_policy_origin_requires_trimmed_text(value: object) -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match="trimmed string"):
        ap.canonicalize_policy_origin(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "requested_url",
    [
        "",
        " https://api.example.org/path",
        "https://api.example.org/path#fragment",
        "https://[2001:db8::1",
    ],
)
def test_requested_url_parser_fail_closed(requested_url: str) -> None:
    with pytest.raises(ap.AcquisitionPolicyError):
        ap.canonicalize_requested_origin(requested_url)


def test_non_default_port_is_preserved_in_canonical_origin() -> None:
    assert ap.canonicalize_policy_origin("https://api.example.org:8443/") == "https://api.example.org:8443"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("execution_modes", ap.ONLINE_REQUIRED, "iterable of strings"),
        ("execution_modes", 3, "iterable of strings"),
        ("execution_modes", [], "must not be empty"),
        ("execution_modes", [ap.ONLINE_REQUIRED, ap.ONLINE_REQUIRED], "duplicate entries"),
        ("execution_modes", [ap.ONLINE_REQUIRED, ""], "non-empty trimmed strings"),
        ("execution_modes", [ap.ONLINE_REQUIRED, 1], "non-empty trimmed strings"),
        ("allowed_origins", "https://api.example.org", "iterable of strings"),
        ("allowed_origins", 3, "iterable of strings"),
    ],
)
def test_source_rule_collection_fields_fail_closed(field: str, value: object, message: str) -> None:
    source_rule = rule()
    source_rule[field] = value
    with pytest.raises(ap.AcquisitionPolicyError, match=message):
        policy(source_rules=[source_rule])


def test_source_rule_must_be_an_object_with_exact_fields() -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match="must be an object"):
        policy(source_rules=["SRC-0001"])

    missing = rule()
    del missing["fallback_policy"]
    with pytest.raises(ap.AcquisitionPolicyError, match="missing=.*fallback_policy"):
        policy(source_rules=[missing])


def test_source_id_type_and_identifier_syntax_fail_closed() -> None:
    non_string = rule()
    non_string["source_id"] = 7
    with pytest.raises(ap.AcquisitionPolicyError, match="source_id must be a string"):
        policy(source_rules=[non_string])

    with pytest.raises(ap.AcquisitionPolicyError, match="Invalid source_id"):
        policy(source_rules=[rule("../escape")])


def test_prior_capture_policy_requires_online_preferred_mode() -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match="requires ONLINE_PREFERRED"):
        policy(source_rules=[rule(fallback_policy=ap.FALLBACK_PRIOR_CAPTURE)])


@pytest.mark.parametrize("source_rules", ["not-a-rule-list", b"rules", 7, None])
def test_source_rules_must_be_an_iterable_of_objects(source_rules: object) -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match="iterable of objects"):
        policy(source_rules=source_rules)


def test_source_rules_must_not_be_empty() -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match="must not be empty"):
        policy(source_rules=[])


def test_source_rule_count_is_bounded() -> None:
    rules = (rule(f"SRC-{index:05d}") for index in range(ap.MAX_SOURCE_RULES + 1))
    with pytest.raises(ap.AcquisitionPolicyError, match="maximum"):
        policy(source_rules=rules)


def test_validator_requires_object_and_exact_schema_version() -> None:
    with pytest.raises(ap.AcquisitionPolicyError, match="must be an object"):
        ap.validate_acquisition_policy([])

    changed = policy()
    changed["policy_schema_version"] = "2"
    changed = rebound(changed)
    with pytest.raises(ap.AcquisitionPolicyError, match="Unsupported policy_schema_version"):
        ap.validate_acquisition_policy(changed)


def test_validator_rejects_missing_top_level_field() -> None:
    changed = policy()
    del changed["boundary"]
    with pytest.raises(ap.AcquisitionPolicyError, match="missing=.*boundary"):
        ap.validate_acquisition_policy(changed)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("policy_id", 1, "policy_id must be a string"),
        ("programme_id", 1, "programme_id must be a string"),
        ("policy_id", "../escape", "Invalid policy_id"),
        ("programme_id", "bad/id", "Invalid programme_id"),
    ],
)
def test_validator_rejects_invalid_identifiers(field: str, value: object, message: str) -> None:
    changed = policy()
    changed[field] = value
    changed = rebound(changed)
    with pytest.raises(ap.AcquisitionPolicyError, match=message):
        ap.validate_acquisition_policy(changed)


@pytest.mark.parametrize("approved_by", [None, "", " operator ", "x" * 257])
def test_validator_rejects_invalid_claimed_operator_identity(approved_by: object) -> None:
    changed = policy()
    changed["approved_by"] = approved_by
    changed = rebound(changed)
    with pytest.raises(ap.AcquisitionPolicyError, match="approved_by"):
        ap.validate_acquisition_policy(changed)


def test_validator_rejects_invalid_expiry_contract() -> None:
    for expires_at in (1, "2026-09-05T11:00:00+02:00", APPROVED_AT, "2026-09-03T09:00:00Z"):
        changed = policy()
        changed["expires_at"] = expires_at
        changed = rebound(changed)
        with pytest.raises(ap.AcquisitionPolicyError, match="expires_at"):
            ap.validate_acquisition_policy(changed)


def test_validator_rejects_non_list_or_noncanonical_source_rules() -> None:
    changed = policy()
    changed["source_rules"] = tuple(changed["source_rules"])  # type: ignore[arg-type]
    changed = rebound(changed)
    with pytest.raises(ap.AcquisitionPolicyError, match="canonical list"):
        ap.validate_acquisition_policy(changed)

    two_rule_policy = policy(source_rules=[rule("SRC-0001"), rule("SRC-0002")])
    changed = copy.deepcopy(two_rule_policy)
    changed["source_rules"] = list(reversed(changed["source_rules"]))  # type: ignore[arg-type]
    changed = rebound(changed)
    with pytest.raises(ap.AcquisitionPolicyError, match="sorted by source_id"):
        ap.validate_acquisition_policy(changed)


def test_validator_rejects_noncanonical_source_rule_content() -> None:
    changed = policy(
        source_rules=[
            rule(
                modes=[ap.ONLINE_PREFERRED, ap.ONLINE_REQUIRED],
                origins=["https://a.example.org", "https://b.example.org"],
            )
        ]
    )
    modified = copy.deepcopy(changed)
    source_rules = modified["source_rules"]
    assert isinstance(source_rules, list)
    source_rule = source_rules[0]
    source_rule["execution_modes"] = list(reversed(source_rule["execution_modes"]))
    modified = rebound(modified)
    with pytest.raises(ap.AcquisitionPolicyError, match="canonical sorted"):
        ap.validate_acquisition_policy(modified)


def test_validator_rejects_boundary_and_digest_shape_substitution() -> None:
    changed = policy()
    changed["boundary"] = "Policy grants publication authority"
    changed = rebound(changed)
    with pytest.raises(ap.AcquisitionPolicyError, match="boundary is invalid"):
        ap.validate_acquisition_policy(changed)

    changed = policy()
    changed["policy_sha256"] = None
    with pytest.raises(ap.AcquisitionPolicyError, match="lowercase hexadecimal"):
        ap.validate_acquisition_policy(changed)


def test_request_scope_identifier_and_mode_types_fail_closed() -> None:
    current = policy()
    for programme_id, source_id, execution_mode in (
        ("../bad", "SRC-0001", ap.ONLINE_REQUIRED),
        ("SU-TRIAL", "../bad", ap.ONLINE_REQUIRED),
        ("SU-TRIAL", "SRC-0001", 1),
    ):
        with pytest.raises(ap.AcquisitionPolicyError):
            ap.require_acquisition_policy(
                current,
                programme_id=programme_id,
                source_id=source_id,
                execution_mode=execution_mode,  # type: ignore[arg-type]
                requested_url="https://api.example.org/data",
                at=ACTIVE_AT,
            )


def test_request_requires_valid_runtime_timestamp() -> None:
    current = policy()
    for at in ("", "not-a-time", "2026-09-04T10:00:00"):
        with pytest.raises(ap.AcquisitionPolicyError):
            ap.require_acquisition_policy(
                current,
                programme_id="SU-TRIAL",
                source_id="SRC-0001",
                execution_mode=ap.ONLINE_REQUIRED,
                requested_url="https://api.example.org/data",
                at=at,
            )


def test_online_request_requires_url_and_replay_rejects_fallback_flag() -> None:
    current = policy()
    with pytest.raises(ap.AcquisitionPolicyError, match="requires a requested_url"):
        ap.require_acquisition_policy(
            current,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ap.ONLINE_REQUIRED,
            at=ACTIVE_AT,
        )

    replay = policy(source_rules=[rule(modes=[ap.REPLAY_ONLY], origins=[])])
    with pytest.raises(ap.AcquisitionPolicyError, match="explicit replay mode"):
        ap.require_acquisition_policy(
            replay,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ap.REPLAY_ONLY,
            fallback_to_prior_capture=True,
            at=ACTIVE_AT,
        )


def test_policy_without_expiry_remains_valid_after_approval() -> None:
    current = policy(expires_at=None)
    validated = ap.require_acquisition_policy(
        current,
        programme_id="SU-TRIAL",
        source_id="SRC-0001",
        execution_mode=ap.ONLINE_REQUIRED,
        requested_url="https://api.example.org/data",
        at="2030-01-01T00:00:00Z",
    )
    assert validated["expires_at"] is None
