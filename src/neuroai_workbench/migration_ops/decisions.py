from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_migration_decisions(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    decisions: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if not text:
            continue
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError(f"Decision line {line_number} must be a JSON object")
        decisions.append(value)
    return decisions


def decisions_by_subject(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        subject_id = decision.get("subject_id")
        if isinstance(subject_id, str):
            mapping[subject_id] = decision
    return mapping


def apply_warning_dispositions(
    warnings: list[dict[str, Any]],
    by_subject: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for warning in warnings:
        clone = dict(warning)
        decision = by_subject.get(str(warning.get("warning_id", "")))
        if decision and isinstance(decision.get("disposition"), str):
            clone["human_disposition"] = decision["disposition"]
            clone["decision_id"] = decision.get("decision_id")
        updated.append(clone)
    return updated
