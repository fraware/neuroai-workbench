"""Retrieval-target URL normalization for coalesce-by-fetch identity.

Source identity and retrieval identity remain distinct. Normalization is lexical
canonicalization only; it does not claim semantic equivalence beyond that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ..util import sha256_bytes


def normalize_retrieval_url(url: str) -> str:
    """Return a canonical http(s) retrieval URL for target grouping."""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        return url.strip()
    host = parsed.hostname.lower().rstrip(".")
    port = parsed.port
    if port is not None and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query_items = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    query = urlencode(query_items, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def retrieval_target_id(normalized_url: str) -> str:
    digest = sha256_bytes(normalized_url.encode("utf-8"))
    return f"RTGT-{digest[:32]}"


@dataclass(frozen=True)
class RetrievalTargetGroup:
    retrieval_target_id: str
    normalized_url: str
    requested_url: str
    source_ids: tuple[str, ...]
    primary_source_id: str
    primary_monitor_id: str
    primary_item: dict[str, Any]


def group_plan_items_by_retrieval_target(
    items: list[dict[str, Any]],
    *,
    source_index: dict[str, dict[str, Any]],
) -> list[RetrievalTargetGroup]:
    """Group due/manual plan items by normalized retrieval URL.

    Non-http(s) URLs each form a singleton group so POLICY_BLOCK still applies
    per logical source without false coalescing of local paths.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in items:
        url = str(item.get("url") or "")
        source_id = str(item["source_id"])
        record = source_index.get(source_id) or {}
        if not url:
            url = str(record.get("url") or "")
        normalized = normalize_retrieval_url(url)
        key = normalized if normalized.startswith(("http://", "https://")) else f"singleton:{source_id}:{url}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(item)

    groups: list[RetrievalTargetGroup] = []
    for key in order:
        members = sorted(buckets[key], key=lambda row: str(row["source_id"]))
        primary = members[0]
        primary_id = str(primary["source_id"])
        url = str(primary.get("url") or source_index.get(primary_id, {}).get("url") or "")
        normalized = normalize_retrieval_url(url)
        groups.append(
            RetrievalTargetGroup(
                retrieval_target_id=retrieval_target_id(
                    normalized if normalized.startswith(("http://", "https://")) else url
                ),
                normalized_url=normalized,
                requested_url=url,
                source_ids=tuple(str(item["source_id"]) for item in members),
                primary_source_id=primary_id,
                primary_monitor_id=str(primary["monitor_id"]),
                primary_item=primary,
            )
        )
    return groups
