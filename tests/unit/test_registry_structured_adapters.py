from __future__ import annotations

import json
from pathlib import Path

from neuroai_workbench.collector.adapters.clinicaltrials import ClinicalTrialsGovAdapter
from neuroai_workbench.collector.adapters.fda_device import FdaDeviceAdapter
from neuroai_workbench.collector.adapters.registry import adapter_for_source, build_adapters, resolve_adapter
from neuroai_workbench.collector.adapters.registry_stub import ClinicalRegulatoryHttpCaptureAdapter
from neuroai_workbench.collector.config import CollectorConfig
from neuroai_workbench.collector.dns import DnsGuard
from neuroai_workbench.collector.http_client import HttpRequest
from tests.unit.test_collector_adapters_scheduler import GLOBAL_IP, FakeTransport
from tests.unit.test_collector_schemas import CONFIG_HASH, valid_collection_request

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "collector"


def registry_getaddrinfo(host: str, port, *args, **kwargs):
    allowed = {
        "clinicaltrials.gov",
        "www.accessdata.fda.gov",
        "accessdata.fda.gov",
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


def test_fda_adapter_selected_for_explicit_device_id(tmp_path: Path) -> None:
    html = (FIXTURES / "fda_DEN250013.html").read_bytes()
    url = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/denovo.cfm?knumber=DEN250013"
    transport = FakeTransport(responses={url: (200, {"content-type": "text/html"}, html)})
    adapters = _adapters(tmp_path, transport)
    source = {
        "source_id": "SRC-FDA",
        "monitor_id": "MON-FDA",
        "source_class": "REGULATORY_RECORD",
        "url": url,
        "fda_device_id": "DEN250013",
    }
    adapter = adapter_for_source(adapters, source)
    assert isinstance(adapter, FdaDeviceAdapter)
    assert adapter.extract_device_id(source, {"requested_url": url}) == "DEN250013"
    request = valid_collection_request()
    request["source_id"] = "SRC-FDA"
    request["monitor_id"] = "MON-FDA"
    request["requested_url"] = url
    outcome = adapter.collect(request, source_record=source)
    assert outcome.kind == "result"
    assert isinstance(transport.calls[0], HttpRequest)
