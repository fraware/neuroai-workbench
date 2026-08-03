#!/usr/bin/env python3
"""Verify an acquired GitHub release, its assets, bundle, and attestations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Any

EXPECTED_WITHHELD_CLAIMS = {
    "UNESCO endorsement or official-methodology status",
    "Legal or regulatory authorization",
    "Clinical safety or effectiveness",
    "Production-grade cybersecurity",
    "Evidence authenticity or methodological adequacy",
    "Completed system conformance",
}
_RELEASE_NOTE_BOUNDARIES = (
    "scientific validity",
    "clinical safety",
    "regulatory authorization",
    "conformance",
    "institutional endorsement",
    "official UNESCO",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _expected_assets(version: str) -> set[str]:
    return {
        f"neuroai_workbench-{version}-py3-none-any.whl",
        f"neuroai_workbench-{version}.tar.gz",
        f"neuroai-workbench-v{version}.bundle",
        "sbom.cdx.json",
        "RELEASE_VERIFICATION.json",
        "SHA256SUMS",
    }


def _parse_checksums(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"SHA256SUMS line {line_number} is malformed")
        digest, name = parts
        name = name.lstrip("*").strip()
        if not _SHA256_RE.fullmatch(digest):
            raise ValueError(f"SHA256SUMS line {line_number} has an invalid digest")
        if Path(name).name != name or name in records:
            raise ValueError(f"SHA256SUMS line {line_number} has an unsafe or duplicate filename")
        records[name] = digest
    return records


def _wheel_metadata(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        broken = archive.testzip()
        if broken is not None:
            raise ValueError(f"Wheel ZIP integrity failed at {broken}")
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        record_names = [name for name in archive.namelist() if name.endswith(".dist-info/RECORD")]
        if len(metadata_names) != 1 or len(record_names) != 1:
            raise ValueError("Wheel must contain exactly one METADATA and RECORD file")
        message = BytesParser(policy=default).parsebytes(archive.read(metadata_names[0]))
        return {"name": str(message["Name"] or ""), "version": str(message["Version"] or "")}


def _sdist_metadata(path: Path) -> dict[str, str]:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        unsafe = [member.name for member in members if member.name.startswith("/") or ".." in Path(member.name).parts]
        if unsafe:
            raise ValueError(f"Source distribution contains unsafe paths: {unsafe[:3]}")
        package_info = [member for member in members if member.name.endswith("/PKG-INFO")]
        if len(package_info) != 1:
            raise ValueError("Source distribution must contain exactly one PKG-INFO")
        extracted = archive.extractfile(package_info[0])
        if extracted is None:
            raise ValueError("Source distribution PKG-INFO could not be read")
        message = BytesParser(policy=default).parsebytes(extracted.read())
        return {"name": str(message["Name"] or ""), "version": str(message["Version"] or "")}


def _bundle_commit(bundle: Path, tag: str) -> tuple[bool, str, str]:
    verify = subprocess.run(
        ["git", "bundle", "verify", str(bundle)],
        text=True,
        capture_output=True,
        check=False,
    )
    with tempfile.TemporaryDirectory(prefix="release-bundle-") as tmp:
        bare = Path(tmp) / "repository.git"
        init = subprocess.run(["git", "init", "--bare", str(bare)], text=True, capture_output=True, check=False)
        fetch = subprocess.run(
            ["git", "-C", str(bare), "fetch", str(bundle), f"refs/tags/{tag}:refs/tags/{tag}"],
            text=True,
            capture_output=True,
            check=False,
        )
        rev = subprocess.run(
            ["git", "-C", str(bare), "rev-list", "-n", "1", f"refs/tags/{tag}"],
            text=True,
            capture_output=True,
            check=False,
        )
    detail = "\n".join(
        part.strip() for part in (verify.stdout, verify.stderr, init.stderr, fetch.stderr, rev.stderr) if part.strip()
    )
    return verify.returncode == init.returncode == fetch.returncode == rev.returncode == 0, rev.stdout.strip(), detail


def audit(
    *,
    assets_dir: Path,
    release: dict[str, Any],
    tag_record: dict[str, Any],
    attestations: dict[str, Any],
    expected_tag: str,
    expected_commit: str,
    require_published: bool,
) -> dict[str, Any]:
    version = expected_tag.removeprefix("v")
    expected_assets = _expected_assets(version)
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any) -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    check("Release tag identity", release.get("tagName") == expected_tag, release.get("tagName"))
    check("Release is not a prerelease", release.get("isPrerelease") is False, release.get("isPrerelease"))
    check(
        "Release publication state",
        (release.get("isDraft") is False) if require_published else isinstance(release.get("isDraft"), bool),
        {"isDraft": release.get("isDraft"), "required": "PUBLISHED" if require_published else "RECORDED"},
    )

    assets = release.get("assets")
    asset_rows = assets if isinstance(assets, list) else []
    asset_names = {str(item.get("name")) for item in asset_rows if isinstance(item, dict)}
    check("Exact custom release asset inventory", asset_names == expected_assets, sorted(asset_names))
    files = {path.name for path in assets_dir.iterdir() if path.is_file()}
    check("Downloaded asset inventory", files == expected_assets, sorted(files))

    checksum_path = assets_dir / "SHA256SUMS"
    try:
        checksum_records = _parse_checksums(checksum_path)
        checksum_parse_error = None
    except (OSError, ValueError) as exc:
        checksum_records = {}
        checksum_parse_error = str(exc)
    check("SHA256SUMS parses safely", checksum_parse_error is None, checksum_parse_error or checksum_records)
    check(
        "SHA256SUMS covers every non-manifest asset",
        set(checksum_records) == expected_assets - {"SHA256SUMS"},
        sorted(checksum_records),
    )
    for name in sorted(expected_assets - {"SHA256SUMS"}):
        path = assets_dir / name
        actual = _sha256(path) if path.is_file() else None
        check(
            f"Checksum {name}",
            actual == checksum_records.get(name),
            {"expected": checksum_records.get(name), "actual": actual},
        )

    metadata_digests = {
        str(item.get("name")): str(item.get("digest") or "")
        for item in asset_rows
        if isinstance(item, dict) and item.get("digest")
    }
    for name, value in sorted(metadata_digests.items()):
        expected = value.removeprefix("sha256:")
        check(f"GitHub asset digest {name}", _sha256(assets_dir / name) == expected, value)

    wheel = assets_dir / f"neuroai_workbench-{version}-py3-none-any.whl"
    sdist = assets_dir / f"neuroai_workbench-{version}.tar.gz"
    try:
        wheel_metadata = _wheel_metadata(wheel)
        wheel_error = None
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        wheel_metadata = {}
        wheel_error = str(exc)
    check("Wheel structure and metadata readable", wheel_error is None, wheel_error or wheel_metadata)
    check(
        "Wheel identity",
        wheel_metadata == {"name": "neuroai-workbench", "version": version},
        wheel_metadata,
    )
    try:
        sdist_metadata = _sdist_metadata(sdist)
        sdist_error = None
    except (OSError, ValueError, tarfile.TarError) as exc:
        sdist_metadata = {}
        sdist_error = str(exc)
    check("Source distribution structure and metadata readable", sdist_error is None, sdist_error or sdist_metadata)
    check(
        "Source distribution identity",
        sdist_metadata == {"name": "neuroai-workbench", "version": version},
        sdist_metadata,
    )

    verification_path = assets_dir / "RELEASE_VERIFICATION.json"
    try:
        verification = _load_object(verification_path, "release verification report")
        verification_error = None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        verification = {}
        verification_error = str(exc)
    check("Release verification report parses", verification_error is None, verification_error or "parsed")
    check("Release verification tag", verification.get("release") == expected_tag, verification.get("release"))
    check(
        "Release verification checks all pass",
        isinstance(verification.get("checks_total"), int)
        and verification.get("checks_total") == verification.get("checks_passed")
        and verification.get("checks_failed") == 0,
        {
            "total": verification.get("checks_total"),
            "passed": verification.get("checks_passed"),
            "failed": verification.get("checks_failed"),
        },
    )
    withheld = verification.get("withheld_claims")
    check(
        "Release verification preserves withheld claims",
        isinstance(withheld, list) and set(map(str, withheld)) == EXPECTED_WITHHELD_CLAIMS,
        withheld,
    )

    sbom_path = assets_dir / "sbom.cdx.json"
    try:
        sbom = _load_object(sbom_path, "CycloneDX SBOM")
        sbom_error = None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sbom = {}
        sbom_error = str(exc)
    components = sbom.get("components")
    check("CycloneDX SBOM parses", sbom_error is None, sbom_error or "parsed")
    check("CycloneDX format identity", sbom.get("bomFormat") == "CycloneDX", sbom.get("bomFormat"))
    check(
        "CycloneDX component inventory is non-empty",
        isinstance(components, list) and len(components) > 0,
        len(components) if isinstance(components, list) else None,
    )

    tag_commit = str(tag_record.get("tag_commit") or "")
    check("Repository tag identity", tag_record.get("tag") == expected_tag, tag_record)
    check("Repository tag peels to expected commit", tag_commit == expected_commit, tag_commit)
    bundle = assets_dir / f"neuroai-workbench-{expected_tag}.bundle"
    bundle_valid, bundle_commit, bundle_detail = _bundle_commit(bundle, expected_tag)
    check("Git bundle verifies", bundle_valid, bundle_detail)
    check("Git bundle tag peels to expected commit", bundle_commit == expected_commit, bundle_commit)

    attestation_rows = attestations.get("assets")
    attestation_map = (
        {str(item.get("name")): bool(item.get("verified")) for item in attestation_rows if isinstance(item, dict)}
        if isinstance(attestation_rows, list)
        else {}
    )
    check("Attestation result inventory", set(attestation_map) == expected_assets, sorted(attestation_map))
    for name in sorted(expected_assets):
        check(f"Build provenance attestation {name}", attestation_map.get(name) is True, attestation_map.get(name))

    body = str(release.get("body") or "")
    for phrase in _RELEASE_NOTE_BOUNDARIES:
        check(f"Release notes preserve boundary: {phrase}", phrase.lower() in body.lower(), phrase)

    failed = [item for item in checks if item["status"] == "FAIL"]
    return {
        "schema_version": 1,
        "release": expected_tag,
        "expected_commit": expected_commit,
        "observed_release_state": "DRAFT" if release.get("isDraft") else "PUBLISHED",
        "release_url": release.get("url"),
        "asset_count": len(asset_names),
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "boundary": (
            "This audit verifies acquired bytes, package metadata, checksums, bundle identity, SBOM structure, "
            "release-verification claims, release-note boundaries, and recorded GitHub attestations. It does not "
            "establish scientific validity, clinical safety, regulatory authorization, conformance, institutional "
            "endorsement, official UNESCO status, source authenticity, or lawful evidence custody."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--release-json", type=Path, required=True)
    parser.add_argument("--tag-json", type=Path, required=True)
    parser.add_argument("--attestations-json", type=Path, required=True)
    parser.add_argument("--expected-tag", default="v0.2.1")
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--require-published", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        report = audit(
            assets_dir=args.assets_dir.resolve(),
            release=_load_object(args.release_json, "release metadata"),
            tag_record=_load_object(args.tag_json, "tag verification"),
            attestations=_load_object(args.attestations_json, "attestation results"),
            expected_tag=args.expected_tag,
            expected_commit=args.expected_commit,
            require_published=args.require_published,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        report = {
            "schema_version": 1,
            "release": args.expected_tag,
            "expected_commit": args.expected_commit,
            "status": "FAIL",
            "checks_total": 1,
            "checks_passed": 0,
            "checks_failed": 1,
            "checks": [{"name": "Audit execution", "status": "FAIL", "detail": str(exc)}],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({key: report.get(key) for key in ("release", "status", "checks_total", "checks_failed")}, indent=2)
    )
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
