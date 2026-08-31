#!/usr/bin/env python3
"""Offline reference flow: discovery -> proposal -> adjudication -> release-candidate.

No network. Mechanical PASS is not release authorization.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from neuroai_workbench.discovery import (  # noqa: E402
    adjudicate_candidate_source,
    initialize_discovery_workspace,
    load_programme,
    run_source_universe,
    seed_fixture_queries,
)
from neuroai_workbench.observatory_graph import build_entity, build_source  # noqa: E402
from neuroai_workbench.release import ReleaseCompiler  # noqa: E402

FLOW_BOUNDARY = (
    "This offline reference flow emits candidates, human-gated adjudications, and a "
    "mechanical release candidate. It does not authorize publication, mutate assessments, "
    "or claim institutional readiness."
)


def _su_pubs_pages() -> list[dict]:
    return [
        {
            "payload": {
                "total_count": 2,
                "next_page_token": None,
                "records": [
                    {
                        "identity": "10.1000/neuroai.fixture.1",
                        "title": "Synthetic NeuroAI publication fixture",
                        "url": "https://doi.org/10.1000/neuroai.fixture.1",
                    },
                    {
                        "identity": "PMID:99999999",
                        "title": "Synthetic PMID fixture",
                        "url": "https://pubmed.ncbi.nlm.nih.gov/99999999/",
                    },
                ],
            }
        }
    ]


def run_offline_reference_flow(output_dir: Path) -> dict:
    workspace = output_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    initialize_discovery_workspace(workspace)
    seed_fixture_queries(workspace)

    programme = load_programme("SU-PUBS")
    discovery = run_source_universe(
        programme=programme,
        execution_mode="OFFLINE_FIXTURE",
        pages=_su_pubs_pages(),
        workspace=workspace,
        actor="offline-reference",
    )
    workflow = discovery["workflow"]
    assert workflow is not None
    proposals = workflow["proposals"]
    adjudications = []
    for proposal in proposals:
        if proposal.get("status") != "PENDING_HUMAN_ACCEPTANCE":
            continue
        adjudications.append(
            adjudicate_candidate_source(
                workspace,
                proposal["proposal_id"],
                "ACCEPT",
                rationale="Offline reference acceptance of synthetic fixture candidate.",
                actor="offline-reference",
            )
        )

    entity = build_entity(
        entity_id="ENT-OFFLINE-REF-1",
        entity_type="ORGANIZATION",
        canonical_label="Offline Reference Org",
    )
    source = build_source(
        source_id="SRC-OFFLINE-REF-1",
        source_class="REGISTRY",
        title="Offline reference source",
        publisher="Synthetic",
        canonical_url_or_reference="https://example.test/offline-reference",
    )
    candidate_dir = output_dir / "release-candidate"
    compiled = ReleaseCompiler().build(
        [entity, source],
        candidate_dir,
        candidate_id="CAND-OFFLINE-REF-1",
    )
    result = {
        "universe_id": discovery["programme"]["universe_id"],
        "maturity": discovery["programme"]["maturity"],
        "candidate_count": discovery["coverage"]["included_candidate_count"],
        "proposal_count": len(proposals),
        "adjudication_count": len(adjudications),
        "release_candidate_dir": str(candidate_dir),
        "mechanical_verification": compiled["verification"].get("mechanical_verification"),
        "release_authorized": compiled["descriptor"].get("release_authorized", False),
        "s2_mutated": False,
        "network_used": False,
        "boundary": FLOW_BOUNDARY,
    }
    (output_dir / "flow-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for workspace and release candidate (default: temp dir)",
    )
    args = parser.parse_args()
    if args.output_dir is None:
        with tempfile.TemporaryDirectory(prefix="neuroai-offline-flow-") as raw:
            result = run_offline_reference_flow(Path(raw))
            print(json.dumps(result, indent=2, sort_keys=True))
            print(
                "Note: temp output removed after process exit; pass --output-dir to retain artifacts.",
                file=sys.stderr,
            )
    else:
        result = run_offline_reference_flow(args.output_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("release_authorized") is True:
        print("ERROR: offline flow must not set release_authorized=true", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
