"""Offline checks for bounded temporal-source acquisition."""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from scripts.r1_7_capture_temporal_sources import SOURCE_TARGETS, SameOriginRedirect, capture_target, main


def test_allowlisted_sources_are_distinct_https_urls() -> None:
    assert len(SOURCE_TARGETS) == 6
    assert len({row[0] for row in SOURCE_TARGETS}) == 6
    assert all(row[1].startswith("https://") and row[2] for row in SOURCE_TARGETS)


def test_refuses_network_without_explicit_opt_in(tmp_path: Path) -> None:
    output = tmp_path / "not-created"
    assert not output.exists()
    with pytest.raises(SystemExit, match="2"):
        main(["--output-dir", str(output)])
    assert not output.exists()


def test_unapproved_target_is_rejected_before_network(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown source"):
        capture_target("arbitrary", "https://example.com", "fake", tmp_path)
    slug, url, marker = SOURCE_TARGETS[0]
    with pytest.raises(ValueError, match="allowlist"):
        capture_target(slug, url + "&redirect=1", marker, tmp_path)


def test_cross_domain_redirect_is_refused() -> None:
    request = urllib.request.Request(SOURCE_TARGETS[0][1])
    with pytest.raises(ValueError, match="redirect refused"):
        SameOriginRedirect().redirect_request(
            request, None, 301, "Moved", {}, "https://unrelated.example.org/unsafe"
        )
