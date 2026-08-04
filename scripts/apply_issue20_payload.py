#!/usr/bin/env python3
"""Install the locally validated issue #20 payload under exact integrity checks."""

from __future__ import annotations

import base64
import hashlib
import io
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PART_ROOT = ROOT / ".issue20"
ARCHIVE_SHA256 = "2ab2472de6c244dd19f7880f074974d0042fcd51158cb6477cddcf1e9c5435c9"
EXPECTED_FILES = {
    "src/neuroai_workbench/review.py": "1bd706c1dd6487eb6b5601d4c2cf7506747e24697a389441e2136c7a9bfe1505",
    "src/neuroai_workbench/cli.py": "e1d14e557c1fe26f6ad262841dae300a3a4c6b31573e84c0bf974fa2b2e2cae6",
    "tests/unit/test_review_assignment_transitions.py": "094430155618d43690ebb621b926d1531bba8c40a9ba30beef08ec564d3b4cfa",
    "docs/reference/review.md": "083e27e8528f81cf3bd4317071d81300754f90de9e0e13b17b86feca538eb14c",
    "docs/adr/0011-append-only-review-assignment-lineage.md": "4c4a3488258ccba9e769b14be57c40355a1a68d17c89406a67b5dae65d667f4c",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    observed = text.count(old)
    if observed != 1:
        raise SystemExit(f"{label}: expected one source match, observed {observed}")
    return text.replace(old, new, 1)


def main() -> int:
    parts = sorted(PART_ROOT.glob("payload.part*"))
    if [path.name for path in parts] != [f"payload.part{number:02d}" for number in range(1, 5)]:
        raise SystemExit("issue #20 payload parts are incomplete or unexpected")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in parts)
    archive = base64.b64decode(encoded, validate=True)
    if digest(archive) != ARCHIVE_SHA256:
        raise SystemExit("issue #20 payload archive digest mismatch")

    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            members = bundle.getmembers()
            names = {member.name for member in members}
            if names != set(EXPECTED_FILES):
                raise SystemExit(f"unexpected issue #20 payload members: {sorted(names)}")
            if any(member.isdir() or member.issym() or member.islnk() or Path(member.name).is_absolute() for member in members):
                raise SystemExit("issue #20 payload contains a non-regular or absolute member")
            if any(".." in Path(member.name).parts for member in members):
                raise SystemExit("issue #20 payload contains path traversal")
            bundle.extractall(staging, filter="data")

        for relative, expected in EXPECTED_FILES.items():
            data = (staging / relative).read_bytes()
            if digest(data) != expected:
                raise SystemExit(f"issue #20 file digest mismatch: {relative}")
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    threat_path = ROOT / "THREAT_MODEL.md"
    threat = threat_path.read_text(encoding="utf-8")
    threat = replace_once(
        threat,
        "23. A transaction directory loses its journal and is incorrectly treated as harmless cleanup.\n",
        "23. A transaction directory loses its journal and is incorrectly treated as harmless cleanup.\n"
        "24. A review assignment is silently overwritten, branches into multiple successors, or remains effective after revocation.\n",
        "assignment-lineage threat",
    )
    threat = replace_once(
        threat,
        "- Review-role scope checks, refusal of decision-role self-assignment, and explicit local-identity and authority boundaries (`LOCAL_UNAUTHENTICATED_ATTRIBUTION`).\n",
        "- Review-role scope checks, refusal of decision-role self-assignment, and explicit local-identity and authority boundaries (`LOCAL_UNAUTHENTICATED_ATTRIBUTION`).\n"
        "- Append-only review-assignment lineage with predecessor ID/digest binding, unique-successor and cycle checks, case-lock serialization, effective-state derivation, timestamp-scoped historical authorization, and event-linked supersession/revocation records.\n",
        "assignment-lineage controls",
    )
    threat = replace_once(
        threat,
        "File and directory `fsync` reduce crash windows under the operating-system and filesystem guarantees available to the process. Storage-controller caches, hardware faults, network-filesystem semantics, privileged tampering, and incomplete backup sets remain outside those guarantees.\n\n",
        "File and directory `fsync` reduce crash windows under the operating-system and filesystem guarantees available to the process. Storage-controller caches, hardware faults, network-filesystem semantics, privileged tampering, and incomplete backup sets remain outside those guarantees.\n\n"
        "Review-assignment lineage coordinates cooperative local writers and preserves claimed attribution. It does not authenticate actors, prove institutional delegation, prevent a privileged writer from replacing the complete case tree, or establish that a transition rationale is truthful. Timestamp-scoped authorization depends on the recorded UTC order and event-chain integrity.\n\n",
        "assignment-lineage residual risk",
    )
    threat_path.write_text(threat, encoding="utf-8")

    governance_path = ROOT / "DATA_GOVERNANCE.md"
    governance = governance_path.read_text(encoding="utf-8")
    governance = replace_once(
        governance,
        "Review assignments, statements, disagreements and dispositions are stored as integrity-addressed local records. Reviewer identifiers and roles are claimed workflow metadata; the reference implementation does not authenticate a person, institution, licence, mandate or delegated authority. Review text may contain sensitive interpretations even in the absence of evidence bytes, so institutions must classify, retain, disclose and redact these records deliberately.\n\n",
        "Review assignments, assignment-transition rationales, statements, disagreements and dispositions are stored as integrity-addressed local records. Assignment changes append predecessor-bound `SUPERSEDES` or `REVOKES` records; predecessor files remain immutable, and effective authority is derived from the unique lineage tip. Reviewer identifiers and roles are claimed workflow metadata; the reference implementation does not authenticate a person, institution, licence, mandate or delegated authority. Review and transition text may contain sensitive interpretations, personnel information, availability information, or conflict context even in the absence of evidence bytes, so institutions must classify, retain, disclose and redact these records deliberately.\n\n",
        "assignment-lineage data governance",
    )
    governance_path.write_text(governance, encoding="utf-8")
    print("issue #20 payload installed and verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
