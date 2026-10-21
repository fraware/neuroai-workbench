"""Network-free tests for public PMC source capture and publication identity checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.r1_7_capture_public_pmc import (
    MAX_BYTES,
    PMC_BY_PMID,
    NoRedirect,
    _verified_xml,
    main,
)

ROOT = Path(__file__).resolve().parents[2]


def _sample(pmid: str, pmcid: str) -> bytes:
    return (
        f'<article><front><article-meta><article-id pub-id-type="pmid">{pmid}</article-id>'
        f'<article-id pub-id-type="pmcid">{pmcid}</article-id>'
        "</article-meta></front><body><p>Synthetic source; no actual publication.</p></body></article>"
    ).encode()


def test_four_frozen_public_identifiers_are_exact() -> None:
    assert PMC_BY_PMID == {
        "42505450": "PMC13406779",
        "42645991": "PMC13514590",
        "42022893": "PMC13095558",
        "41939223": "PMC13044042",
    }
    assert MAX_BYTES == 5 * 1024 * 1024


def test_xml_identity_validation_accepts_matching_synthetic_jats() -> None:
    _verified_xml(_sample("42505450", "PMC13406779"), "42505450", "PMC13406779")


@pytest.mark.parametrize(
    "wrong",
    [
        _sample("00000000", "PMC13406779"),
        _sample("42505450", "PMC99999999"),
        b"<html><body>HTTP error page</body></html>",
    ],
)
def test_xml_identity_validation_rejects_wrong_article(wrong: bytes) -> None:
    with pytest.raises(ValueError, match="not an article|identifiers do not match"):
        _verified_xml(wrong, "42505450", "PMC13406779")


def test_capture_command_explicitly_refuses_implicit_network(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output = tmp_path / "must-not-be-created"
    assert not output.exists()
    with pytest.raises(SystemExit, match="2"):
        main(["--output-dir", str(output)])
    assert "pass --allow-network explicitly" in capsys.readouterr().err
    assert not output.exists()


def test_no_redirect_policy_blocks_unexpected_target() -> None:
    request = __import__("urllib.request", fromlist=["Request"]).Request(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13406779/fullTextXML"
    )
    with pytest.raises(ValueError, match="refuses redirects"):
        NoRedirect().redirect_request(request, None, 302, "Found", {}, "https://127.0.0.1/private")


def test_cli_help_has_no_network_side_effects(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.r1_7_capture_public_pmc", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert "--allow-network" in result.stdout
    assert not list(tmp_path.iterdir())
