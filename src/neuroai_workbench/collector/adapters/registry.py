from __future__ import annotations

from typing import Any

from ..config import CollectorConfig
from ..credentials import CredentialProvider
from ..dns import DnsGuard
from ..http_client import HttpTransport
from ..service import HttpCollector
from .auth_download import AuthenticatedDownloadStub
from .base import CollectorAdapter
from .html import HtmlPageAdapter
from .json_api import JsonApiAdapter
from .registry_stub import ClinicalRegulatoryRegistryStub
from .xml_feed import XmlFeedAdapter

ADAPTER_ORDER: tuple[str, ...] = (
    "auth_download",
    "registry_stub",
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
        "registry_stub": ClinicalRegulatoryRegistryStub(collector),
    }
    if credential_provider is not None:
        adapters["auth_download"] = AuthenticatedDownloadStub(collector, credential_provider=credential_provider)
    return adapters


def resolve_adapter(
    adapters: dict[str, CollectorAdapter],
    *,
    source_class: str,
    requested_url: str,
) -> CollectorAdapter:
    ordered = [adapters[adapter_id] for adapter_id in ADAPTER_ORDER if adapter_id in adapters]
    ordered.extend(adapter for adapter_id, adapter in adapters.items() if adapter_id not in ADAPTER_ORDER)
    for adapter in ordered:
        if adapter.supports_source_class(source_class):
            return adapter
    if requested_url.rstrip("/").endswith(".json"):
        return adapters["json_api"]
    if any(token in requested_url.lower() for token in ("/rss", "/atom", ".xml")):
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
    )
