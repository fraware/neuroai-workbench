from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.collector.adapters.clinicaltrials import ClinicalTrialsGovAdapter
from neuroai_workbench.collector.adapters.fda_device import FdaDeviceAdapter
from neuroai_workbench.collector.adapters.pubmed import PubmedCrossrefAdapter
from neuroai_workbench.collector.adapters.registry import adapter_for_source, build_adapters, resolve_adapter
from neuroai_workbench.collector.adapters.registry_stub import ClinicalRegulatoryHttpCaptureAdapter
from neuroai_workbench.collector.adapters.structured import load_adapter_contract
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.http_client import HttpRequest
from neuroai_workbench.collector.schemas import (
    NORMALIZED_DEVICE_SCHEMA,
    NORMALIZED_PUBLICATION_SCHEMA,
    NORMALIZED_STUDY_SCHEMA,
    STRUCTURED_ADAPTER_CONTRACT_SCHEMA,
    schema_errors,
)
from tests.unit.test_collector_adapters_scheduler import GLOBAL_IP, FakeTransport
from tests.unit.test_collector_schemas import CONFIG_HASH, valid_collection_request

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "collector"

STRUCTURED_ADAPTER_IDS = (
    "clinicaltrials_gov",
    "fda_device",
    "fda_maude",
    "fda_recall",
    "pubmed_crossref",
    "who_ictrp",
    "eu_ctis",
    "neuroscience_archive",
    "patents_grants",
)


def registry_getaddrinfo(host: str, port, *args, **kwargs):
    allowed = {
        "clinicaltrials.gov",
        "www.accessdata.fda.gov",
        "accessdata.fda.gov",
        "api.fda.gov",
        "eutils.ncbi.nlm.nih.gov",
        "pubmed.ncbi.nlm.nih.gov",
        "api.crossref.org",
        "example.org",
    }
    if host.lower().rstrip(".") in allowed or host.endswith(".example.org"):
        return [(2, 1, 6, "", (GLOBAL_IP, 0))]
    raise OSError("unknown host")


def _adapters(tmp_path: Path, transport: FakeTransport) -> dict:
    config = CollectorConfig(
        collector_version="0.3.0.dev0-collector",
        configuration_hash=CONFIG_HASH,
        requests_per_host_per_minute=100,
    )
    return build_adapters(
        config=config,
        transport=transport,
        quarantine_root=tmp_path / "quarantine",
        dns_guard=DnsGuard(getaddrinfo=registry_getaddrinfo),
    )


def test_routing_honesty_stops_substring_trial_surprise(tmp_path: Path) -> None:
    transport = FakeTransport(
        responses={"https://example.org/company-trial-blog": (200, {"content-type": "text/html"}, b"<html>x</html>")}
    )
    adapters = _adapters(tmp_path, transport)
    # Company page mentioning TRIAL in class name must not hit clinicaltrials adapter via substring.
    source = {
        "source_id": "SRC-X",
        "source_class": "OFFICIAL_COMPANY_PAGE",
        "url": "https://example.org/company-trial-blog",
    }
    adapter = adapter_for_source(adapters, source)
    assert adapter.adapter_id == "html"
    assert not ClinicalRegulatoryHttpCaptureAdapter(adapters["html"].collector).supports_source_class(  # type: ignore[attr-defined]
        "OFFICIAL_COMPANY_PAGE"
    )


def test_ctgov_adapter_rewrites_nct_and_fetches_fixture(tmp_path: Path) -> None:
    payload = (FIXTURES / "ctgov_NCT01234567.json").read_bytes()
    api_url = "https://clinicaltrials.gov/api/v2/studies/NCT01234567"
    transport = FakeTransport(responses={api_url: (200, {"content-type": "application/json"}, payload)})
    adapters = _adapters(tmp_path, transport)
    source = {
        "source_id": "SRC-CT",
        "monitor_id": "MON-CT",
        "source_class": "CLINICAL_TRIAL_REGISTRY",
        "url": "https://clinicaltrials.gov/study/NCT01234567",
        "nct_id": "NCT01234567",
    }
    adapter = adapter_for_source(adapters, source)
    assert isinstance(adapter, ClinicalTrialsGovAdapter)
    request = valid_collection_request()
    request["source_id"] = "SRC-CT"
    request["monitor_id"] = "MON-CT"
    request["requested_url"] = source["url"]
    outcome = adapter.collect(request, source_record=source)
    assert outcome.kind == "result"
    assert len(transport.calls) == 1
    assert transport.calls[0].url == api_url
    body = json.loads(payload.decode("utf-8"))
    assert body["protocolSection"]["identificationModule"]["nctId"] == "NCT01234567"


def test_ctgov_search_pagination_and_field_change(tmp_path: Path) -> None:
    page1 = (FIXTURES / "ctgov_search_page1.json").read_bytes()
    page2 = (FIXTURES / "ctgov_search_page2.json").read_bytes()
    study = json.loads((FIXTURES / "ctgov_NCT01234567.json").read_text(encoding="utf-8"))
    adapters = _adapters(tmp_path, FakeTransport())
    adapter = adapters["clinicaltrials_gov"]
    assert isinstance(adapter, ClinicalTrialsGovAdapter)

    url1 = adapter.build_search_url("brain computer interface", page_size=10)
    assert "query.term=brain+computer+interface" in url1 or "query.term=brain%20computer%20interface" in url1
    assert "pageSize=10" in url1
    parsed1 = adapter.parse_search_page(json.loads(page1.decode("utf-8")))
    assert parsed1["has_more"] is True
    assert parsed1["next_page_token"] == "SYNTHETIC_PAGE_2_TOKEN"
    assert len(parsed1["studies"]) == 1

    url2 = adapter.build_search_url(
        "brain computer interface",
        page_size=10,
        page_token="SYNTHETIC_PAGE_2_TOKEN",
    )
    assert "pageToken=SYNTHETIC_PAGE_2_TOKEN" in url2
    parsed2 = adapter.parse_search_page(json.loads(page2.decode("utf-8")))
    assert parsed2["has_more"] is False
    assert parsed2["next_page_token"] is None

    transport = FakeTransport(responses={url1: (200, {"content-type": "application/json"}, page1)})
    adapters = _adapters(tmp_path / "search", transport)
    adapter = adapters["clinicaltrials_gov"]
    assert isinstance(adapter, ClinicalTrialsGovAdapter)
    request = valid_collection_request()
    request["requested_url"] = "https://clinicaltrials.gov/search"
    source = {
        "source_id": "SRC-SEARCH",
        "monitor_id": "MON-SEARCH",
        "source_class": "CLINICAL_TRIAL_REGISTRY",
        "url": request["requested_url"],
        "metadata": {"search_query": "brain computer interface", "page_size": 10},
    }
    outcome = adapter.collect(request, source_record=source)
    assert outcome.kind == "result"
    assert transport.calls[0].url == url1

    normalized = adapter.normalize_study(study)
    assert schema_errors(normalized, NORMALIZED_STUDY_SCHEMA) == []
    assert normalized["nct_id"] == "NCT01234567"
    assert normalized["overall_status"] == "RECRUITING"

    changed_study = json.loads(json.dumps(study))
    changed_study["protocolSection"]["statusModule"]["overallStatus"] = "COMPLETED"
    updated = adapter.normalize_study(changed_study)
    comparison = adapter.compare_normalized_studies(normalized, updated)
    assert comparison["unchanged"] is False
    assert "overall_status" in comparison["changed_fields"]
    assert comparison["prior_aggregate_digest"] != comparison["current_aggregate_digest"]

    same = adapter.compare_normalized_studies(normalized, adapter.normalize_study(study))
    assert same["unchanged"] is True
    assert same["changed_fields"] == []


def test_ctgov_extracts_nct_from_metadata_and_falls_back_without_id(tmp_path: Path) -> None:
    adapters = _adapters(tmp_path, FakeTransport())
    adapter = adapters["clinicaltrials_gov"]
    assert isinstance(adapter, ClinicalTrialsGovAdapter)
    assert (
        adapter.extract_nct_id(
            {"metadata": {"nct_id": "nct99887766"}, "source_class": "CLINICAL_TRIAL_REGISTRY"},
            {"requested_url": "https://example.org/study"},
        )
        == "NCT99887766"
    )
    assert (
        adapter.extract_nct_id({"source_class": "CLINICAL_TRIAL_REGISTRY"}, {"requested_url": "https://example.org/x"})
        is None
    )
    request = valid_collection_request()
    request["requested_url"] = "https://page.example.org/no-nct"
    transport = FakeTransport(
        responses={"https://page.example.org/no-nct": (200, {"content-type": "text/html"}, b"<html>no nct</html>")}
    )
    adapters = _adapters(tmp_path / "fallback", transport)
    outcome = adapters["clinicaltrials_gov"].collect(
        request,
        source_record={
            "source_id": "SRC-NO",
            "source_class": "CLINICAL_TRIAL_REGISTRY",
            "url": request["requested_url"],
        },
    )
    assert outcome.kind == "result"
    assert transport.calls[0].url == "https://page.example.org/no-nct"


def test_fda_extracts_from_metadata_and_skips_without_device_id(tmp_path: Path) -> None:
    adapters = _adapters(tmp_path, FakeTransport())
    fda = adapters["fda_device"]
    assert isinstance(fda, FdaDeviceAdapter)
    assert (
        fda.extract_device_id(
            {"source_class": "REGULATORY_RECORD", "metadata": {"knumber": "K123456"}},
            {"requested_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm"},
        )
        == "K123456"
    )
    source = {
        "source_id": "SRC-REG",
        "source_class": "REGULATORY_RECORD",
        "url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm",
    }
    assert fda.supports_source(source, {"requested_url": source["url"]}) is False
    selected = adapter_for_source(adapters, source)
    assert selected.adapter_id != "fda_device"


def test_resolve_adapter_json_and_feed_url_fallbacks(tmp_path: Path) -> None:
    adapters = _adapters(tmp_path, FakeTransport())
    assert (
        resolve_adapter(
            adapters,
            source_class="UNKNOWN_CLASS",
            requested_url="https://page.example.org/data.json",
        ).adapter_id
        == "json_api"
    )
    assert (
        resolve_adapter(
            adapters,
            source_class="UNKNOWN_CLASS",
            requested_url="https://page.example.org/feed.atom",
        ).adapter_id
        == "xml_feed"
    )


def test_fda_adapter_rewrites_to_openfda_and_normalizes(tmp_path: Path) -> None:
    payload = (FIXTURES / "openfda_DEN250013.json").read_bytes()
    adapters = _adapters(tmp_path, FakeTransport())
    fda = adapters["fda_device"]
    assert isinstance(fda, FdaDeviceAdapter)
    api_url = fda.build_openfda_url("DEN250013")
    assert api_url.startswith("https://api.fda.gov/device/510k.json?")
    assert "DEN250013" in api_url

    transport = FakeTransport(responses={api_url: (200, {"content-type": "application/json"}, payload)})
    adapters = _adapters(tmp_path / "fda", transport)
    fda = adapters["fda_device"]
    assert isinstance(fda, FdaDeviceAdapter)
    landing = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/denovo.cfm?knumber=DEN250013"
    source = {
        "source_id": "SRC-FDA",
        "monitor_id": "MON-FDA",
        "source_class": "REGULATORY_RECORD",
        "url": landing,
        "fda_device_id": "DEN250013",
    }
    adapter = adapter_for_source(adapters, source)
    assert isinstance(adapter, FdaDeviceAdapter)
    linkage = adapter.pathway_linkage("DEN250013")
    assert linkage["pathway"] == "DENOVO"
    assert linkage["openfda_endpoint"] == "device/510k"

    request = valid_collection_request()
    request["source_id"] = "SRC-FDA"
    request["monitor_id"] = "MON-FDA"
    request["requested_url"] = landing
    outcome = adapter.collect(request, source_record=source)
    assert outcome.kind == "result"
    assert isinstance(transport.calls[0], HttpRequest)
    assert transport.calls[0].url == api_url

    normalized = adapter.normalize_device(json.loads(payload.decode("utf-8")), device_id="DEN250013")
    assert schema_errors(normalized, NORMALIZED_DEVICE_SCHEMA) == []
    assert normalized["pathway"] == "DENOVO"
    assert normalized["device_name"] == "Synthetic De Novo fixture device"
    assert any(link["identifier"] == "DEN250013" for link in normalized["linked_identifiers"])

    for device_id, pathway, endpoint in (
        ("K123456", "510K", "device/510k"),
        ("P123456", "PMA", "device/pma"),
        ("H123456", "HDE", "device/pma"),
    ):
        link = adapter.pathway_linkage(device_id)
        assert link["pathway"] == pathway
        assert link["openfda_endpoint"] == endpoint


def test_pubmed_crossref_adapter_with_fixtures(tmp_path: Path) -> None:
    pubmed_body = (FIXTURES / "pubmed_PMID41124203.json").read_bytes()
    crossref_body = (FIXTURES / "crossref_doi_fixture.json").read_bytes()
    adapters = _adapters(tmp_path, FakeTransport())
    pubmed = adapters["pubmed_crossref"]
    assert isinstance(pubmed, PubmedCrossrefAdapter)

    pmid_url = pubmed.build_retrieval_url("PMID", "41124203")
    doi_url = pubmed.build_retrieval_url("DOI", "10.1000/neuroai.fixture.41124203")
    transport = FakeTransport(
        responses={
            pmid_url: (200, {"content-type": "application/json"}, pubmed_body),
            doi_url: (200, {"content-type": "application/json"}, crossref_body),
        }
    )
    adapters = _adapters(tmp_path / "pub", transport)
    pubmed = adapters["pubmed_crossref"]
    assert isinstance(pubmed, PubmedCrossrefAdapter)

    source = {
        "source_id": "SRC-PMID",
        "monitor_id": "MON-PMID",
        "source_class": "PEER_REVIEWED_PRIMARY_CLINICAL_STUDY",
        "url": "https://pubmed.ncbi.nlm.nih.gov/41124203/",
        "pmid": "41124203",
    }
    selected = adapter_for_source(adapters, source)
    assert isinstance(selected, PubmedCrossrefAdapter)
    request = valid_collection_request()
    request["source_id"] = "SRC-PMID"
    request["monitor_id"] = "MON-PMID"
    request["requested_url"] = source["url"]
    outcome = selected.collect(request, source_record=source)
    assert outcome.kind == "result"
    assert transport.calls[0].url == pmid_url

    normalized = selected.normalize_publication(
        json.loads(pubmed_body.decode("utf-8")),
        id_type="PMID",
        identifier="41124203",
    )
    assert schema_errors(normalized, NORMALIZED_PUBLICATION_SCHEMA) == []
    assert normalized["doi"] == "10.1000/neuroai.fixture.41124203"

    doi_source = {
        "source_id": "SRC-DOI",
        "source_class": "OFFICIAL_BIBLIOGRAPHIC_METADATA",
        "url": "https://doi.org/10.1000/neuroai.fixture.41124203",
        "doi": "10.1000/neuroai.fixture.41124203",
    }
    assert adapter_for_source(adapters, doi_source).adapter_id == "pubmed_crossref"
    doi_request = valid_collection_request()
    doi_request["source_id"] = "SRC-DOI"
    doi_request["requested_url"] = doi_source["url"]
    doi_outcome = adapters["pubmed_crossref"].collect(doi_request, source_record=doi_source)
    assert doi_outcome.kind == "result"
    assert transport.calls[1].url == doi_url
    crossref_norm = selected.normalize_publication(
        json.loads(crossref_body.decode("utf-8")),
        id_type="DOI",
        identifier="10.1000/neuroai.fixture.41124203",
    )
    assert schema_errors(crossref_norm, NORMALIZED_PUBLICATION_SCHEMA) == []

    # Without an identifier, peer-reviewed pages stay on HTTP page-capture adapter.
    page_only = {
        "source_id": "SRC-PAGE",
        "source_class": "PEER_REVIEWED_PRIMARY_CLINICAL_STUDY",
        "url": "https://page.example.org/paper",
    }
    assert adapter_for_source(adapters, page_only).adapter_id == "clinical_regulatory_http_capture"


def test_scaffold_adapters_refuse_live_collection(tmp_path: Path) -> None:
    adapters = _adapters(tmp_path, FakeTransport())
    for adapter_id, source_class in (
        ("fda_maude", "FDA_MAUDE_RECORD"),
        ("fda_recall", "FDA_RECALL_RECORD"),
        ("who_ictrp", "WHO_ICTRP_RECORD"),
        ("eu_ctis", "EU_CTIS_RECORD"),
        ("neuroscience_archive", "NEUROSCIENCE_DATASET_RECORD"),
        ("patents_grants", "PATENT_OR_GRANT_RECORD"),
    ):
        contract = load_adapter_contract(adapter_id)
        assert schema_errors(contract, STRUCTURED_ADAPTER_CONTRACT_SCHEMA) == []
        assert contract["completeness"] == "SCAFFOLD_NOT_COMPLETE"
        source = {
            "source_id": f"SRC-{adapter_id}",
            "source_class": source_class,
            "url": "https://example.org/scaffold",
        }
        selected = adapter_for_source(adapters, source)
        assert selected.adapter_id == adapter_id
        request = valid_collection_request()
        request["source_id"] = source["source_id"]
        request["requested_url"] = source["url"]
        outcome = selected.collect(request, source_record=source)
        assert outcome.kind == "failure"
        assert outcome.record["failure_class"] == "TERMS_OF_USE_BLOCKED"
        assert "SCAFFOLD_NOT_COMPLETE" in outcome.record["failure_message"]


def test_all_structured_adapter_contracts_validate() -> None:
    for adapter_id in STRUCTURED_ADAPTER_IDS:
        contract = load_adapter_contract(adapter_id)
        assert schema_errors(contract, STRUCTURED_ADAPTER_CONTRACT_SCHEMA) == []
        assert contract["adapter_id"] == adapter_id


def test_partial_adapters_declare_page_capture_boundary() -> None:
    for adapter_id in ("clinicaltrials_gov", "fda_device", "pubmed_crossref"):
        contract = load_adapter_contract(adapter_id)
        assert contract["completeness"] == "PARTIAL"
        assert "completeness" in contract["boundary"].lower() or "not" in contract["boundary"].lower()
