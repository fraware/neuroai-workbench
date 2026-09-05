from __future__ import annotations

import hashlib
import hmac
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


class BenchmarkContractError(ValueError):
    """Raised when benchmark or evaluation metadata violates the controlled contract."""


SCHEMA_VERSION = "0.2"
COMMITMENT_SCHEME = "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1"
BENCHMARK_KINDS = frozenset({"PATENT", "PRODUCT"})
BENCHMARK_STATES = frozenset({"DRAFT_UNFROZEN", "FROZEN_COMMITMENTS_ONLY"})
G1_GATE_STATES = frozenset({"NOT_APPROVED", "APPROVED_REFERENCE_PROVIDED"})

APPROVED_D1_CANONICAL_SHA256 = "7d270002094dcdecb703d5b70ef2268e4869005c284ffd98db3eb936641a78cb"
BOUNDARY_DISPOSITIONS = frozenset({"INCLUDE", "EXCLUDE", "BORDERLINE", "ABSTAIN"})
REQUIRED_BOUNDARY_DISPOSITIONS = frozenset({"INCLUDE", "EXCLUDE", "BORDERLINE"})
RESOLVED_ADJUDICATION_STATES = frozenset({"AGREE", "ADJUDICATED"})
UNRESOLVED_ADJUDICATION_STATE = "DISAGREE_UNADJUDICATED"
ADJUDICATION_STATES = frozenset({*RESOLVED_ADJUDICATION_STATES, UNRESOLVED_ADJUDICATION_STATE})

BINARY_PROJECTION_ID = "D1_INCLUDE_EXCLUDE_BINARY_V1"
BINARY_POSITIVE_DISPOSITION = "INCLUDE"
BINARY_NEGATIVE_DISPOSITION = "EXCLUDE"
BINARY_EXCLUDED_HUMAN_DISPOSITIONS = frozenset({"BORDERLINE", "ABSTAIN"})

# Compatibility symbols retained for import stability. Their values now reflect
# the D1-governed four-way boundary domain; legacy POSITIVE/NEGATIVE gold labels
# are intentionally not accepted by the v0.2 evaluator.
PREDICTION_LABELS = BOUNDARY_DISPOSITIONS
GOLD_LABELS = BOUNDARY_DISPOSITIONS

# Recommended public domain labels for membership versus label commitments.
MEMBERSHIP_DOMAIN_SEPARATOR = "NEUROAI:PRE_G2:MEMBERSHIP:V1"
LABEL_DOMAIN_SEPARATOR = "NEUROAI:PRE_G2:LABEL:V1"

REQUIRED_STRATA: dict[str, frozenset[str]] = {
    "PATENT": frozenset(
        {
            "SEMANTICALLY_DECEPTIVE_NEGATIVE",
            "MISSING_OR_SHORT_ABSTRACT",
            "MULTI_YEAR",
            "MULTI_JURISDICTION",
            "MULTILINGUAL",
            "GRAY_CAPABILITY",
        }
    ),
    "PRODUCT": frozenset(
        {
            "CLINICAL",
            "CONSUMER",
            "WORKPLACE",
            "RESEARCH",
            "ENTERTAINMENT_XR",
            "WELLNESS",
            "AMBIGUOUS_BIOSIGNAL",
            "NONTRADITIONAL_FORM_FACTOR",
            "MULTILINGUAL",
            "MULTI_JURISDICTION",
        }
    ),
}

PUBLIC_CONTRACT_FIELDS = frozenset(
    {
        "schema_version",
        "benchmark_id",
        "benchmark_kind",
        "state",
        "g1_gate_state",
        "g1_disposition_id",
        "g1_disposition_sha256",
        "g2_passed",
        "canonical_s2_authority",
        "publication_authority",
        "assessment_effect",
        "private_membership_location",
        "private_labels_location",
        "commitment_scheme",
        "membership_commitment",
        "label_commitment",
        "boundary_semantics",
        "required_strata",
        "double_label_subset_required",
        "adjudication_states",
    }
)

_BOUNDARY_SEMANTICS_FIELDS = frozenset(
    {
        "source_d1_canonical_json_sha256",
        "allowed_dispositions",
        "required_g2_coverage_dispositions",
        "resolved_adjudication_states",
        "unresolved_adjudication_state",
        "rationale_required",
        "binary_projection",
    }
)

_BINARY_PROJECTION_FIELDS = frozenset(
    {
        "projection_id",
        "positive_disposition",
        "negative_disposition",
        "excluded_human_dispositions",
        "model_prediction_domain",
        "unresolved_adjudication_excluded_from_binary_metrics",
        "model_borderline_on_human_include_counts_as_effective_false_negative",
        "model_abstain_on_human_include_counts_as_effective_false_negative",
        "missing_prediction_on_human_include_counts_as_effective_false_negative",
        "probability_field",
    }
)

PROHIBITED_PREDICTION_KEYS = frozenset(
    {
        "abstract",
        "adjudicated_label",
        "adjudication_outcome",
        "adjudication_state",
        "adjudicator_decision",
        "adjudicator_packet",
        "adjudicator_packets",
        "answer_key",
        "benchmark_membership",
        "boundary_disposition",
        "claim_text",
        "final_boundary_disposition",
        "gold",
        "gold_boundary_disposition",
        "gold_label",
        "gold_labels",
        "gold_rationale",
        "ground_truth",
        "held_out",
        "held_out_member",
        "heldout_member",
        "heldout_members",
        "heldout_membership",
        "holdout_member",
        "human_boundary_disposition",
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
        "reviewer_dispositions",
        "reviewer_labels",
        "secret_nonce",
        "source_text",
        "test_labels",
        "true_label",
        "truth",
    }
)

_LEGACY_GOLD_KEYS = frozenset({"gold_label", "final_label"})


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON-compatible content deterministically for controlled commitments."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise BenchmarkContractError("Commitment payload must be finite JSON-compatible data") from exc
    return encoded.encode("utf-8")


def keyed_commitment(
    payload: Any,
    secret_key: bytes,
    *,
    domain_separator: str,
) -> str:
    """Return an opaque domain-separated HMAC-SHA256 commitment.

    The secret key must stay in controlled S3. Domain separators prevent
    cross-context reuse of identical payloads (for example membership versus
    label commitments, or D3 versus D4).
    """

    if not isinstance(secret_key, bytes) or len(secret_key) < 32:
        raise BenchmarkContractError("Commitment key must contain at least 32 bytes and remain in controlled S3")
    if not isinstance(domain_separator, str) or not domain_separator:
        raise BenchmarkContractError("domain_separator must be a non-empty string")
    if not domain_separator.isascii():
        raise BenchmarkContractError("domain_separator must be ASCII")
    material = (
        COMMITMENT_SCHEME.encode("ascii")
        + b"\x00"
        + domain_separator.encode("ascii")
        + b"\x00"
        + canonical_json_bytes(payload)
    )
    return hmac.new(secret_key, material, hashlib.sha256).hexdigest()


def _is_sha256_hex(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _exact_string_set(value: Any, expected: frozenset[str]) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and len(value) == len(set(value))
        and set(value) == expected
    )


def _validate_boundary_semantics_contract(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise BenchmarkContractError("boundary_semantics must be an object")
    unexpected = set(value) - _BOUNDARY_SEMANTICS_FIELDS
    missing = _BOUNDARY_SEMANTICS_FIELDS - set(value)
    if unexpected or missing:
        raise BenchmarkContractError("boundary_semantics must contain the exact v0.2 controlled field set")
    if value.get("source_d1_canonical_json_sha256") != APPROVED_D1_CANONICAL_SHA256:
        raise BenchmarkContractError("boundary_semantics must bind the exact approved D1 canonical JSON SHA-256")
    if not _exact_string_set(value.get("allowed_dispositions"), BOUNDARY_DISPOSITIONS):
        raise BenchmarkContractError("allowed_dispositions must preserve the exact D1 four-way boundary domain")
    if not _exact_string_set(value.get("required_g2_coverage_dispositions"), REQUIRED_BOUNDARY_DISPOSITIONS):
        raise BenchmarkContractError("required_g2_coverage_dispositions must require INCLUDE, EXCLUDE, and BORDERLINE")
    if not _exact_string_set(value.get("resolved_adjudication_states"), RESOLVED_ADJUDICATION_STATES):
        raise BenchmarkContractError("resolved_adjudication_states must be AGREE and ADJUDICATED")
    if value.get("unresolved_adjudication_state") != UNRESOLVED_ADJUDICATION_STATE:
        raise BenchmarkContractError("unresolved_adjudication_state must preserve unresolved reviewer disagreement")
    if value.get("rationale_required") is not True:
        raise BenchmarkContractError("boundary dispositions require recorded rationale")

    projection = value.get("binary_projection")
    if not isinstance(projection, Mapping):
        raise BenchmarkContractError("binary_projection must be an object")
    if set(projection) != _BINARY_PROJECTION_FIELDS:
        raise BenchmarkContractError("binary_projection must contain the exact v0.2 controlled field set")
    if projection.get("projection_id") != BINARY_PROJECTION_ID:
        raise BenchmarkContractError("binary_projection projection_id is not the controlled v0.2 projection")
    if projection.get("positive_disposition") != BINARY_POSITIVE_DISPOSITION:
        raise BenchmarkContractError("binary_projection positive_disposition must be INCLUDE")
    if projection.get("negative_disposition") != BINARY_NEGATIVE_DISPOSITION:
        raise BenchmarkContractError("binary_projection negative_disposition must be EXCLUDE")
    if not _exact_string_set(projection.get("excluded_human_dispositions"), BINARY_EXCLUDED_HUMAN_DISPOSITIONS):
        raise BenchmarkContractError("binary_projection must exclude human BORDERLINE and ABSTAIN from binary metrics")
    if not _exact_string_set(projection.get("model_prediction_domain"), BOUNDARY_DISPOSITIONS):
        raise BenchmarkContractError("binary_projection model_prediction_domain must preserve four-way routing")
    for field in (
        "unresolved_adjudication_excluded_from_binary_metrics",
        "model_borderline_on_human_include_counts_as_effective_false_negative",
        "model_abstain_on_human_include_counts_as_effective_false_negative",
        "missing_prediction_on_human_include_counts_as_effective_false_negative",
    ):
        if projection.get(field) is not True:
            raise BenchmarkContractError(f"binary_projection {field} must remain true")
    if projection.get("probability_field") != "probability_include":
        raise BenchmarkContractError("binary_projection probability_field must be probability_include")


def validate_public_benchmark_contract(contract: Mapping[str, Any]) -> None:
    """Validate the public PRE-G2 contract without reading held-out membership or labels."""

    unexpected_fields = set(contract) - PUBLIC_CONTRACT_FIELDS
    if unexpected_fields:
        raise BenchmarkContractError(
            f"Public benchmark contract contains unsupported fields: {', '.join(sorted(unexpected_fields))}"
        )

    if contract.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkContractError(f"schema_version must be {SCHEMA_VERSION}")

    benchmark_id = contract.get("benchmark_id")
    if not isinstance(benchmark_id, str) or not benchmark_id.strip():
        raise BenchmarkContractError("benchmark_id must be a non-empty string")

    kind = contract.get("benchmark_kind")
    if kind not in BENCHMARK_KINDS:
        raise BenchmarkContractError(f"benchmark_kind must be one of {sorted(BENCHMARK_KINDS)}")

    state = contract.get("state")
    if state not in BENCHMARK_STATES:
        raise BenchmarkContractError(f"state must be one of {sorted(BENCHMARK_STATES)}")

    g1_gate_state = contract.get("g1_gate_state")
    if g1_gate_state not in G1_GATE_STATES:
        raise BenchmarkContractError(f"g1_gate_state must be one of {sorted(G1_GATE_STATES)}")
    g1_disposition_id = contract.get("g1_disposition_id")
    g1_disposition_sha256 = contract.get("g1_disposition_sha256")
    if g1_gate_state == "NOT_APPROVED":
        if g1_disposition_id is not None or g1_disposition_sha256 is not None:
            raise BenchmarkContractError("NOT_APPROVED G1 state cannot carry a governance disposition binding")
    else:
        if not isinstance(g1_disposition_id, str) or not g1_disposition_id.strip():
            raise BenchmarkContractError("Approved G1 reference requires a non-empty g1_disposition_id")
        if not _is_sha256_hex(g1_disposition_sha256):
            raise BenchmarkContractError("Approved G1 reference requires a SHA-256-format g1_disposition_sha256")

    if contract.get("g2_passed") is not False:
        raise BenchmarkContractError("g2_passed must remain false in PRE-G2 public benchmark contracts")
    if contract.get("canonical_s2_authority") is not False:
        raise BenchmarkContractError("canonical_s2_authority must remain false")
    if contract.get("publication_authority") is not False:
        raise BenchmarkContractError("publication_authority must remain false")
    if contract.get("assessment_effect") not in {None, "NONE"}:
        raise BenchmarkContractError("assessment_effect must be NONE")

    if contract.get("private_membership_location") != "S3_CONTROLLED":
        raise BenchmarkContractError("Held-out membership must remain in S3_CONTROLLED")
    if contract.get("private_labels_location") != "S3_CONTROLLED":
        raise BenchmarkContractError("Held-out labels must remain in S3_CONTROLLED")
    if contract.get("commitment_scheme") != COMMITMENT_SCHEME:
        raise BenchmarkContractError(f"commitment_scheme must be {COMMITMENT_SCHEME}")

    _validate_boundary_semantics_contract(contract.get("boundary_semantics"))

    strata = contract.get("required_strata")
    if not isinstance(strata, list) or any(not isinstance(item, str) for item in strata):
        raise BenchmarkContractError("required_strata must be a list of strings")
    if len(strata) != len(set(strata)):
        raise BenchmarkContractError("required_strata must not contain duplicates")
    if set(strata) != REQUIRED_STRATA[kind]:
        missing = REQUIRED_STRATA[kind] - set(strata)
        unexpected = set(strata) - REQUIRED_STRATA[kind]
        details = []
        if missing:
            details.append(f"missing {', '.join(sorted(missing))}")
        if unexpected:
            details.append(f"unexpected {', '.join(sorted(unexpected))}")
        raise BenchmarkContractError(f"required_strata must match the controlled {kind} set: {'; '.join(details)}")

    if contract.get("double_label_subset_required") is not True:
        raise BenchmarkContractError("double_label_subset_required must be true")

    states = contract.get("adjudication_states")
    if not _exact_string_set(states, ADJUDICATION_STATES):
        raise BenchmarkContractError(
            "adjudication_states must preserve resolved review separately from unresolved disagreement"
        )

    membership_commitment = contract.get("membership_commitment")
    label_commitment = contract.get("label_commitment")
    if state == "DRAFT_UNFROZEN":
        if membership_commitment is not None or label_commitment is not None:
            raise BenchmarkContractError("DRAFT_UNFROZEN contracts must not claim frozen commitments")
    else:
        if g1_gate_state != "APPROVED_REFERENCE_PROVIDED":
            raise BenchmarkContractError("FROZEN_COMMITMENTS_ONLY requires an approved G1 disposition reference")
        if not _is_sha256_hex(membership_commitment) or not _is_sha256_hex(label_commitment):
            raise BenchmarkContractError("FROZEN_COMMITMENTS_ONLY contracts require SHA-256-format commitments")


def _guard_prediction_value(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in PROHIBITED_PREDICTION_KEYS:
                raise BenchmarkContractError(f"Prediction payload contains prohibited oracle field at {path}.{key}")
            _guard_prediction_value(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _guard_prediction_value(child, f"{path}[{index}]")


def validate_prediction_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    """Validate four-way model routing while rejecting held-out oracle leakage."""

    seen: set[str] = set()
    for index, row in enumerate(rows):
        if "prediction" in row:
            raise BenchmarkContractError(
                "Legacy prediction field is not accepted in v0.2; use boundary_prediction with D1 dispositions"
            )
        if "probability_positive" in row:
            raise BenchmarkContractError(
                "Legacy probability_positive field is not accepted in v0.2; use probability_include"
            )
        _guard_prediction_value(row, f"rows[{index}]")
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise BenchmarkContractError("Each prediction row requires a non-empty item_id")
        if item_id in seen:
            raise BenchmarkContractError(f"Duplicate prediction item_id: {item_id}")
        seen.add(item_id)
        prediction = row.get("boundary_prediction")
        if prediction not in BOUNDARY_DISPOSITIONS:
            raise BenchmarkContractError(f"boundary_prediction must be one of {sorted(BOUNDARY_DISPOSITIONS)}")
        probability = row.get("probability_include")
        if probability is not None:
            if not isinstance(probability, (int, float)) or isinstance(probability, bool):
                raise BenchmarkContractError("probability_include must be numeric when supplied")
            probability_value = float(probability)
            if not math.isfinite(probability_value) or not 0.0 <= probability_value <= 1.0:
                raise BenchmarkContractError("probability_include must be finite and between 0 and 1")


def _validate_gold_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        legacy = _LEGACY_GOLD_KEYS & set(row)
        if legacy:
            raise BenchmarkContractError(
                "Legacy binary gold fields are not accepted in v0.2; use boundary_disposition and adjudication_state"
            )
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise BenchmarkContractError("Each controlled gold row requires a non-empty item_id")
        if item_id in indexed:
            raise BenchmarkContractError(f"Duplicate controlled gold item_id: {item_id}")

        state = row.get("adjudication_state")
        disposition = row.get("boundary_disposition")
        rationale = row.get("rationale")
        if state not in ADJUDICATION_STATES:
            raise BenchmarkContractError(f"Unknown adjudication_state for {item_id}")
        if not isinstance(rationale, str) or not rationale.strip():
            raise BenchmarkContractError(f"Controlled gold row {item_id} requires recorded rationale")
        if state == UNRESOLVED_ADJUDICATION_STATE:
            if disposition is not None:
                raise BenchmarkContractError(
                    f"Unresolved reviewer disagreement for {item_id} cannot carry a governed boundary disposition"
                )
        elif disposition not in BOUNDARY_DISPOSITIONS:
            raise BenchmarkContractError(
                f"Resolved adjudication for {item_id} requires one of {sorted(BOUNDARY_DISPOSITIONS)}"
            )
        indexed[item_id] = row
    return indexed


def validate_controlled_gold_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    """Validate controlled human dispositions without exposing or persisting them."""

    _validate_gold_rows(rows)


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _distribution(ids: Iterable[str], prediction_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    counts = {disposition: 0 for disposition in sorted(BOUNDARY_DISPOSITIONS)}
    counts["MISSING"] = 0
    for item_id in ids:
        prediction_row = prediction_by_id.get(item_id)
        if prediction_row is None:
            counts["MISSING"] += 1
        else:
            counts[str(prediction_row["boundary_prediction"])] += 1
    return counts


def _routing_summary(
    item_ids: Sequence[str],
    prediction_by_id: Mapping[str, Mapping[str, Any]],
    *,
    target_disposition: str,
) -> dict[str, Any]:
    counts = _distribution(item_ids, prediction_by_id)
    total = len(item_ids)
    return {
        "human_disposition": target_disposition,
        "count": total,
        "model_routing_counts": counts,
        "exact_route_rate": _safe_ratio(counts[target_disposition], total),
    }


def _score_subset(
    item_ids: Iterable[str],
    gold_by_id: Mapping[str, Mapping[str, Any]],
    prediction_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    ids = list(item_ids)
    resolved_ids = [
        item_id for item_id in ids if gold_by_id[item_id]["adjudication_state"] in RESOLVED_ADJUDICATION_STATES
    ]
    unresolved_ids = [
        item_id for item_id in ids if gold_by_id[item_id]["adjudication_state"] == UNRESOLVED_ADJUDICATION_STATE
    ]

    disposition_ids: dict[str, list[str]] = {
        disposition: [item_id for item_id in resolved_ids if gold_by_id[item_id]["boundary_disposition"] == disposition]
        for disposition in sorted(BOUNDARY_DISPOSITIONS)
    }
    human_counts = {disposition: len(group) for disposition, group in disposition_ids.items()}

    binary_ids = disposition_ids[BINARY_POSITIVE_DISPOSITION] + disposition_ids[BINARY_NEGATIVE_DISPOSITION]
    include_count = len(disposition_ids[BINARY_POSITIVE_DISPOSITION])
    exclude_count = len(disposition_ids[BINARY_NEGATIVE_DISPOSITION])
    true_positive = 0
    true_negative = 0
    false_positive = 0
    false_negative_answered = 0
    include_routed_borderline = 0
    include_routed_abstain = 0
    include_missing = 0
    binary_answered = 0
    model_borderline_routes = 0
    model_abstain_routes = 0
    missing_prediction = 0
    brier_sum = 0.0
    probability_count = 0

    for item_id in binary_ids:
        human = str(gold_by_id[item_id]["boundary_disposition"])
        prediction_row = prediction_by_id.get(item_id)
        if prediction_row is None:
            missing_prediction += 1
            if human == BINARY_POSITIVE_DISPOSITION:
                include_missing += 1
            continue

        prediction = str(prediction_row["boundary_prediction"])
        if prediction in {BINARY_POSITIVE_DISPOSITION, BINARY_NEGATIVE_DISPOSITION}:
            binary_answered += 1
            if human == BINARY_POSITIVE_DISPOSITION and prediction == BINARY_POSITIVE_DISPOSITION:
                true_positive += 1
            elif human == BINARY_NEGATIVE_DISPOSITION and prediction == BINARY_NEGATIVE_DISPOSITION:
                true_negative += 1
            elif human == BINARY_NEGATIVE_DISPOSITION and prediction == BINARY_POSITIVE_DISPOSITION:
                false_positive += 1
            elif human == BINARY_POSITIVE_DISPOSITION and prediction == BINARY_NEGATIVE_DISPOSITION:
                false_negative_answered += 1
        elif prediction == "BORDERLINE":
            model_borderline_routes += 1
            if human == BINARY_POSITIVE_DISPOSITION:
                include_routed_borderline += 1
        else:
            model_abstain_routes += 1
            if human == BINARY_POSITIVE_DISPOSITION:
                include_routed_abstain += 1

        probability = prediction_row.get("probability_include")
        if probability is not None:
            target = 1.0 if human == BINARY_POSITIVE_DISPOSITION else 0.0
            brier_sum += (float(probability) - target) ** 2
            probability_count += 1

    effective_false_negative = (
        false_negative_answered + include_routed_borderline + include_routed_abstain + include_missing
    )
    binary_metrics = {
        "projection_id": BINARY_PROJECTION_ID,
        "eligible_count": len(binary_ids),
        "include_count": include_count,
        "exclude_count": exclude_count,
        "answered_count": binary_answered,
        "model_borderline_route_count": model_borderline_routes,
        "model_abstain_route_count": model_abstain_routes,
        "missing_prediction_count": missing_prediction,
        "coverage": _safe_ratio(binary_answered, len(binary_ids)),
        "precision": _safe_ratio(true_positive, true_positive + false_positive),
        "recall": _safe_ratio(true_positive, include_count),
        "false_negative_rate": _safe_ratio(effective_false_negative, include_count),
        "probability_include_coverage": _safe_ratio(probability_count, len(binary_ids)),
        "brier_score": _safe_ratio(brier_sum, probability_count),
        "confusion": {
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative_answered": false_negative_answered,
            "include_routed_borderline": include_routed_borderline,
            "include_routed_abstain": include_routed_abstain,
            "include_missing": include_missing,
        },
    }

    resolved_confusion = {
        disposition: _distribution(group, prediction_by_id) for disposition, group in disposition_ids.items()
    }
    return {
        "row_count": len(ids),
        "resolved_count": len(resolved_ids),
        "unresolved_adjudication_count": len(unresolved_ids),
        "human_disposition_counts": human_counts,
        "binary": binary_metrics,
        "routing": {
            "human_borderline": _routing_summary(
                disposition_ids["BORDERLINE"], prediction_by_id, target_disposition="BORDERLINE"
            ),
            "human_abstain": _routing_summary(
                disposition_ids["ABSTAIN"], prediction_by_id, target_disposition="ABSTAIN"
            ),
            "resolved_confusion": resolved_confusion,
            "unresolved_adjudication_prediction_counts": _distribution(unresolved_ids, prediction_by_id),
        },
    }


def _normalize_subgroup_values(value: Any) -> list[str]:
    if value is None:
        return ["UNKNOWN"]
    if isinstance(value, str):
        return [value or "UNKNOWN"]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        normalized = [item or "UNKNOWN" for item in value] or ["UNKNOWN"]
        return list(dict.fromkeys(normalized))
    raise BenchmarkContractError("Subgroup values must be strings, lists of strings, or null")


def score_predictions(
    prediction_rows: Sequence[Mapping[str, Any]],
    controlled_gold_rows: Sequence[Mapping[str, Any]],
    *,
    subgroup_fields: Sequence[str] = (
        "strata",
        "language",
        "jurisdiction",
        "text_availability",
    ),
) -> dict[str, Any]:
    """Score a versioned INCLUDE/EXCLUDE projection and report four-way routing.

    Controlled human rows remain caller-owned S3 data. Human BORDERLINE and
    ABSTAIN dispositions, plus unresolved reviewer disagreement, are never
    coerced into the binary precision/recall denominator.
    """

    validate_prediction_rows(prediction_rows)
    gold_by_id = _validate_gold_rows(controlled_gold_rows)
    prediction_by_id = {str(row["item_id"]): row for row in prediction_rows}
    unexpected = set(prediction_by_id) - set(gold_by_id)
    if unexpected:
        raise BenchmarkContractError(
            f"Predictions contain item_ids outside the controlled benchmark: {sorted(unexpected)}"
        )

    all_ids = list(gold_by_id)
    overall = _score_subset(all_ids, gold_by_id, prediction_by_id)

    subgroup_metrics: dict[str, dict[str, Any]] = {}
    for field in subgroup_fields:
        groups: dict[str, list[str]] = {}
        for item_id in all_ids:
            for value in _normalize_subgroup_values(gold_by_id[item_id].get(field)):
                groups.setdefault(value, []).append(item_id)
        subgroup_metrics[field] = {
            value: _score_subset(item_ids, gold_by_id, prediction_by_id) for value, item_ids in sorted(groups.items())
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "boundary": (
            "Aggregate software metrics over caller-supplied controlled human dispositions. "
            "The D1 four-way boundary remains authoritative; the binary projection is explicitly "
            "limited to human INCLUDE versus EXCLUDE. No scientific truth, G2 approval, canonical "
            "S2 authority, publication authority, or v4.2 assessment effect is created."
        ),
        "binary_projection": {
            "projection_id": BINARY_PROJECTION_ID,
            "positive_disposition": BINARY_POSITIVE_DISPOSITION,
            "negative_disposition": BINARY_NEGATIVE_DISPOSITION,
            "excluded_human_dispositions": sorted(BINARY_EXCLUDED_HUMAN_DISPOSITIONS),
            "unresolved_adjudication_excluded": True,
        },
        "overall": overall,
        "subgroups": subgroup_metrics,
    }
