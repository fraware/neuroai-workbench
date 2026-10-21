"""Deterministic, offline, nonterminal term screening of saved R1.7 PMC XML.

A mention is not an accepted offering, commercial availability claim, canonical
identity, or an exhaustive extraction decision. This script only reads saved bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

TERMS = {
    "Emotiv Insight": "DEVICE_MENTION_CANDIDATE",
    "OpenBCI Galea": "DEVICE_MENTION_CANDIDATE",
    "OpenBCI Ultracortex": "DEVICE_MENTION_CANDIDATE",
    "Unicorn Hybrid Black": "DEVICE_MENTION_CANDIDATE",
    "Bitbrain": "DEVICE_MENTION_CANDIDATE",
    "Muse": "DEVICE_MENTION_CANDIDATE",
    "OpenBCI": "DEVICE_MENTION_CANDIDATE",
    "ROS4HC": "FRAMEWORK_MENTION",
    "OpenViBE": "FRAMEWORK_MENTION",
    "ROS Neuro": "FRAMEWORK_MENTION",
    "ASCRIBE-XR": "PLATFORM_MENTION",
}
PATTERN = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(term) for term in sorted(TERMS, key=len, reverse=True)) + r")(?!\w)",
    re.IGNORECASE,
)
MAX_MATCHES = 500


def screen_saved_article(path: Path) -> dict[str, Any]:
    match = re.fullmatch(r"pmid-([0-9]+)-fulltext\.xml", path.name)
    if match is None:
        raise ValueError("Saved XML filename must preserve its PMID")
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    root = ET.fromstring(payload)
    if root.tag != "article":
        raise ValueError("Saved source must be a JATS article")
    pmids = [(node.text or "").strip() for node in root.iter("article-id") if node.get("pub-id-type") == "pmid"]
    if pmids != [match.group(1)]:
        raise ValueError("Saved article PMID differs from its filename")
    body = root.find("body")
    if body is None:
        raise ValueError("Saved article has no body")
    found: list[dict[str, Any]] = []
    passages = 0
    for passage in body.iter("p"):
        text = " ".join("".join(passage.itertext()).split())
        if not text:
            continue
        passages += 1
        for matched in PATTERN.finditer(text):
            term = next(key for key in TERMS if key.casefold() == matched.group().casefold())
            found.append(
                {
                    "term": term,
                    "mention_type": TERMS[term],
                    "passage_index": passages,
                    "passage_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "exact_matched_text": matched.group(),
                    "context": text[max(0, matched.start() - 65) : matched.end() + 65],
                    "disposition": "UNRESOLVED_MENTION_FOR_REVIEW",
                }
            )
            if len(found) > MAX_MATCHES:
                raise ValueError("Source mention limit exceeded; review before reporting completeness")
    return {
        "pmid": match.group(1),
        "source_file": path.name,
        "source_raw_sha256": digest,
        "body_paragraph_count": passages,
        "mention_count": len(found),
        "mentions": found,
        "status": "CANDIDATE_MENTION_SCREENING_ONLY",
        "product_identity_or_completion_inferred": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    files = sorted(args.input_dir.glob("pmid-*-fulltext.xml"))
    if not files:
        parser.error("No saved public article XML files; nothing to screen")
    records = [screen_saved_article(path) for path in files]
    report = {
        "report_id": "R1_7_PUBLIC_JATS_MENTION_SCREENING_v0.1",
        "papers": records,
        "status": "NONTERMINAL_SCREENING_ONLY",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    for record in records:
        print(
            f"PMID {record['pmid']}: {record['mention_count']} literal body mentions; "
            f"raw SHA256 {record['source_raw_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
