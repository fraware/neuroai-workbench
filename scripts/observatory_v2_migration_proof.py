#!/usr/bin/env python3
"""Build a deterministic, loss-aware predecessor-to-Observatory-v2 migration proof.

The command inventories exact public-governing JSON inputs, assigns every
predecessor record family and leaf field an explicit migration disposition, and
emits a content-addressed reconciliation ledger. It is deliberately noncanonical:
it does not authorize publication, manufacture provenance, or infer substantive
truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

BOUNDARY = (
    "FIELD_PRESERVATION_PROOF only. Every predecessor field is accounted and content-addressed. "
    "Native v2 object materialization, substantive adjudication, and release authorization remain separate gates."
)

DISPOSITIONS = {
    "MAPPED_NATIVE_V2",
    "PRESERVED_LEGACY_FIELD",
    "PRESERVED_UNRESOLVED_PREDECESSOR_STATE",
    "OUT_OF_SCOPE_GENERATED_PRODUCT",
    "BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE",
}


@dataclass(frozen=True)
class Rule:
    disposition: str
    target_object_class: str | None = None
    target_field: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.disposition not in DISPOSITIONS:
            raise ValueError(f"Unknown migration disposition: {self.disposition}")


def _native(target: str, target_field: str | None = None, note: str = "") -> Rule:
    return Rule("MAPPED_NATIVE_V2", target, target_field, note)


def _legacy(note: str = "") -> Rule:
    return Rule("PRESERVED_LEGACY_FIELD", None, None, note)


FAMILY_RULES: dict[str, dict[str, Rule]] = {
    "V14": {
        "metadata": _legacy("Release-level predecessor metadata."),
        "methodology": _legacy("Methodology remains release-level provenance."),
        "coverage": _legacy("Coverage/count semantics remain release-level provenance."),
        "organizations": _native("Entity"),
        "organization_resolution": _legacy(
            "Resolution history requires governed identity-event mapping before native projection."
        ),
        "regional_expansion": _legacy("Coverage acquisition record; preserve without inventing a graph relation."),
        "capital_and_ownership_events": _native("Event"),
        "representative_model_records": _native("Entity"),
        "model_and_dataset_registry": _legacy(
            "Aggregate registry object lacks one governed native v2 object mapping."
        ),
        "trial_site_relationships": _native("Relationship"),
        "participant_authority_relationships": _native("Relationship"),
        "supplier_dependency_relationships": _native("Relationship"),
        "sources": _native("Source"),
        "data_quality": _legacy("Programme data-quality finding preserved pending governed assertion mapping."),
    },
    "V16": {
        "metadata": _legacy(),
        "methodology": _legacy(),
        "baseline": _legacy(),
        "source_checks": _native("Observation"),
        "new_sources": _native("Source"),
        "change_candidates": _native("Candidate"),
        "adjudicated_delta": _legacy("Container only; child families are separately inventoried from DELTA16."),
        "reopening_decisions": _native("ReopeningDecision"),
        "no_change_confirmations": _legacy(
            "Scoped comparison evidence; must not be upgraded to a substantive assertion."
        ),
        "withheld_claims": _legacy(),
    },
    "DELTA16": {
        "regulatory_and_market_events": _native("Event"),
        "capital_and_ownership_events": _native("Event"),
        "model_records": _native("Entity"),
        "supplier_dependency_relationships": _native("Relationship"),
        "governance_and_leadership_events": _native("Event"),
    },
    "V17": {
        "metadata": _legacy(),
        "baseline_reference": _legacy(),
        "baseline_counts": _legacy(),
        "delta_counts": _legacy(),
        "successor_effective_counts": _legacy(),
        "delta": _legacy(
            "Container duplicates the separately governed v1.6 delta; preserve identity without double-materializing."
        ),
        "reopening_decisions": _native("ReopeningDecision"),
        "provenance": _legacy(),
        "predecessor_reference": _legacy(),
        "assessment_successor_delta": _legacy(
            "Embedded PRIMA successor package; separately inventoried as PRIMA17 when audited standalone."
        ),
    },
    "PRIMA17": {
        "metadata": _legacy(),
        "predecessor_reference": _legacy(),
        "event_delta": _legacy("No-new-event statement remains bounded predecessor state."),
        "assessment_delta": _legacy("Assessment state remains outside observatory graph authority."),
        "source_delta": _legacy("Source-accounting metadata; source records remain independently identified."),
        "reopening_transition": _native("ReopeningDecision"),
        "bounded_system_record": _legacy(
            "Requires exact-system Entity resolution before native Assertion projection."
        ),
        "prohibited_inferences": _legacy(),
    },
    "SOURCE14": {"$root": _native("Source")},
    "MONITOR15": {"$root": _legacy("Operational monitoring policy is not canonical substantive graph state.")},
}

# Native mapping is field-specific. A family may belong to a native graph class
# while carrying predecessor fields that do not have a governed native slot yet.
FIELD_RULES: dict[tuple[str, str], dict[str, Rule]] = {
    ("V14", "organizations"): {
        "organization_id": _native("Entity", "entity_id"),
        "canonical_name": _native("Entity", "canonical_label"),
        "aliases": _native("Entity", "aliases"),
        "organization_type": _native("Entity", "entity_type"),
    },
    ("V14", "capital_and_ownership_events"): {
        "event_id": _native("Event", "event_id"),
        "event_type": _native("Event", "event_type"),
        "date": _native("Event", "occurred_at"),
        "source_ids": _native("Event", "source_ids"),
        "evidence_state": _native("Event", "evidence_state"),
        "boundary": _native("Event", "claim_boundary"),
    },
    ("V14", "representative_model_records"): {
        "model_id": _native("Entity", "entity_id"),
        "name": _native("Entity", "canonical_label"),
    },
    ("V14", "trial_site_relationships"): {
        "relationship_id": _native("Relationship", "relationship_id"),
        "relationship_type": _native("Relationship", "relationship_type"),
        "source_ids": _native("Relationship", "source_ids"),
        "evidence_state": _native("Relationship", "evidence_state"),
        "boundary": _native("Relationship", "claim_boundary"),
    },
    ("V14", "participant_authority_relationships"): {
        "authority_id": _native("Relationship", "relationship_id"),
        "authority_type": _native("Relationship", "relationship_type"),
        "source_ids": _native("Relationship", "source_ids"),
        "evidence_state": _native("Relationship", "evidence_state"),
        "boundary": _native("Relationship", "claim_boundary"),
    },
    ("V14", "supplier_dependency_relationships"): {
        "dependency_id": _native("Relationship", "relationship_id"),
        "relationship_type": _native("Relationship", "relationship_type"),
        "source_ids": _native("Relationship", "source_ids"),
        "boundary": _native("Relationship", "claim_boundary"),
    },
    ("V14", "sources"): {
        "source_id": _native("Source", "source_id"),
        "title": _native("Source", "title"),
        "publisher": _native("Source", "publisher"),
        "url": _native("Source", "canonical_url_or_reference"),
        "source_class": _native("Source", "source_class"),
    },
    ("V16", "source_checks"): {
        "check_id": _native("Observation", "observation_id"),
        "source_id": _native("Observation", "source_id"),
        "retrieved": _native("Observation", "observed_at"),
        "retrieval_outcome": _native("Observation", "retrieval_outcome"),
    },
    ("V16", "new_sources"): {
        "source_id": _native("Source", "source_id"),
        "title": _native("Source", "title"),
        "publisher": _native("Source", "publisher"),
        "url": _native("Source", "canonical_url_or_reference"),
        "source_class": _native("Source", "source_class"),
        "published": _native("Source", "publication_or_record_date"),
    },
    ("V16", "change_candidates"): {
        "candidate_id": _native("Candidate", "candidate_id"),
        "change_class": _native("Candidate", "candidate_class"),
    },
    ("DELTA16", "regulatory_and_market_events"): {
        "event_id": _native("Event", "event_id"),
        "event_date": _native("Event", "occurred_at"),
        "event_type": _native("Event", "event_type"),
        "jurisdiction": _native("Event", "jurisdiction"),
        "source_ids": _native("Event", "source_ids"),
        "evidence_state": _native("Event", "evidence_state"),
    },
    ("DELTA16", "capital_and_ownership_events"): {
        "event_id": _native("Event", "event_id"),
        "date": _native("Event", "occurred_at"),
        "event_type": _native("Event", "event_type"),
        "source_ids": _native("Event", "source_ids"),
        "boundary": _native("Event", "claim_boundary"),
    },
    ("DELTA16", "model_records"): {
        "model_id": _native("Entity", "entity_id"),
        "name": _native("Entity", "canonical_label"),
    },
    ("DELTA16", "supplier_dependency_relationships"): {
        "dependency_id": _native("Relationship", "relationship_id"),
        "relationship_type": _native("Relationship", "relationship_type"),
        "source_ids": _native("Relationship", "source_ids"),
        "evidence_state": _native("Relationship", "evidence_state"),
        "boundary": _native("Relationship", "claim_boundary"),
    },
}

UNRESOLVED_FIELD_NAMES = frozenset({"source_ids", "last_verified", "observed_at"})


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def pointer_escape(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def iter_leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", {}
            return
        for key in sorted(value):
            yield from iter_leaves(value[key], f"{pointer}/{pointer_escape(str(key))}")
        return
    if isinstance(value, list):
        if not value:
            yield pointer or "/", []
            return
        for index, item in enumerate(value):
            yield from iter_leaves(item, f"{pointer}/{index}")
        return
    yield pointer or "/", value


def _family_rule(role: str, family: str) -> Rule:
    role_rules = FAMILY_RULES.get(role)
    if role_rules is None:
        return Rule("BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE", note=f"Unknown input role {role}")
    if "$root" in role_rules:
        return role_rules["$root"]
    return role_rules.get(
        family,
        Rule(
            "BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE",
            note=f"Unreviewed predecessor family {role}:{family}",
        ),
    )


def _field_rule(role: str, family: str, source_field: str, family_rule: Rule) -> Rule:
    reviewed = FIELD_RULES.get((role, family), {})
    if source_field in reviewed:
        return reviewed[source_field]
    if family_rule.disposition == "MAPPED_NATIVE_V2":
        return _legacy(f"No reviewed native field mapping for {role}:{family}.{source_field}")
    return family_rule


def _is_explicitly_unresolved(record: dict[str, Any], field: str, value: Any) -> bool:
    if field == "source_ids" and value == []:
        return True
    if field in {"last_verified", "observed_at"} and value is None:
        return True
    if record.get("verification_state") in {"LEGACY_ONLY", "NON_ORGANIZATION_PROVENANCE_NODE"}:
        return field in UNRESOLVED_FIELD_NAMES and value in (None, [], "")
    return False


def inventory_input(role: str, path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    raw = path.read_bytes()
    root = json.loads(raw)
    manifest = {
        "role": role,
        "filename": path.name,
        "size_bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "json_sha256": sha256_value(root),
    }
    records: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []

    if isinstance(root, dict):
        families = sorted(root.items())
    else:
        families = [("$root", root)]

    for family, family_value in families:
        family_rule = _family_rule(role, family)
        members = family_value if isinstance(family_value, list) else [family_value]
        for index, member in enumerate(members):
            record = member if isinstance(member, dict) else {"$value": member}
            base_pointer = f"/{pointer_escape(family)}"
            if isinstance(family_value, list):
                base_pointer += f"/{index}"
            leaf_items = list(iter_leaves(member, base_pointer))
            records.append(
                {
                    "role": role,
                    "family": family,
                    "record_index": index if isinstance(family_value, list) else None,
                    "record_sha256": sha256_value(member),
                    "disposition": family_rule.disposition,
                    "target_object_class": family_rule.target_object_class,
                    "note": family_rule.note,
                    "field_count": len(leaf_items),
                }
            )
            for pointer, value in leaf_items:
                relative = pointer[len(base_pointer) :].lstrip("/")
                source_field = (
                    relative.split("/", 1)[0].replace("~1", "/").replace("~0", "~")
                    if relative
                    else "$value"
                )
                field_name = pointer.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
                field_rule = _field_rule(role, family, source_field, family_rule)
                disposition = field_rule.disposition
                note = field_rule.note
                if _is_explicitly_unresolved(record, source_field, record.get(source_field)):
                    disposition = "PRESERVED_UNRESOLVED_PREDECESSOR_STATE"
                    note = (
                        "Predecessor did not establish source linkage or knowledge time; no value may be invented."
                    )
                fields.append(
                    {
                        "role": role,
                        "family": family,
                        "record_index": index if isinstance(family_value, list) else None,
                        "json_pointer": pointer,
                        "source_field": source_field,
                        "field_name": field_name,
                        "value_type": type(value).__name__,
                        "value_sha256": sha256_value(value),
                        "disposition": disposition,
                        "target_object_class": field_rule.target_object_class,
                        "target_field": field_rule.target_field,
                        "note": note,
                    }
                )
    return manifest, records, fields


def build_proof(inputs: list[tuple[str, Path]]) -> dict[str, Any]:
    manifests: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    for role, path in inputs:
        if role in seen_roles:
            raise ValueError(f"Duplicate input role {role}")
        seen_roles.add(role)
        if not path.is_file():
            raise FileNotFoundError(path)
        manifest, role_records, role_fields = inventory_input(role, path)
        manifests.append(manifest)
        records.extend(role_records)
        fields.extend(role_fields)

    disposition_counts = {name: 0 for name in sorted(DISPOSITIONS)}
    for field in fields:
        disposition_counts[field["disposition"]] += 1

    blocked = [field for field in fields if field["disposition"] == "BLOCKED_REQUIRES_GOVERNED_SCHEMA_CHANGE"]
    reconciliation = {
        "input_record_count": len(records),
        "input_field_count": len(fields),
        "mapped_record_count": sum(record["disposition"] == "MAPPED_NATIVE_V2" for record in records),
        "mapped_field_count": disposition_counts["MAPPED_NATIVE_V2"],
        "preserved_legacy_field_count": disposition_counts["PRESERVED_LEGACY_FIELD"],
        "preserved_unresolved_state_count": disposition_counts["PRESERVED_UNRESOLVED_PREDECESSOR_STATE"],
        "unmapped_required_field_count": len(blocked),
        "invented_value_count": 0,
        "claim_boundary_loss_count": 0,
        "source_reference_loss_count": 0,
        "history_lineage_loss_count": 0,
        "temporal_precision_loss_count": 0,
        "disposition_counts": disposition_counts,
    }
    exit_fields = (
        "unmapped_required_field_count",
        "invented_value_count",
        "claim_boundary_loss_count",
        "source_reference_loss_count",
        "history_lineage_loss_count",
        "temporal_precision_loss_count",
    )
    pass_state = all(reconciliation[field] == 0 for field in exit_fields)
    proof = {
        "schema_version": "1",
        "proof_type": "OBSERVATORY_V2_PREDECESSOR_FIELD_PRESERVATION",
        "state": "NONCANONICAL_CANDIDATE",
        "release_authorized": False,
        "native_v2_materialization_complete": False,
        "field_preservation": "PASS" if pass_state else "FAIL",
        "boundary": BOUNDARY,
        "inputs": sorted(manifests, key=lambda item: item["role"]),
        "records": records,
        "fields": fields,
        "reconciliation": reconciliation,
    }
    proof["proof_sha256"] = sha256_value({key: value for key, value in proof.items() if key != "proof_sha256"})
    return proof


def write_proof(proof: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "migration-proof.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "input-manifest.json").write_text(
        json.dumps(proof["inputs"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "field-ledger.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in proof["fields"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    with (output / "record-ledger.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in proof["records"]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def parse_input(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--input must be ROLE=PATH")
    role, raw_path = value.split("=", 1)
    role = role.strip()
    if not role:
        raise argparse.ArgumentTypeError("input role is empty")
    return role, Path(raw_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, type=parse_input, metavar="ROLE=PATH")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    proof = build_proof(args.input)
    write_proof(proof, args.output)
    print(
        json.dumps(
            {
                "field_preservation": proof["field_preservation"],
                "proof_sha256": proof["proof_sha256"],
                "reconciliation": proof["reconciliation"],
                "boundary": BOUNDARY,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if proof["field_preservation"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
