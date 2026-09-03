from __future__ import annotations

import hashlib
import json
import math
from importlib.resources import files
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

CANONICALIZATION = "JSON_UTF8_SORTED_KEYS_COMPACT_V1"
COMMITMENT_SCHEME = "SHA256_DOMAIN_CANONICAL_PAYLOAD_NONCE_V1"
NONCE_DISPOSITION = "S3_CONTROLLED_NOT_PUBLIC"
PRE_G2_STATUS = "PRE_G2"

_FORBIDDEN_PUBLIC_KEYS = {
    "abstract",
    "adjudicator_packet",
    "adjudicator_packets",
    "claim_text",
    "claims",
    "gold_label",
    "gold_labels",
    "heldout_member",
    "heldout_members",
    "heldout_membership",
    "human_label",
    "human_labels",
    "licensed_bytes",
    "member_ids",
    "membership",
    "nonce",
    "nonce_b64",
    "nonce_hex",
    "raw_bytes",
    "raw_text",
    "secret_nonce",
    "source_text",
    "test_labels",
}

_COMMON_REQUIRED_METRICS = {
    "precision",
    "recall",
    "false_negative_rate",
    "abstention_rate",
    "calibration_error",
}
_COMMON_REQUIRED_SUBGROUPS = {"language", "jurisdiction", "text_state", "edge_case_type"}

_EDGE_CASE_REQUIREMENTS = {
    "patent": {
        "positive",
        "negative",
        "deceptive_negative",
        "borderline",
        "missing_or_short_abstract",
        "multi_year",
        "multi_jurisdiction",
        "multilingual",
        "gray_capability",
    },
    "product": {
        "clinical",
        "consumer",
        "workplace",
        "research",
        "entertainment_xr",
        "wellness",
        "ambiguous_biosignal",
        "nontraditional_form_factor",
        "multilingual",
        "multi_jurisdiction",
    },
}


class BenchmarkContractError(ValueError):
    """Raised when a PRE-G2 benchmark contract violates a control boundary."""


def _reject_non_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise BenchmarkContractError(f"Non-finite number at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_non_finite(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_non_finite(child, f"{path}[{index}]")


def canonical_json_bytes(payload: Any) -> bytes:
    """Return the exact canonical bytes used by PRE-G2 commitment tooling."""
    _reject_non_finite(payload)
    try:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise BenchmarkContractError(f"Payload is not canonical JSON data: {exc}") from exc
    return text.encode("utf-8")


def create_commitment(
    payload: Any,
    *,
    nonce: bytes,
    domain_separator: str,
    split: str,
) -> dict[str, str]:
    """Create a domain-separated salted commitment without exposing the nonce."""
    if len(nonce) < 32:
        raise BenchmarkContractError("Commitment nonce must contain at least 32 bytes of entropy")
    if not domain_separator or not domain_separator.isascii():
        raise BenchmarkContractError("domain_separator must be non-empty ASCII")
    if not split:
        raise BenchmarkContractError("split must be non-empty")
    canonical = canonical_json_bytes(payload)
    material = (
        COMMITMENT_SCHEME.encode("ascii")
        + b"\x00"
        + domain_separator.encode("ascii")
        + b"\x00"
        + canonical
        + b"\x00"
        + nonce
    )
    return {
        "split": split,
        "scheme": COMMITMENT_SCHEME,
        "digest": hashlib.sha256(material).hexdigest(),
        "domain_separator": domain_separator,
        "canonicalization": CANONICALIZATION,
        "nonce_disposition": NONCE_DISPOSITION,
    }


def _walk_public_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_PUBLIC_KEYS:
                raise BenchmarkContractError(f"Forbidden S3/held-out field {key!r} at {path}")
            _walk_public_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk_public_keys(child, f"{path}[{index}]")


def assert_public_manifest_has_no_s3_leakage(manifest: Mapping[str, Any]) -> None:
    """Fail closed if a public S1 manifest carries protected benchmark material."""
    _walk_public_keys(manifest)


def _schema_for(kind: str) -> Mapping[str, Any]:
    if kind not in {"patent", "product"}:
        raise BenchmarkContractError(f"Unsupported benchmark_kind: {kind!r}")
    resource = files("neuroai_workbench.resources.benchmarks").joinpath(
        f"{kind.upper()}_BENCHMARK_MANIFEST.schema.json"
    )
    return json.loads(resource.read_text(encoding="utf-8"))


def _format_schema_errors(errors: Sequence[Any]) -> str:
    formatted: list[str] = []
    for error in errors:
        path = "$"
        if error.absolute_path:
            path += "." + ".".join(str(part) for part in error.absolute_path)
        formatted.append(f"{path}: {error.message}")
    return "; ".join(formatted)


def validate_public_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate one public PRE-G2 manifest without granting any scientific status."""
    assert_public_manifest_has_no_s3_leakage(manifest)
    kind = str(manifest.get("benchmark_kind", ""))
    validator = Draft202012Validator(_schema_for(kind))
    errors = sorted(
        validator.iter_errors(manifest),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise BenchmarkContractError(_format_schema_errors(errors))

    if manifest["status"] != PRE_G2_STATUS:
        raise BenchmarkContractError("Only PRE_G2 manifests are accepted by this scaffold")
    if manifest["g1_approved"] or manifest["g2_frozen"]:
        raise BenchmarkContractError("PRE-G2 scaffold cannot claim G1 approval or G2 freeze")
    if manifest["contains_real_heldout_labels"]:
        raise BenchmarkContractError("Public S1 manifest cannot contain real held-out labels")
    if manifest["split_commitment_state"] == "CREATED":
        if not manifest["split_commitments"]:
            raise BenchmarkContractError("CREATED split commitments require at least one descriptor")
    elif manifest["split_commitments"]:
        raise BenchmarkContractError("Pre-commitment state cannot carry split commitment descriptors")

    for descriptor in manifest["split_commitments"]:
        if descriptor["nonce_disposition"] != NONCE_DISPOSITION:
            raise BenchmarkContractError("Commitment nonce must remain controlled in S3")
        if descriptor["scheme"] != COMMITMENT_SCHEME:
            raise BenchmarkContractError("Unsupported commitment scheme")
        if descriptor["canonicalization"] != CANONICALIZATION:
            raise BenchmarkContractError("Unsupported canonicalization")

    adjudication = manifest["adjudication_contract"]
    if adjudication["label_authority"] != "HUMAN_ADJUDICATION_ONLY":
        raise BenchmarkContractError("Model output cannot be label authority")
    if adjudication["model_output_role"] != "UNTRUSTED_DRAFT_ONLY":
        raise BenchmarkContractError("Model output role must remain untrusted draft only")

    metrics = set(manifest["metrics_contract"]["required_metrics"])
    if not _COMMON_REQUIRED_METRICS.issubset(metrics):
        missing = sorted(_COMMON_REQUIRED_METRICS - metrics)
        raise BenchmarkContractError(f"Missing required metrics: {missing}")
    subgroups = set(manifest["metrics_contract"]["required_subgroup_dimensions"])
    if not _COMMON_REQUIRED_SUBGROUPS.issubset(subgroups):
        missing = sorted(_COMMON_REQUIRED_SUBGROUPS - subgroups)
        raise BenchmarkContractError(f"Missing required subgroup dimensions: {missing}")

    edge_cases = set(manifest["subgroup_contract"]["required_edge_case_types"])
    missing_edge_cases = sorted(_EDGE_CASE_REQUIREMENTS[kind] - edge_cases)
    if missing_edge_cases:
        raise BenchmarkContractError(f"Missing {kind} edge-case requirements: {missing_edge_cases}")


def validate_synthetic_fixture(fixture: Mapping[str, Any]) -> None:
    """Validate a test-only fixture while keeping model output distinct from human labels."""
    if fixture.get("synthetic") is not True:
        raise BenchmarkContractError("Repository benchmark fixtures must be explicitly synthetic")
    if fixture.get("benchmark_status") != "SYNTHETIC_TEST_ONLY":
        raise BenchmarkContractError("Synthetic fixture cannot claim frozen benchmark status")
    if fixture.get("benchmark_kind") not in {"patent", "product"}:
        raise BenchmarkContractError("Synthetic fixture benchmark_kind must be patent or product")

    annotations = fixture.get("human_annotations")
    if not isinstance(annotations, list) or not annotations:
        raise BenchmarkContractError("Synthetic fixture requires human_annotations")
    adjudication = fixture.get("adjudication")
    if not isinstance(adjudication, Mapping):
        raise BenchmarkContractError("Synthetic fixture requires an adjudication object")
    if adjudication.get("basis") != "HUMAN_SYNTHETIC_ANNOTATIONS":
        raise BenchmarkContractError("Synthetic adjudication must be human-annotation based")

    model_outputs = fixture.get("model_outputs", [])
    if not isinstance(model_outputs, list):
        raise BenchmarkContractError("model_outputs must be a list")
    for output in model_outputs:
        if not isinstance(output, Mapping):
            raise BenchmarkContractError("Each model output must be an object")
        if output.get("authority") != "UNTRUSTED_DRAFT_ONLY":
            raise BenchmarkContractError("Synthetic model outputs must remain untrusted drafts")
