from __future__ import annotations

import json

import pytest

from neuroai_workbench.collector import service as collector_service
from neuroai_workbench.collector.authorization import LIVE_AUTHORIZATION_ENV, build_authorization_packet

_LEGACY_SHADOW_LIVE_MODULES = frozenset(
    {
        "test_shadow_comparative_refresh.py",
        "test_shadow_evaluation_cycle.py",
        "test_shadow_live_collection.py",
    }
)
_PHASE3_RUNTIME_PROOF_MODULE = "test_online_first_runtime_proof.py"
_PHASE3_SYNTHETIC_CAPTURE_TIME = "2026-09-05T12:00:00Z"


@pytest.fixture(autouse=True)
def _bind_live_authorization_for_legacy_shadow_tests(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Supply the authorization half of the live gate to legacy downstream tests.

    These modules exercise behavior after authorization and already opt into the
    independent ``NEUROAI_LIVE_COLLECTION=1`` gate themselves. Authorization
    boundary tests live in dedicated modules and are intentionally excluded so
    missing, malformed, and tampered packets continue to fail closed.
    """
    if request.path.name not in _LEGACY_SHADOW_LIVE_MODULES:
        return

    packet = build_authorization_packet(
        authorization_id="AUTH-TEST-LEGACY-SHADOW",
        authorized_by="pytest-fixture",
        purpose="Network-free unit test exercising behavior after the live authorization boundary.",
        network_mode="AUTHORIZED_NETWORK",
        network_permitted=True,
        authorized_at="2026-09-03T00:00:00Z",
    )
    monkeypatch.setenv(
        LIVE_AUTHORIZATION_ENV,
        json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
    )


@pytest.fixture(autouse=True)
def _freeze_phase3_synthetic_capture_clock(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the Phase 3 synthetic live capture inside its declared replay cutoff.

    The proof tests intentionally use a historical ``as_of`` so recurrence is
    deterministic. Collector results otherwise receive wall-clock ``retrieved_at``
    values, which would make the unchanged fixture expire as calendar time moves
    forward. This patch is restricted to the Phase 3 test seam; production and
    ordinary replay clocks remain untouched.
    """
    if request.path.name != _PHASE3_RUNTIME_PROOF_MODULE:
        return
    monkeypatch.setattr(collector_service, "utc_now", lambda: _PHASE3_SYNTHETIC_CAPTURE_TIME)
