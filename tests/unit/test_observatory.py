from __future__ import annotations
import json
from pathlib import Path
from neuroai_workbench.observatory import import_release, load_imported_release, load_release, queue_release, summarize_release, validate_release

EXAMPLE = Path(__file__).parents[2] / "examples" / "observatory" / "evidence_depth_release_v1.4.json"

def test_example_validates():
    release=load_release(EXAMPLE); report=validate_release(release)
    assert report["valid"] is True
    assert report["counts"]["organizations"] >= 200

def test_summary_preserves_boundary():
    value=summarize_release(load_release(EXAMPLE))
    assert value["valid"] is True
    assert value["coverage"]["verification_rate"] > 0.9
    assert any("source universes" in x for x in value["boundaries"])

def test_queue_retains_partial_records():
    value=queue_release(load_release(EXAMPLE))
    assert value["counts"]["organizations"] == 3

def test_duplicate_identifier_fails():
    value=load_release(EXAMPLE)
    value["organizations"].append(dict(value["organizations"][0]))
    assert validate_release(value)["valid"] is False

def test_unresolved_source_fails():
    value=load_release(EXAMPLE)
    value["capital_and_ownership_events"][0]["source_ids"]=["MISSING"]
    assert validate_release(value)["valid"] is False

def test_import_round_trip(tmp_path: Path):
    result=import_release(tmp_path,EXAMPLE)
    assert Path(result["target"]).is_dir()
    loaded=load_imported_release(tmp_path,"v1.4")
    assert loaded["metadata"]["version"] == "v1.4"
