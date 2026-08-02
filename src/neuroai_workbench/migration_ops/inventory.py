from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_archive_inventory(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if not text:
            continue
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError(f"Inventory line {line_number} must be a JSON object")
        records.append(value)
    return records


def load_unresolved_ambiguities(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Unresolved ambiguities document must be a JSON object")
    return value
