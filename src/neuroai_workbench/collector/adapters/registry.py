from __future__ import annotations

from typing import Any

from ..config import CollectorConfig
from ..credentials import CredentialProvider
from ..dns import DnsGuard
from ..http_client import HttpTransport
from ..service import HttpCollector
from .auth_download import AuthenticatedDownloadStub
from .base import CollectorAdapter
from .clinicaltrials import ClinicalTrialsGovAdapter
from .fda_device import FdaDeviceAdapter
from .html import HtmlPageAdapter
from .json_api import JsonApiAdapter
from .registry_stub import ClinicalRegulatoryHttpCaptureAdapter
from .xml_feed import XmlFeedAdapter

# Explicit class→adapter preference order (first match wins).
ADAPTER_ORDER: tuple[str, ...] = (
    "auth_download",
    "clinicaltrials_gov",
    "fda_device",
    "clinical_regulatory_http_capture",
    "json_api",
    "xml_feed",
    "html",
)


def build_adapters(
    *,
    config: CollectorConfig,
    transport: HttpTransport,
    quarantine_root,
    credential_provider: CredentialProvider | None = None,
    dns_guard: DnsGuard | None = None,
) -> dict[str, CollectorAdapter]:
    collector = HttpCollector(config=config, transport=transport, quarantine_root=quarantine_root)
    if dns_guard is not None:
        collector.http_client.dns_guard = dns_guard
    adapters: dict[str, CollectorAdapter] = {
        "html": HtmlPageAdapter(collector),
        "json_api": JsonApiAdapter(collector),
        "xml_feed": XmlFeedAdapter(collector),
        "clinical_regulatory_http_capture": ClinicalRegulatoryHttpCaptureAdapter(collector),
        "clinicaltrials_gov": ClinicalTrialsGovAdapter(collector),
        "fda_device": FdaDeviceAdapter(collector),
    }
    if credential_provider is not None:
        adapters["auth_download"] = AuthenticatedDownloadStub(collector, credential_provider=credential_provider)
    return adapters


def resolve_adapter(
    adapters: dict[str, CollectorAdapter],
    *,
    source_class: str,
    requested_url: str,
    source_record: dict[str, Any] | None = None,
) -> CollectorAdapter:
    ordered = [adapters[adapter_id] for adapter_id in ADAPTER_ORDER if adapter_id in adapters]
    ordered.extend(adapter for adapter_id, adapter in adapters.items() if adapter_id not in ADAPTER_ORDER)

    # Prefer FDA adapter only when an explicit device identifier is present.
    fda = adapters.get("fda_device")
    if fda is not None and source_record is not None and hasattr(fda, "supports_source"):
        if fda.supports_source(source_record, {"requested_url": requested_url}):  # type: ignore[attr-defined]
            return fda

    for adapter in ordered:
        if adapter.adapter_id == "fda_device":
            continue
        if adapter.supports_source_class(source_class):
            return adapter
    if requested_url.rstrip("/").endswith(".json"):
        return adapters["json_api"]
    if any(token in requested_url.lower() for token in ("/rss", "/atom", ".xml", "/feed")):
        return adapters["xml_feed"]
    return adapters["html"]


def adapter_for_source(
    adapters: dict[str, CollectorAdapter],
    source_record: dict[str, Any],
) -> CollectorAdapter:
    return resolve_adapter(
        adapters,
        source_class=str(source_record.get("source_class", "")),
        requested_url=str(source_record.get("url", "")),
        source_record=source_record,
    )
