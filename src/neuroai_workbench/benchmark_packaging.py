"""Packaged PRE-G2 public benchmark resources for the selected keyed-HMAC lineage.

This module is additive packaging over ``evaluation_benchmarks``. It does not
introduce a second commitment foundation, claim G0/G1/G2 passage, or load real
held-out membership or labels.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Any, cast

from jsonschema import Draft202012Validator

from neuroai_workbench.evaluation_benchmarks import (
    BENCHMARK_KINDS,
    BenchmarkContractError,
    validate_prediction_rows,
    validate_public_benchmark_contract,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.benchmarks"

PATENT_SCHEMA = "PATENT_PUBLIC_BENCHMARK_CONTRACT.schema.json"
PRODUCT_SCHEMA = "PRODUCT_PUBLIC_BENCHMARK_CONTRACT.schema.json"
PATENT_CONTRACT = "D3_PATENT_PRE_G2.contract.json"
PRODUCT_CONTRACT = "D4_PRODUCT_PRE_G2.contract.json"
SYNTHETIC_FIXTURES = "SYNTHETIC_FIXTURES.json"

_SCHEMA_BY_KIND = {
    "PATENT": PATENT_SCHEMA,
    "PRODUCT": PRODUCT_SCHEMA,
}

_CONTRACT_BY_KIND = {
    "PATENT": PATENT_CONTRACT,
    "PRODUCT": PRODUCT_CONTRACT,
}

_MODEL_OUTPUT_AUTHORITY = "UNTRUSTED_DRAFT_ONLY"
_SYNTHETIC_STATUS = "SYNTHETIC_TEST_ONLY"
_HUMAN_ANNOTATION_BASIS = "HUMAN_SYNTHETIC_ANNOTATIONS"

# Public packaged contracts must also fail closed on nested oracle-style keys
# that are outside the exact allowlist surface.
_PACKAGED_LEAKAGE_KEYS = frozenset(
    {
        "abstract",
        "adjudicated_label",
        "adjudication_outcome",
        "adjudicator_decision",
        "adjudicator_packet",
        "adjudicator_packets",
        "answer_key",
        "benchmark_membership",
        "claim_text",
        "gold",
        "gold_label",
        "gold_labels",
        "ground_truth",
        "held_out",
        "held_out_member",
        "heldout_member",
        "heldout_members",
        "heldout_membership",
        "holdout_member",
        "human_label",
        "human_labels",
        "is_holdout",
        "licensed_bytes",
        "member_ids",
        "membership",
        "nonce",
        "nonce_b64",
        "nonce_hex",
        "oracle_label",
        "raw_bytes",
        "raw_text",
        "reference_label",
        "reviewer_labels",
        "secret_nonce",
        "source_text",
        "test_labels",
        "true_label",
        "truth",
    }
)


def _resource_json(name: str) -> Any:
    return json.loads(files(RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8"))


def _load_schema(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], _resource_json(name))


def _format_schema_errors(errors: Sequence[Any]) -> str:
    formatted: list[str] = []
    for error in errors:
        path = "$"
        if error.absolute_path:
            path += "." + ".".join(str(part) for part in error.absolute_path)
        formatted.append(f"{path}: {error.message}")
    return "; ".join(formatted)


def _walk_packaged_leakage(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _PACKAGED_LEAKAGE_KEYS:
                raise BenchmarkContractError(f"Packaged public contract contains prohibited field at {path}.{key}")
            _walk_packaged_leakage(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_packaged_leakage(child, f"{path}[{index}]")


def validate_packaged_public_contract(contract: Mapping[str, Any]) -> None:
    """Validate a packaged public contract with schema + selected-lineage semantics."""

    _walk_packaged_leakage(contract)
    kind = contract.get("benchmark_kind")
    if kind not in _SCHEMA_BY_KIND:
        raise BenchmarkContractError(f"benchmark_kind must be one of {sorted(BENCHMARK_KINDS)}")
    validator = Draft202012Validator(_load_schema(_SCHEMA_BY_KIND[str(kind)]))
    errors = sorted(
        validator.iter_errors(contract),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise BenchmarkContractError(_format_schema_errors(errors))
    validate_public_benchmark_contract(contract)


def load_packaged_public_contract(kind: str) -> dict[str, Any]:
    """Load and validate one empty DRAFT_UNFROZEN public contract resource."""

    if kind not in _CONTRACT_BY_KIND:
        raise BenchmarkContractError(f"Unsupported packaged contract kind: {kind!r}")
    contract = cast(dict[str, Any], _resource_json(_CONTRACT_BY_KIND[kind]))
    validate_packaged_public_contract(contract)
    return contract


def load_all_packaged_public_contracts() -> dict[str, dict[str, Any]]:
    """Load and validate both packaged D3/D4 public contracts."""

    return {kind: load_packaged_public_contract(kind) for kind in sorted(_CONTRACT_BY_KIND)}


def validate_synthetic_fixture(fixture: Mapping[str, Any]) -> None:
    """Validate a synthetic fixture and keep model output as UNTRUSTED_DRAFT_ONLY."""

    if fixture.get("synthetic") is not True:
        raise BenchmarkContractError("Repository benchmark fixtures must be explicitly synthetic")
    if fixture.get("benchmark_status") != _SYNTHETIC_STATUS:
        raise BenchmarkContractError("Synthetic fixture cannot claim frozen benchmark status")
    if fixture.get("benchmark_kind") not in BENCHMARK_KINDS:
        raise BenchmarkContractError(f"Synthetic fixture benchmark_kind must be one of {sorted(BENCHMARK_KINDS)}")

    annotations = fixture.get("human_annotations")
    if not isinstance(annotations, list) or not annotations:
        raise BenchmarkContractError("Synthetic fixture requires human_annotations")
    for index, annotation in enumerate(annotations):
        if not isinstance(annotation, Mapping):
            raise BenchmarkContractError(f"human_annotations[{index}] must be an object")
        annotator_id = annotation.get("annotator_id")
        if not isinstance(annotator_id, str) or not annotator_id:
            raise BenchmarkContractError(f"human_annotations[{index}] requires annotator_id")
        label = annotation.get("label")
        if not isinstance(label, str) or not label:
            raise BenchmarkContractError(f"human_annotations[{index}] requires a non-empty label")

    adjudication = fixture.get("adjudication")
    if not isinstance(adjudication, Mapping):
        raise BenchmarkContractError("Synthetic fixture requires an adjudication object")
    if adjudication.get("basis") != _HUMAN_ANNOTATION_BASIS:
        raise BenchmarkContractError("Synthetic adjudication must be human-annotation based")

    model_outputs = fixture.get("model_outputs", [])
    if not isinstance(model_outputs, list):
        raise BenchmarkContractError("model_outputs must be a list")
    prediction_rows: list[dict[str, Any]] = []
    for index, output in enumerate(model_outputs):
        if not isinstance(output, Mapping):
            raise BenchmarkContractError(f"model_outputs[{index}] must be an object")
        if output.get("authority") != _MODEL_OUTPUT_AUTHORITY:
            raise BenchmarkContractError("Synthetic model outputs must remain untrusted drafts")
        model_id = output.get("model_id")
        if not isinstance(model_id, str) or not model_id:
            raise BenchmarkContractError(f"model_outputs[{index}] requires model_id")
        prediction = output.get("prediction")
        if not isinstance(prediction, str) or not prediction:
            raise BenchmarkContractError(f"model_outputs[{index}] requires prediction")
        row: dict[str, Any] = {
            "item_id": f"{fixture.get('fixture_id', 'SYN')}:{model_id}:{index}",
            "prediction": prediction,
        }
        if "probability_positive" in output:
            row["probability_positive"] = output["probability_positive"]
        # Reuse the selected-lineage prediction leakage guard without elevating drafts.
        prediction_rows.append(row)
    if prediction_rows:
        validate_prediction_rows(prediction_rows)


def load_synthetic_fixtures() -> list[dict[str, Any]]:
    """Load and validate the packaged synthetic-only fixture set."""

    payload = _resource_json(SYNTHETIC_FIXTURES)
    if not isinstance(payload, list) or not payload:
        raise BenchmarkContractError("SYNTHETIC_FIXTURES.json must be a non-empty list")
    fixtures: list[dict[str, Any]] = []
    for index, fixture in enumerate(payload):
        if not isinstance(fixture, Mapping):
            raise BenchmarkContractError(f"SYNTHETIC_FIXTURES[{index}] must be an object")
        material = cast(dict[str, Any], dict(fixture))
        validate_synthetic_fixture(material)
        fixtures.append(material)
    return fixtures
