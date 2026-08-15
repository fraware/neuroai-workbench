from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

import neuroai_workbench.governance_release as release_mod


def _current_policy_package() -> dict[str, Any]:
    policy = release_mod.load_governance_completion_policy(version="current")
    return {
        "policy_evaluation_reference": {
            "policy_id": policy["policy_id"],
            "policy_version": policy["policy_version"],
            "policy_sha256": release_mod.governance_policy_sha256(policy),
        }
    }


def test_designated_actor_is_admitted_only_for_current_policy_binding() -> None:
    package = _current_policy_package()
    assert release_mod._require_designated_authority_actor(package, "fraware") == "fraware"


def test_non_designated_actor_is_rejected() -> None:
    with pytest.raises(ValueError, match="designated governance authority fraware"):
        release_mod._require_designated_authority_actor(_current_policy_package(), "other-human")


def test_stale_policy_binding_is_rejected() -> None:
    package = deepcopy(_current_policy_package())
    package["policy_evaluation_reference"]["policy_version"] = "1.0.0"
    with pytest.raises(ValueError, match="not bound to the current designated-authority policy"):
        release_mod._require_designated_authority_actor(package, "fraware")


def test_missing_policy_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing its policy evaluation reference"):
        release_mod._require_designated_authority_actor({}, "fraware")
