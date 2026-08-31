from __future__ import annotations

from pathlib import Path

from neuroai_workbench.collector import PriorCapture
from neuroai_workbench.util import sha256_bytes
from tests.unit.test_collector_http import FakeTransport, _collector
from tests.unit.test_collector_schemas import valid_collection_request


def test_successful_collection_outcome_exposes_persisted_quarantine_record(tmp_path: Path) -> None:
    body = b'{"protocolSection":{"identificationModule":{"nctId":"NCT03333954"}}}'
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                200,
                {"Content-Type": "application/json"},
                body,
            )
        }
    )
    collector = _collector(tmp_path, transport)
    outcome = collector.collect(valid_collection_request())
    assert outcome.kind == "result"
    assert outcome.quarantine_record is not None
    record = outcome.quarantine_record
    assert record["result_id"] == outcome.record["result_id"]
    assert record["source_id"] == outcome.record["source_id"]
    assert record["monitor_id"] == outcome.record["monitor_id"]
    assert record["sha256"] == outcome.record["sha256"]
    assert record["quarantine_path"] == outcome.record["quarantine_path"]
    assert record["approval_state"] == "PENDING_HUMAN_APPROVAL"
    stored = tmp_path / "quarantine" / "records" / f"{record['quarantine_id']}.json"
    assert stored.is_file()


def test_not_modified_collection_outcome_exposes_new_quarantine_record(tmp_path: Path) -> None:
    prior_body = b"prior"
    prior_hash = sha256_bytes(prior_body)
    prior_path = f"incoming/SRC-0001/{prior_hash[:12]}/source.html"
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                304,
                {"ETag": '"same"'},
                b"",
            )
        }
    )
    collector = _collector(tmp_path, transport)
    prior = PriorCapture(
        etag='"same"',
        content_sha256=prior_hash,
        quarantine_path=prior_path,
        size_bytes=len(prior_body),
        media_type="text/html",
        original_filename="source.html",
    )
    outcome = collector.collect(valid_collection_request(), prior_capture=prior)
    assert outcome.kind == "result"
    assert outcome.record["http_status"] == 304
    assert outcome.quarantine_record is not None
    assert outcome.quarantine_record["result_id"] == outcome.record["result_id"]
    assert outcome.quarantine_record["approval_state"] == "PENDING_HUMAN_APPROVAL"


def test_failure_collection_outcome_has_no_quarantine_record(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={
            "https://example.org/source": (
                500,
                {"Content-Type": "text/plain"},
                b"failed",
            )
        }
    )
    collector = _collector(tmp_path, transport)
    outcome = collector.collect(valid_collection_request())
    assert outcome.kind == "failure"
    assert outcome.quarantine_record is None
