from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from .. import __version__
from ..migration_ops.constants import OPS_WORKSPACE_ENV
from ..util import atomic_write_json, sha256_file, utc_now

WORKBENCH_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCAFFOLD = WORKBENCH_ROOT / "templates" / "neuroai-observatory-data"
DEFAULT_FIXTURES = DEFAULT_SCAFFOLD / "fixtures"
APPROVED_SYNTHETIC_FIXTURES = (
    "synthetic_source_registry.json",
    "synthetic_disposition_summary.json",
)

# Authorized public redistribution set for the first real data release (bytes from ops extract).
AUTHORIZED_PUBLIC_RELEASE_SET = "public-governing-v1"
AUTHORIZED_PUBLIC_OPS_FILES: tuple[tuple[str, str], ...] = (
    ("01_CONFIG/source_monitor_registry_v1.5.json", "source_monitor_registry_v1.5.json"),
    (
        "05_RELEASES/historical/CANONICAL_EVIDENCE_DEPTH_AND_OBSERVATORY_RELEASE_v1.4.json",
        "canonical_observatory_release_v1.4.json",
    ),
    (
        "05_RELEASES/historical/CANONICAL_LIVE_REFRESH_RELEASE_v1.6.json",
        "canonical_live_refresh_release_v1.6.json",
    ),
    ("05_RELEASES/historical/ADJUDICATED_DELTA_v1.6.json", "adjudicated_delta_v1.6.json"),
    (
        "05_RELEASES/current/CANONICAL_SUCCESSOR_SNAPSHOT_v1.7.json",
        "canonical_successor_snapshot_v1.7.json",
    ),
)

DEFAULT_WITHHELD_CLAIMS = (
    "No regulatory authorization",
    "No clinical effectiveness or safety conclusion",
    "No system conformance determination",
    "No UNESCO endorsement or institutional authority",
    "No protected-evidence completeness claim",
)


@dataclass(frozen=True)
class PublishPlan:
    release_tag: str
    source_fixtures: tuple[Path, ...]
    staging_root: Path
    manifest_path: Path
    descriptor_path: Path
    dry_run: bool
    withheld_claims: tuple[str, ...]
    release_set: str
    workbench_commit: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_tag": self.release_tag,
            "release_set": self.release_set,
            "source_fixtures": [str(path) for path in self.source_fixtures],
            "staging_root": str(self.staging_root),
            "manifest_path": str(self.manifest_path),
            "descriptor_path": str(self.descriptor_path),
            "dry_run": self.dry_run,
            "withheld_claims": list(self.withheld_claims),
            "workbench_commit": self.workbench_commit,
            "boundary": (
                "Publish planning copies authorized public records only; "
                "it does not establish scientific truth, regulatory authorization, or release authority."
            ),
        }


def resolve_data_repo_root(path: Path | None) -> Path:
    if path is not None:
        candidate = path.resolve()
        if not candidate.is_dir():
            raise ValueError(f"data repository root is not a directory: {candidate}")
        return candidate
    if DEFAULT_SCAFFOLD.is_dir():
        return DEFAULT_SCAFFOLD.resolve()
    raise ValueError(
        "No neuroai-observatory-data root found. Provide --target or initialize "
        "templates/neuroai-observatory-data from the workbench scaffold."
    )


def _load_script_module(name: str, script: Path) -> ModuleType:
    if not script.is_file():
        raise FileNotFoundError(f"{script.name} not found under {script.parent}")
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {script.name} from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workbench_commit_pin(repo_root: Path | None = None) -> str | None:
    root = repo_root or WORKBENCH_ROOT
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def materialize_authorized_public_fixtures(
    output_dir: Path,
    *,
    ops_workspace: Path | None = None,
) -> list[Path]:
    """Copy authorized public governing JSON from ops workspace into output_dir."""
    root = ops_workspace
    if root is None:
        env = os.environ.get(OPS_WORKSPACE_ENV, "").strip()
        root = Path(env) if env else None
    if root is None or not root.is_dir():
        raise FileNotFoundError(
            f"Authorized public release set requires {OPS_WORKSPACE_ENV} pointing at the Operations Starter extract."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for rel, dest_name in AUTHORIZED_PUBLIC_OPS_FILES:
        source = root / rel
        if not source.is_file():
            raise FileNotFoundError(f"Authorized public source missing: {source}")
        target = output_dir / dest_name
        shutil.copy2(source, target)
        written.append(target)
    # Public disposition summary (metadata only; no protected evidence).
    summary = {
        "schema_version": "1.0",
        "title": "Public migration disposition summary",
        "release_set": AUTHORIZED_PUBLIC_RELEASE_SET,
        "human_disposition": "ACCEPTED_WITH_RESIDUALS",
        "residuals": ["AMB-003"],
        "ambiguities": {
            "AMB-001": "RESOLVED_OPS_DIGEST_VERIFIED",
            "AMB-002": "RESOLVED_OPS_DIGEST_VERIFIED",
            "AMB-003": "INACCESSIBLE",
            "AMB-004": "RESOLVED_REPO_EXISTS",
        },
        "withheld_claims": list(DEFAULT_WITHHELD_CLAIMS),
        "boundary": (
            "Disposition summary records migration closure state only; "
            "it does not establish substantive observatory truth or institutional authority."
        ),
    }
    summary_path = output_dir / "public_disposition_summary.json"
    atomic_write_json(summary_path, summary)
    written.append(summary_path)
    return written


def build_publish_plan(
    *,
    release_tag: str,
    staging_root: Path,
    target: Path | None = None,
    fixture_dir: Path | None = None,
    dry_run: bool = False,
    release_set: str = "synthetic",
    ops_workspace: Path | None = None,
) -> PublishPlan:
    resolve_data_repo_root(target)
    if release_set == AUTHORIZED_PUBLIC_RELEASE_SET:
        fixtures = (fixture_dir or (staging_root / "_authorized_fixtures")).resolve()
        if fixture_dir is None or not any(fixtures.glob("*.json")):
            materialize_authorized_public_fixtures(fixtures, ops_workspace=ops_workspace)
        source_fixtures = tuple(sorted(fixtures.glob("*.json")))
        if not source_fixtures:
            raise FileNotFoundError(f"Authorized public fixtures missing under {fixtures}")
    else:
        fixtures = (fixture_dir or DEFAULT_FIXTURES).resolve()
        missing = [name for name in APPROVED_SYNTHETIC_FIXTURES if not (fixtures / name).is_file()]
        if missing:
            raise FileNotFoundError(f"Approved synthetic fixtures missing under {fixtures}: {', '.join(missing)}")
        source_fixtures = tuple(fixtures / name for name in APPROVED_SYNTHETIC_FIXTURES)

    release_dir = staging_root / "releases" / release_tag
    return PublishPlan(
        release_tag=release_tag,
        source_fixtures=source_fixtures,
        staging_root=staging_root.resolve(),
        manifest_path=release_dir / "SHA256SUMS.txt",
        descriptor_path=release_dir / "release-descriptor.json",
        dry_run=dry_run,
        withheld_claims=DEFAULT_WITHHELD_CLAIMS,
        release_set=release_set,
        workbench_commit=_workbench_commit_pin(),
    )


def _fixture_output_dir(plan: PublishPlan) -> Path:
    if plan.release_set == AUTHORIZED_PUBLIC_RELEASE_SET:
        return plan.staging_root / "releases" / plan.release_tag / "records"
    return plan.staging_root / "fixtures"


def _copy_approved_fixtures(plan: PublishPlan) -> Path:
    fixtures_dir = _fixture_output_dir(plan)
    if not plan.dry_run:
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        for source in plan.source_fixtures:
            shutil.copy2(source, fixtures_dir / source.name)
        # Mirror authorized public records into top-level fixtures for discovery without mixing synthetics.
        if plan.release_set == AUTHORIZED_PUBLIC_RELEASE_SET:
            mirror = plan.staging_root / "fixtures"
            mirror.mkdir(parents=True, exist_ok=True)
            for source in plan.source_fixtures:
                shutil.copy2(source, mirror / source.name)
    return fixtures_dir


def _render_descriptor(plan: PublishPlan, manifest_sha256: str, record_counts: dict[str, int]) -> dict[str, Any]:
    notes = (
        "Authorized public governing records copied from Operations Starter via workbench publish pipeline."
        if plan.release_set == AUTHORIZED_PUBLIC_RELEASE_SET
        else "Synthetic public fixtures copied from workbench publish pipeline; manifest identity only."
    )
    return {
        "release_id": f"OBS-DATA-{utc_now()[:10].replace('-', '')}-{plan.release_tag.upper()}",
        "release_tag": plan.release_tag,
        "release_set": plan.release_set,
        "published_at": utc_now(),
        "workbench_version": __version__,
        "workbench_commit": plan.workbench_commit,
        "manifest_path": f"releases/{plan.release_tag}/SHA256SUMS.txt",
        "manifest_sha256": manifest_sha256,
        "record_counts": record_counts,
        "notes": notes,
        "withheld_claims": list(plan.withheld_claims),
    }


def _manifest_for_tree(repo_root: Path, fixtures_dir: Path, manifest_path: Path) -> str:
    generate = _load_script_module("observatory_generate_manifest", repo_root / "scripts" / "generate_manifest.py")
    return cast(str, generate.render_manifest(fixtures_dir, exclude={manifest_path.resolve()}))


def _verify_manifest(repo_root: Path, fixtures_dir: Path, manifest_path: Path) -> tuple[bool, list[str]]:
    verify = _load_script_module("observatory_verify_manifest", repo_root / "scripts" / "verify_manifest.py")
    return cast(tuple[bool, list[str]], verify.verify_manifest(fixtures_dir, manifest_path))


def publish_release(plan: PublishPlan, *, target: Path | None = None) -> dict[str, Any]:
    repo_root = resolve_data_repo_root(target)
    fixtures_dir = _copy_approved_fixtures(plan)

    if plan.dry_run:
        with tempfile.TemporaryDirectory(prefix="neuroai-publish-dry-") as tmp:
            temp_root = Path(tmp)
            temp_fixtures = temp_root / "fixtures"
            temp_fixtures.mkdir()
            for source in plan.source_fixtures:
                shutil.copy2(source, temp_fixtures / source.name)
            temp_manifest = temp_root / "SHA256SUMS.txt"
            manifest_text = _manifest_for_tree(repo_root, temp_fixtures, temp_manifest)
            temp_manifest.write_text(manifest_text, encoding="utf-8")
            ok, errors = _verify_manifest(repo_root, temp_fixtures, temp_manifest)
            manifest_sha256 = sha256_file(temp_manifest)
            file_count = 0 if not manifest_text.strip() else len(manifest_text.strip().splitlines())
            byte_total = sum(path.stat().st_size for path in plan.source_fixtures)
            fixture_hashes = {path.name: sha256_file(path) for path in plan.source_fixtures}
    else:
        plan.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_text = _manifest_for_tree(repo_root, fixtures_dir, plan.manifest_path)
        plan.manifest_path.write_text(manifest_text, encoding="utf-8")
        ok, errors = _verify_manifest(repo_root, fixtures_dir, plan.manifest_path)
        manifest_sha256 = sha256_file(plan.manifest_path)
        file_count = 0 if not manifest_text.strip() else len(manifest_text.strip().splitlines())
        byte_total = sum(path.stat().st_size for path in fixtures_dir.rglob("*") if path.is_file())
        fixture_hashes = {path.name: sha256_file(fixtures_dir / path.name) for path in plan.source_fixtures}
        descriptor = _render_descriptor(plan, manifest_sha256, {"files": file_count, "bytes": byte_total})
        atomic_write_json(plan.descriptor_path, descriptor)

    descriptor = _render_descriptor(plan, manifest_sha256, {"files": file_count, "bytes": byte_total})

    return {
        "plan": plan.to_dict(),
        "dry_run": plan.dry_run,
        "manifest_verified": ok,
        "manifest_errors": errors,
        "descriptor": descriptor,
        "fixtures_sha256": fixture_hashes,
        "boundary": (
            "Manifest verification confirms artifact identity only; it does not establish substantive observatory truth."
        ),
    }


def verify_publish_staging(plan: PublishPlan, *, target: Path | None = None) -> dict[str, Any]:
    repo_root = resolve_data_repo_root(target)
    fixtures_dir = _fixture_output_dir(plan)
    if not plan.manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {plan.manifest_path}")

    ok, errors = _verify_manifest(repo_root, fixtures_dir, plan.manifest_path)
    descriptor_ok = True
    descriptor_errors: list[str] = []
    if plan.descriptor_path.is_file():
        descriptor = json.loads(plan.descriptor_path.read_text(encoding="utf-8"))
        manifest_sha256 = sha256_file(plan.manifest_path)
        if descriptor.get("manifest_sha256") != manifest_sha256:
            descriptor_ok = False
            descriptor_errors.append("descriptor manifest_sha256 mismatch")
    else:
        descriptor_ok = False
        descriptor_errors.append("release descriptor missing")

    return {
        "manifest_verified": ok,
        "manifest_errors": errors,
        "descriptor_verified": descriptor_ok,
        "descriptor_errors": descriptor_errors,
        "release_tag": plan.release_tag,
        "staging_root": str(plan.staging_root),
    }
