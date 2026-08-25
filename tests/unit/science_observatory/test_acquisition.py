from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from neuroai_workbench.science_observatory import acquisition
from neuroai_workbench.science_observatory.http_transport import HttpResult
from neuroai_workbench.science_observatory.query_compiler import compile_from_paths
from neuroai_workbench.science_observatory.source_contracts import EXPECTED_FROZEN_USER_AGENT

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "science_observatory" / "external_s2"
PROTOCOL = FIXTURES / "discovery-protocol-v0.1.json"
COMPILATION = FIXTURES / "query-compilation-v0.2.json"


class FakeTransport:
    def __init__(self, responses, *, user_agent: str | None = None):
        self.responses = list(responses)
        self.urls: list[str] = []
        if user_agent is not None:
            self.user_agent = user_agent

    def fetch(self, url: str) -> HttpResult:
        self.urls.append(url)
        if not self.responses:
            raise RuntimeError("unexpected transport call")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, payload, headers = item
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        return HttpResult(status=status, headers=headers, body=body)


class Clock:
    def __init__(self) -> None:
        self.second = 0

    def __call__(self) -> str:
        value = f"2026-08-25T04:00:{self.second:02d}Z"
        self.second += 1
        return value


def frozen_plan() -> dict:
    return compile_from_paths(PROTOCOL, COMPILATION)


def provider_unit(provider: str) -> dict:
    plan = frozen_plan()
    unit = deepcopy(next(row for row in plan["query_units"] if row["provider"] == provider))
    unit["evidence_cutoff"] = plan["evidence_cutoff"]
    return unit


def crossref_response(*, total: int = 1, doi: str = "10.1/a", title: str = "A", next_cursor="done"):
    return (
        200,
        {
            "message": {
                "total-results": total,
                "items": [{"DOI": doi, "title": [title]}],
                "next-cursor": next_cursor,
            }
        },
        {"content-type": "application/json"},
    )


def epmc_response(*, total: int = 1, record: dict | None = None, next_cursor="done"):
    if record is None:
        record = {
            "source": "MED",
            "id": "123",
            "doi": "10.1/b",
            "title": "B",
            "pubYear": "2015",
        }
    return (
        200,
        {
            "hitCount": total,
            "nextCursorMark": next_cursor,
            "resultList": {"result": [record]},
        },
        {"content-type": "application/json"},
    )


def test_current_frozen_plan_integrity_is_accepted() -> None:
    by_id = acquisition.validate_plan_integrity(frozen_plan())
    assert len(by_id) == 768


def test_crossref_complete_two_page_query_unit(tmp_path: Path) -> None:
    responses = [
        (
            200,
            {
                "message": {
                    "total-results": 2,
                    "items": [
                        {
                            "DOI": "10.1234/A",
                            "title": ["First"],
                            "published": {"date-parts": [[2015, 2, 3]]},
                        }
                    ],
                    "next-cursor": "cursor-2",
                }
            },
            {"content-type": "application/json"},
        ),
        (
            200,
            {
                "message": {
                    "total-results": 2,
                    "items": [
                        {
                            "DOI": "10.1234/B",
                            "title": ["Second"],
                            "published": {"date-parts": [[2015]]},
                        }
                    ],
                    "next-cursor": "cursor-3",
                }
            },
            {"content-type": "application/json"},
        ),
    ]
    result = acquisition.acquire_query_unit(
        provider_unit("CROSSREF"),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport(responses),
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )

    assert result["status"] == "COMPLETE"
    assert result["candidate_count"] == result["provider_total"] == 2
    assert result["coverage_state"] == "ISSUED_COMPLETE_QUERY_UNIT"
    assert result["coverage"]["rates"]["discovery"] == 1.0
    assert result["freeze"]["retrieval_cutoff"] == "2026-08-20T00:00:00Z"
    candidates = list(acquisition._load_jsonl(tmp_path / result["candidates_path"]))
    assert [row["identifiers"]["doi"] for row in candidates] == ["10.1234/a", "10.1234/b"]
    assert [row["publication_date"] for row in candidates] == ["2015-02-03", "2015"]
    assert len(list((tmp_path / "raw" / "sha256").rglob("*.json"))) == 2
    assert result["page_manifest"][0]["requested_at"] < result["page_manifest"][0]["observed_at"]
    assert result["release_eligibility"] == acquisition.RELEASE_INELIGIBLE


def test_europe_pmc_identity_is_source_aware(tmp_path: Path) -> None:
    record = {
        "source": "med",
        "id": "123456",
        "doi": "https://doi.org/10.5555/ABC",
        "pmid": "123456",
        "pmcid": "pmc999",
        "title": "Example",
        "pubYear": "2015",
    }
    result = acquisition.acquire_query_unit(
        provider_unit("EUROPE_PMC"),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([epmc_response(record=record)]),
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    candidate = next(acquisition._load_jsonl(tmp_path / result["candidates_path"]))

    assert result["status"] == "COMPLETE"
    assert candidate["provider_record_source"] == "MED"
    assert candidate["provider_record_id"] == "123456"
    assert candidate["identifiers"] == {
        "doi": "10.5555/abc",
        "pmid": "123456",
        "pmcid": "PMC999",
        "openalex": None,
    }
    assert candidate["selection_state"] == "DISCOVERED_CANDIDATE"
    assert candidate["canonical_effect"] == "NONE_REQUIRES_RELEVANCE_ADJUDICATION"


def test_europe_pmc_same_bare_id_different_sources_remain_distinct(tmp_path: Path) -> None:
    records = [
        {"source": "MED", "id": "123", "title": "Published record", "pubYear": "2015"},
        {"source": "PPR", "id": "123", "title": "Preprint record", "pubYear": "2015"},
    ]
    response = (
        200,
        {"hitCount": 2, "nextCursorMark": "done", "resultList": {"result": records}},
        {},
    )
    result = acquisition.acquire_query_unit(
        provider_unit("EUROPE_PMC"),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([response]),
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    candidates = list(acquisition._load_jsonl(tmp_path / result["candidates_path"]))

    assert {(row["provider_record_source"], row["provider_record_id"]) for row in candidates} == {
        ("MED", "123"),
        ("PPR", "123"),
    }
    assert len({row["candidate_id"] for row in candidates}) == 2


def test_missing_europe_pmc_source_fails_closed_without_coverage(tmp_path: Path) -> None:
    record = {"id": "123", "title": "Missing source", "pubYear": "2015"}
    result = acquisition.acquire_query_unit(
        provider_unit("EUROPE_PMC"),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([epmc_response(record=record)]),
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )

    assert result["status"] == "PARTIAL"
    assert "provider source database code" in result["freeze"]["failure_reason"]
    assert result["coverage"] is None


def test_cursor_stall_is_partial_and_coverage_is_not_issued(tmp_path: Path) -> None:
    response = (
        200,
        {
            "message": {
                "total-results": 2,
                "items": [{"DOI": "10.1/a", "title": ["A"]}],
                "next-cursor": "*",
            }
        },
        {},
    )
    result = acquisition.acquire_query_unit(
        provider_unit("CROSSREF"),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([response]),
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )

    assert result["status"] == "PARTIAL"
    assert result["freeze"]["failure_reason"] == "CURSOR_DID_NOT_ADVANCE_BEFORE_PROVIDER_TOTAL"
    assert result["coverage"] is None
    assert result["coverage_state"] == "NOT_ISSUED_INCOMPLETE_QUERY_UNIT"


def test_provider_total_change_is_partial(tmp_path: Path) -> None:
    responses = [
        (
            200,
            {
                "message": {
                    "total-results": 3,
                    "items": [{"DOI": "10.1/a", "title": ["A"]}],
                    "next-cursor": "c2",
                }
            },
            {},
        ),
        (
            200,
            {
                "message": {
                    "total-results": 4,
                    "items": [{"DOI": "10.1/b", "title": ["B"]}],
                    "next-cursor": "c3",
                }
            },
            {},
        ),
    ]
    result = acquisition.acquire_query_unit(
        provider_unit("CROSSREF"),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport(responses),
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    assert result["status"] == "PARTIAL"
    assert result["freeze"]["failure_reason"] == "PROVIDER_TOTAL_CHANGED_DURING_TRAVERSAL"


def test_transient_http_retry_then_success() -> None:
    transport = FakeTransport(
        [
            (429, {"error": "rate"}, {"retry-after": "0"}),
            (200, {"ok": True}, {}),
        ]
    )
    sleeps: list[float] = []
    result = acquisition.fetch_with_retries(
        transport,
        "https://example.invalid/test",
        max_attempts=2,
        sleep_fn=sleeps.append,
    )

    assert result.status == 200
    assert sleeps == [0.0]
    assert len(transport.urls) == 2


def test_scoped_plan_cannot_claim_full_plan_completion(tmp_path: Path) -> None:
    manifest = acquisition.acquire_plan(
        frozen_plan(),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([crossref_response()]),
        max_units=1,
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )

    assert manifest["complete_query_units"] == 1
    assert manifest["selected_is_full_plan"] is False
    assert manifest["full_plan_complete"] is False
    assert manifest["status"] == "PARTIAL_OR_SCOPED_ACQUISITION"
    assert manifest["canonical_effect"] == "NONE_CANDIDATE_DISCOVERY_ONLY"


def test_exact_doi_dedup_is_candidate_only(tmp_path: Path) -> None:
    plan = frozen_plan()
    crossref = next(unit for unit in plan["query_units"] if unit["provider"] == "CROSSREF")
    epmc = next(unit for unit in plan["query_units"] if unit["provider"] == "EUROPE_PMC")
    manifest = acquisition.acquire_plan(
        plan,
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport(
            [
                crossref_response(doi="10.1/shared", title="Shared"),
                epmc_response(
                    record={
                        "source": "MED",
                        "id": "123",
                        "doi": "10.1/shared",
                        "title": "Shared",
                        "pubYear": "2015",
                    }
                ),
            ]
        ),
        query_unit_ids={crossref["query_unit_id"], epmc["query_unit_id"]},
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    report = json.loads((tmp_path / "dedup-report.json").read_text(encoding="utf-8"))
    doi_groups = report["duplicate_identifier_groups"]["DOI"]

    assert manifest["full_plan_complete"] is False
    assert len(doi_groups) == 1
    assert doi_groups[0]["normalized_identifier"] == "10.1/shared"
    assert doi_groups[0]["candidate_count"] == 2
    assert report["canonical_merge_performed"] is False
    assert report["fuzzy_matching_performed"] is False


def test_internally_rehashed_subset_cannot_impersonate_frozen_full_plan() -> None:
    plan = frozen_plan()
    mutated = deepcopy(plan)
    mutated["query_units"] = mutated["query_units"][:2]
    mutated["unit_count"] = 2
    mutated["provider_counts"] = {"CROSSREF": 2, "EUROPE_PMC": 0}
    mutated["plan_sha256"] = acquisition._sha256_json(acquisition._plan_basis(mutated))
    mutated["plan_id"] = f"SCIENCE-QUERY-PLAN-{mutated['plan_sha256'][:20].upper()}"

    with pytest.raises(ValueError, match="does not match the current Phase 4 v0.2 plan identity"):
        acquisition.validate_plan_integrity(mutated)


def test_unknown_query_unit_selection_fails_instead_of_silently_dropping(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown ids"):
        acquisition.acquire_plan(
            frozen_plan(),
            output_root=tmp_path,
            repository_root=ROOT,
            transport=FakeTransport([]),
            query_unit_ids={"QUNIT-CROSSREF-NOTDECLARED"},
            sleep_fn=lambda _: None,
            clock_fn=Clock(),
        )


def test_complete_result_tampering_blocks_resume_before_network(tmp_path: Path) -> None:
    first = acquisition.acquire_plan(
        frozen_plan(),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([crossref_response()]),
        max_units=1,
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    result_path = tmp_path / first["query_unit_result_paths"][0]
    result = json.loads(result_path.read_text(encoding="utf-8"))
    candidate_path = tmp_path / result["candidates_path"]
    candidate_path.write_text(candidate_path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

    transport = FakeTransport([])
    with pytest.raises(ValueError, match="candidate file digest mismatch"):
        acquisition.acquire_plan(
            frozen_plan(),
            output_root=tmp_path,
            repository_root=ROOT,
            transport=transport,
            max_units=1,
            sleep_fn=lambda _: None,
            clock_fn=Clock(),
        )
    assert transport.urls == []


def test_incomplete_attempt_is_archived_before_clean_retry(tmp_path: Path) -> None:
    partial_response = (
        200,
        {
            "message": {
                "total-results": 2,
                "items": [{"DOI": "10.1/a", "title": ["A"]}],
                "next-cursor": "*",
            }
        },
        {},
    )
    first = acquisition.acquire_plan(
        frozen_plan(),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([partial_response]),
        max_units=1,
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    assert first["partial_query_units"] == 1

    second = acquisition.acquire_plan(
        frozen_plan(),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([crossref_response()]),
        max_units=1,
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    archives = list((tmp_path / "units").rglob("attempt.json"))
    archived = json.loads(archives[0].read_text(encoding="utf-8"))

    assert second["complete_query_units"] == 1
    assert len(archives) == 1
    assert archived["archived_status"] == "PARTIAL"
    assert (tmp_path / archived["candidate_snapshot_path"]).is_file()
    assert (tmp_path / "runs" / first["run_id"] / "run-manifest.json").is_file()


def test_transport_user_agent_drift_is_rejected_before_network(tmp_path: Path) -> None:
    transport = FakeTransport([], user_agent="different-client")
    with pytest.raises(ValueError, match="User-Agent differs"):
        acquisition.acquire_plan(
            frozen_plan(),
            output_root=tmp_path,
            repository_root=ROOT,
            transport=transport,
            max_units=1,
            sleep_fn=lambda _: None,
            clock_fn=Clock(),
        )
    assert transport.urls == []


def test_frozen_transport_user_agent_is_accepted(tmp_path: Path) -> None:
    manifest = acquisition.acquire_plan(
        frozen_plan(),
        output_root=tmp_path,
        repository_root=ROOT,
        transport=FakeTransport([crossref_response()], user_agent=EXPECTED_FROZEN_USER_AGENT),
        max_units=1,
        sleep_fn=lambda _: None,
        clock_fn=Clock(),
    )
    assert manifest["complete_query_units"] == 1


def test_repository_output_is_rejected() -> None:
    with pytest.raises(ValueError, match="outside the Git repository"):
        acquisition.validate_output_root(ROOT / "acquisition-output", repository_root=ROOT)
