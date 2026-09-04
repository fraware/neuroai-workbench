from __future__ import annotations

import copy

import pytest

from neuroai_workbench.collector.acquisition_policy import (
    FALLBACK_FORBID,
    FALLBACK_PRIOR_CAPTURE,
    ONLINE_PREFERRED,
    ONLINE_REQUIRED,
    REPLAY_ONLY,
    AcquisitionPolicyError,
    build_acquisition_policy,
    canonicalize_policy_origin,
    require_acquisition_policy,
    validate_acquisition_policy,
)

APPROVED_AT = "2026-09-04T09:00:00Z"
ACTIVE_AT = "2026-09-04T10:00:00Z"
EXPIRES_AT = "2026-09-05T09:00:00Z"


def source_rule(
    source_id: str,
    *,
    modes: list[str] | None = None,
    origins: list[str] | None = None,
    fallback_policy: str = FALLBACK_FORBID,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "execution_modes": modes or [ONLINE_REQUIRED],
        "allowed_origins": origins or ["https://api.example.org"],
        "fallback_policy": fallback_policy,
    }


def build_online_policy(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "policy_id": "ACP-0001",
        "programme_id": "SU-TRIAL",
        "approved_by": "local-operator",
        "approved_at": APPROVED_AT,
        "expires_at": EXPIRES_AT,
        "source_rules": [
            source_rule(
                "SRC-0002",
                modes=[REPLAY_ONLY, ONLINE_PREFERRED],
                origins=["https://registry.example.org:443/"],
                fallback_policy=FALLBACK_PRIOR_CAPTURE,
            ),
            source_rule(
                "SRC-0001",
                modes=[ONLINE_REQUIRED, ONLINE_PREFERRED],
                origins=["https://api.example.org:443/"],
                fallback_policy=FALLBACK_PRIOR_CAPTURE,
            ),
        ],
    }
    kwargs.update(overrides)
    return build_acquisition_policy(**kwargs)  # type: ignore[arg-type]


def test_builder_canonicalizes_source_rules_and_set_like_inputs_deterministically() -> None:
    first = build_online_policy()
    second = build_online_policy(
        source_rules=[
            source_rule(
                "SRC-0001",
                modes=[ONLINE_PREFERRED, ONLINE_REQUIRED],
                origins=["https://api.example.org/"],
                fallback_policy=FALLBACK_PRIOR_CAPTURE,
            ),
            source_rule(
                "SRC-0002",
                modes=[ONLINE_PREFERRED, REPLAY_ONLY],
                origins=["https://registry.example.org"],
                fallback_policy=FALLBACK_PRIOR_CAPTURE,
            ),
        ]
    )
    assert first == second
    assert [rule["source_id"] for rule in first["source_rules"]] == ["SRC-0001", "SRC-0002"]
    assert first["source_rules"][0]["allowed_origins"] == ["https://api.example.org"]


def test_post_digest_tampering_is_rejected() -> None:
    policy = build_online_policy()
    policy["source_rules"][0]["allowed_origins"] = ["https://evil.invalid"]
    with pytest.raises(AcquisitionPolicyError, match="digest mismatch"):
        validate_acquisition_policy(policy)


def test_unknown_top_level_and_source_rule_fields_fail_closed() -> None:
    policy = build_online_policy()
    policy["future_semantics"] = True
    with pytest.raises(AcquisitionPolicyError, match=r"unknown=\['future_semantics'\]"):
        validate_acquisition_policy(policy)

    rule = source_rule("SRC-0001")
    rule["redirect_anywhere"] = True
    with pytest.raises(AcquisitionPolicyError, match=r"unknown=\['redirect_anywhere'\]"):
        build_online_policy(source_rules=[rule])


def test_unknown_execution_mode_is_rejected() -> None:
    with pytest.raises(AcquisitionPolicyError, match="Unsupported execution_modes entry"):
        build_online_policy(source_rules=[source_rule("SRC-0001", modes=["ONLINE_UNBOUNDED"])])


def test_online_source_rule_requires_an_allowed_origin() -> None:
    rule = source_rule("SRC-0001", modes=[ONLINE_REQUIRED])
    rule["allowed_origins"] = []
    with pytest.raises(AcquisitionPolicyError, match="requires at least one allowed origin"):
        build_online_policy(source_rules=[rule])


def test_replay_only_source_rule_refuses_network_origins() -> None:
    with pytest.raises(AcquisitionPolicyError, match="replay-only source rule"):
        build_online_policy(
            source_rules=[source_rule("SRC-0001", modes=[REPLAY_ONLY], origins=["https://api.example.org"])]
        )


def test_exact_allowed_origin_succeeds_for_bound_source() -> None:
    policy = build_online_policy()
    validated = require_acquisition_policy(
        policy,
        programme_id="SU-TRIAL",
        source_id="SRC-0001",
        execution_mode=ONLINE_REQUIRED,
        requested_url="https://api.example.org/v2/studies?page=2",
        at=ACTIVE_AT,
    )
    assert validated["policy_id"] == "ACP-0001"


def test_source_cannot_use_other_source_origin() -> None:
    policy = build_online_policy()
    with pytest.raises(AcquisitionPolicyError, match="outside the source rule"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_REQUIRED,
            requested_url="https://registry.example.org/v2/studies",
            at=ACTIVE_AT,
        )


def test_suffix_confusable_host_is_rejected() -> None:
    policy = build_online_policy()
    with pytest.raises(AcquisitionPolicyError, match="outside the source rule"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_REQUIRED,
            requested_url="https://api.example.org.evil.invalid/v2/studies",
            at=ACTIVE_AT,
        )


@pytest.mark.parametrize(
    "requested_url",
    [
        "http://api.example.org/v2/studies",
        "https://api.example.org:444/v2/studies",
    ],
)
def test_scheme_and_non_default_port_confusion_are_rejected(requested_url: str) -> None:
    policy = build_online_policy()
    with pytest.raises(AcquisitionPolicyError, match="outside the source rule"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_REQUIRED,
            requested_url=requested_url,
            at=ACTIVE_AT,
        )


def test_origin_and_request_user_info_are_rejected() -> None:
    with pytest.raises(AcquisitionPolicyError, match="user-info"):
        canonicalize_policy_origin("https://user:secret@api.example.org")
    policy = build_online_policy()
    with pytest.raises(AcquisitionPolicyError, match="user-info"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_REQUIRED,
            requested_url="https://user:secret@api.example.org/v2/studies",
            at=ACTIVE_AT,
        )


@pytest.mark.parametrize(
    "origin",
    [
        "ftp://api.example.org",
        "https://api.example.org/path",
        "https://api.example.org?scope=all",
        "https://api.example.org#fragment",
        "https://*.example.org",
        "https://api.example.org.",
        "https://api.example.org:99999",
        " https://api.example.org",
        "https://[2001:db8::1",
        "https://[fe80::1%25eth0]",
    ],
)
def test_malformed_or_ambiguous_policy_origins_are_rejected(origin: str) -> None:
    with pytest.raises(AcquisitionPolicyError):
        canonicalize_policy_origin(origin)


def test_default_ports_and_ip_literals_are_canonicalized() -> None:
    assert canonicalize_policy_origin("https://example.org:443/") == "https://example.org"
    assert canonicalize_policy_origin("http://example.org:80") == "http://example.org"
    assert canonicalize_policy_origin("https://[2001:0db8::1]:443/") == "https://[2001:db8::1]"


def test_expired_and_preapproval_policies_are_rejected_at_request_time() -> None:
    policy = build_online_policy()
    with pytest.raises(AcquisitionPolicyError, match="expired"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_REQUIRED,
            requested_url="https://api.example.org/v2/studies",
            at=EXPIRES_AT,
        )
    with pytest.raises(AcquisitionPolicyError, match="not active"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_REQUIRED,
            requested_url="https://api.example.org/v2/studies",
            at="2026-09-04T08:59:59Z",
        )


def test_builder_rejects_fractional_timestamp_instead_of_truncating() -> None:
    with pytest.raises(AcquisitionPolicyError, match="whole-second precision"):
        build_online_policy(approved_at="2026-09-04T09:00:00.500Z")


def test_replay_only_refuses_network_url() -> None:
    replay_rule = source_rule("SRC-0001", modes=[REPLAY_ONLY])
    replay_rule["allowed_origins"] = []
    policy = build_acquisition_policy(
        policy_id="ACP-REPLAY",
        programme_id="SU-TRIAL",
        approved_by="local-operator",
        approved_at=APPROVED_AT,
        source_rules=[replay_rule],
    )
    require_acquisition_policy(
        policy,
        programme_id="SU-TRIAL",
        source_id="SRC-0001",
        execution_mode=REPLAY_ONLY,
        at=ACTIVE_AT,
    )
    with pytest.raises(AcquisitionPolicyError, match="must not supply"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=REPLAY_ONLY,
            requested_url="https://api.example.org/v2/studies",
            at=ACTIVE_AT,
        )


def test_prior_capture_fallback_is_online_preferred_only_and_explicit() -> None:
    policy = build_online_policy()
    require_acquisition_policy(
        policy,
        programme_id="SU-TRIAL",
        source_id="SRC-0001",
        execution_mode=ONLINE_PREFERRED,
        requested_url="https://api.example.org/v2/studies",
        fallback_to_prior_capture=True,
        at=ACTIVE_AT,
    )
    with pytest.raises(AcquisitionPolicyError, match="only for ONLINE_PREFERRED"):
        require_acquisition_policy(
            policy,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_REQUIRED,
            requested_url="https://api.example.org/v2/studies",
            fallback_to_prior_capture=True,
            at=ACTIVE_AT,
        )

    no_fallback = build_online_policy(
        source_rules=[
            source_rule(
                "SRC-0001",
                modes=[ONLINE_PREFERRED],
                origins=["https://api.example.org"],
                fallback_policy=FALLBACK_FORBID,
            )
        ]
    )
    with pytest.raises(AcquisitionPolicyError, match="forbids prior-capture fallback"):
        require_acquisition_policy(
            no_fallback,
            programme_id="SU-TRIAL",
            source_id="SRC-0001",
            execution_mode=ONLINE_PREFERRED,
            requested_url="https://api.example.org/v2/studies",
            fallback_to_prior_capture=True,
            at=ACTIVE_AT,
        )


def test_policy_scope_mismatch_fails_closed() -> None:
    policy = build_online_policy()
    attempts = [
        {"programme_id": "OTHER", "source_id": "SRC-0001", "execution_mode": ONLINE_REQUIRED},
        {"programme_id": "SU-TRIAL", "source_id": "SRC-9999", "execution_mode": ONLINE_REQUIRED},
        {"programme_id": "SU-TRIAL", "source_id": "SRC-0001", "execution_mode": REPLAY_ONLY},
        {"programme_id": "SU-TRIAL", "source_id": "SRC-0001", "execution_mode": "UNKNOWN"},
    ]
    for attempt in attempts:
        with pytest.raises(AcquisitionPolicyError):
            require_acquisition_policy(
                policy,
                requested_url="https://api.example.org/v2/studies",
                at=ACTIVE_AT,
                **attempt,  # type: ignore[arg-type]
            )


def test_duplicate_source_rules_and_origins_fail_closed() -> None:
    with pytest.raises(AcquisitionPolicyError, match="each source_id exactly once"):
        build_online_policy(source_rules=[source_rule("SRC-0001"), source_rule("SRC-0001")])
    with pytest.raises(AcquisitionPolicyError, match="duplicate entries"):
        build_online_policy(
            source_rules=[
                source_rule(
                    "SRC-0001",
                    origins=["https://api.example.org", "https://api.example.org/"],
                )
            ]
        )


def test_source_rule_field_types_and_origin_bounds_fail_closed() -> None:
    rule = source_rule("SRC-0001")
    rule["fallback_policy"] = []
    with pytest.raises(AcquisitionPolicyError, match="Unsupported fallback_policy"):
        build_online_policy(source_rules=[rule])

    too_many_origins = [f"https://host-{index}.example.org" for index in range(65)]
    with pytest.raises(AcquisitionPolicyError, match="maximum of 64 entries"):
        build_online_policy(source_rules=[source_rule("SRC-0001", origins=too_many_origins)])


def test_validator_returns_a_detached_nested_policy_copy() -> None:
    policy = build_online_policy()
    validated = validate_acquisition_policy(policy)
    validated["source_rules"][0]["allowed_origins"][0] = "https://changed.invalid"
    assert policy["source_rules"][0]["allowed_origins"][0] == "https://api.example.org"


def test_noncanonical_timestamp_and_digest_case_fail_closed() -> None:
    policy = build_online_policy()
    changed = copy.deepcopy(policy)
    changed["approved_at"] = "2026-09-04T11:00:00+02:00"
    changed["policy_sha256"] = "0" * 64
    with pytest.raises(AcquisitionPolicyError, match="canonical UTC"):
        validate_acquisition_policy(changed)

    changed = copy.deepcopy(policy)
    changed["policy_sha256"] = str(changed["policy_sha256"]).upper()
    with pytest.raises(AcquisitionPolicyError, match="lowercase hexadecimal"):
        validate_acquisition_policy(changed)


def test_policy_success_does_not_bypass_existing_live_authorization_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroai_workbench.collector.authorization import (
        LIVE_COLLECTION_ENV,
        CollectionAuthorizationError,
        build_authorization_packet,
        require_network_authorization,
    )

    policy = build_online_policy()
    require_acquisition_policy(
        policy,
        programme_id="SU-TRIAL",
        source_id="SRC-0001",
        execution_mode=ONLINE_REQUIRED,
        requested_url="https://api.example.org/v2/studies",
        at=ACTIVE_AT,
    )

    authorization = build_authorization_packet(
        authorization_id="AUTH-ONLINE-FIRST-PHASE1",
        authorized_by="local-operator",
        purpose="Regression: policy does not replace the live gate",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
        authorized_at=APPROVED_AT,
    )
    monkeypatch.delenv(LIVE_COLLECTION_ENV, raising=False)
    with pytest.raises(CollectionAuthorizationError, match=f"{LIVE_COLLECTION_ENV}=1"):
        require_network_authorization(authorization)
