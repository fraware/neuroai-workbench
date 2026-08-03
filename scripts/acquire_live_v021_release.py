#!/usr/bin/env python3
"""Acquire and audit the private v0.2.1 release inside a trusted GitHub runner."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from scripts import verify_github_release_assets as release_audit

REPOSITORY = "fraware/neuroai-workbench"
TAG = "v0.2.1"
EXPECTED_COMMIT = "7e60d10271ceba7ec5674bcd9de2d8903947bdf5"


def _checkout_token() -> str:
    result = subprocess.run(
        ["git", "config", "--get-regexp", r"^http\..*\.extraheader$"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("GitHub checkout authorization header is unavailable")
    for line in result.stdout.splitlines():
        _, _, value = line.partition(" ")
        prefix = "AUTHORIZATION: basic "
        if value.upper().startswith(prefix.upper()):
            encoded = value[len(prefix) :].strip()
            decoded = base64.b64decode(encoded).decode("utf-8")
            _, separator, token = decoded.partition(":")
            if separator and token:
                return token
    raise RuntimeError("GitHub checkout token could not be decoded")


def _run_gh(arguments: list[str], *, token: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["GH_TOKEN"] = token
    environment.pop("GITHUB_TOKEN", None)
    return subprocess.run(
        ["gh", *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_output(arguments: list[str]) -> str:
    result = subprocess.run(["git", *arguments], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout.strip()


def acquire_and_audit() -> dict[str, Any]:
    token = _checkout_token()
    expected_assets = sorted(release_audit._expected_assets(TAG.removeprefix("v")))
    with tempfile.TemporaryDirectory(prefix="v021-live-audit-") as temporary:
        root = Path(temporary)
        assets = root / "assets"
        assets.mkdir()

        view = _run_gh(
            [
                "release",
                "view",
                TAG,
                "--repo",
                REPOSITORY,
                "--json",
                "tagName,isDraft,isPrerelease,url,body,assets",
            ],
            token=token,
        )
        if view.returncode != 0:
            raise RuntimeError(f"release metadata acquisition failed: {view.stderr.strip()}")
        release = json.loads(view.stdout)
        if not isinstance(release, dict):
            raise RuntimeError("release metadata is not a JSON object")

        download = _run_gh(
            ["release", "download", TAG, "--repo", REPOSITORY, "--dir", str(assets), "--clobber"],
            token=token,
        )
        if download.returncode != 0:
            raise RuntimeError(f"release asset acquisition failed: {download.stderr.strip()}")

        tag_type = _git_output(["cat-file", "-t", f"refs/tags/{TAG}"])
        tag_commit = _git_output(["rev-parse", f"refs/tags/{TAG}^{{commit}}"])
        tag_record = {"tag": TAG, "tag_type": tag_type, "tag_commit": tag_commit}

        attestation_rows: list[dict[str, Any]] = []
        for name in expected_assets:
            path = assets / name
            verification = _run_gh(
                ["attestation", "verify", str(path), "--repo", REPOSITORY],
                token=token,
            )
            attestation_rows.append(
                {
                    "name": name,
                    "verified": verification.returncode == 0,
                    "diagnostic": (
                        "verified"
                        if verification.returncode == 0
                        else (verification.stderr.strip() or verification.stdout.strip() or "verification failed")[:500]
                    ),
                }
            )

        report = release_audit.audit(
            assets_dir=assets,
            release=release,
            tag_record=tag_record,
            attestations={"assets": attestation_rows},
            expected_tag=TAG,
            expected_commit=EXPECTED_COMMIT,
            require_published=True,
        )
        report["live_acquisition"] = {
            "repository": REPOSITORY,
            "tag": TAG,
            "downloaded_assets": sorted(path.name for path in assets.iterdir() if path.is_file()),
            "tag_type": tag_type,
            "attestations": attestation_rows,
            "credential_source": "ephemeral GitHub Actions checkout credential",
            "protected_bytes_retained": False,
        }
        return report


if __name__ == "__main__":
    print(json.dumps(acquire_and_audit(), ensure_ascii=False, indent=2))
