from __future__ import annotations

from neuroai_workbench.collector.url_normalize import (
    group_plan_items_by_retrieval_target,
    normalize_retrieval_url,
    retrieval_target_id,
)


def test_normalize_retrieval_url_canonicalizes_host_path_query() -> None:
    left = normalize_retrieval_url("HTTPS://Example.ORG:443/a/?b=2&a=1#frag")
    right = normalize_retrieval_url("https://example.org/a?a=1&b=2")
    assert left == right == "https://example.org/a?a=1&b=2"
    assert retrieval_target_id(left) == retrieval_target_id(right)


def test_group_plan_items_coalesces_equivalent_urls() -> None:
    items = [
        {"source_id": "SRC-B", "monitor_id": "MON-B", "url": "https://example.org/home"},
        {"source_id": "SRC-A", "monitor_id": "MON-A", "url": "HTTPS://Example.org/home/"},
    ]
    groups = group_plan_items_by_retrieval_target(items, source_index={})
    assert len(groups) == 1
    assert groups[0].source_ids == ("SRC-A", "SRC-B")
    assert groups[0].primary_source_id == "SRC-A"
