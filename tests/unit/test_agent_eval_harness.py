from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "scripts" / "agent_eval_harness.py"


def test_agent_eval_harness_passes_behavioral_cases() -> None:
    proc = subprocess.run(
        [sys.executable, str(HARNESS), "--json"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    report = json.loads(proc.stdout)
    assert report["passed"] is True
    ids = {case["id"] for case in report["cases"]}
    assert "prohibited_missing_evidence_to_fail_shortcut" in ids
    assert "preserve_not_assessed_semantics" in ids
    assert "network_binding_restrictions" in ids
    assert "event_chain_tampering_detection" in ids
