from __future__ import annotations

import hashlib
import hmac
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


class BenchmarkContractError(ValueError):
    """Raised when benchmark or evaluation metadata violates the controlled contract."""


SCHEMA_VERSION = "0.1"
COMMITMENT_SCHEME = "HMAC_SHA256_DOMAIN_CANONICAL_JSON_V1"
BENCHMARK_KINDS = frozenset({"PATENT", "PRODUCT"})
BENCHMARK_STATES = frozenset({"DRAFT_UNFROZEN", "FROZEN_COMMITMENTS_ONLY"})
G1_GATE_STATES = frozenset({"NOT_APPROVED", "APPROVED_REFERENCE_PROVIDED"})
PREDICTION_LABELS = frozenset({"POSITIVE", "NEGATIVE", "ABSTAIN"})
GOLD_LABELS = frozenset({"POSITIVE", "NEGATIVE", "UNRESOLVED"})
ADJUDICATION_STATES = frozenset(
    {
        "AGREE",
        "DISAGREE_UNADJUDICATED",
        "ADJUDICATED",
        "ABSTAIN_UNRESOLVED",
    }
)
# Recommended public domain labels for membership versus label commitments.
MEMBERSHIP_DOMAIN_SEPARATOR = "NEUROAI:PRE_G2:MEMBERSHIP:V1"
LABEL_DOMAIN_SEPARATOR = "NEUROAI:PRE_G2:LABEL:V1"

REQUIRED_STRATA: dict[str, frozenset[str]] = {
    "PATENT": frozenset(
        {
            "POSITIVE",
            "NEGATIVE",
            "SEMANTICALLY_DECEPTIVE_NEGATIVE",
            "BORDERLINE",
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
        "required_strata",
        "double_label_subset_required",
        "adjudication_states",
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

    strata = contract.get("required_strata")
    if not isinstance(strata, list) or any(not isinstance(item, str) for item in strata):
        raise BenchmarkContractError("required_strata must be a list of strings")
    if len(strata) != len(set(strata)):
        raise BenchmarkContractError("required_strata must not contain duplicates")
    missing = REQUIRED_STRATA[kind] - set(strata)
    if missing:
        raise BenchmarkContractError(f"required_strata is missing: {', '.join(sorted(missing))}")

    if contract.get("double_label_subset_required") is not True:
        raise BenchmarkContractError("double_label_subset_required must be true")

    states = contract.get("adjudication_states")
    states_valid = isinstance(states, list) and len(states) == len(set(states)) and set(states) == ADJUDICATION_STATES
    if not states_valid:
        raise BenchmarkContractError("adjudication_states must preserve the complete controlled state set")

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
    """Reject prediction payloads that contain held-out oracle fields or malformed outputs."""

    seen: set[str] = set()
    for index, row in enumerate(rows):
        _guard_prediction_value(row, f"rows[{index}]")
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise BenchmarkContractError("Each prediction row requires a non-empty item_id")
        if item_id in seen:
            raise BenchmarkContractError(f"Duplicate prediction item_id: {item_id}")
        seen.add(item_id)
        label = row.get("prediction")
        if label not in PREDICTION_LABELS:
            raise BenchmarkContractError(f"prediction must be one of {sorted(PREDICTION_LABELS)}")
        probability = row.get("probability_positive")
        if probability is not None:
            if not isinstance(probability, (int, float)) or isinstance(probability, bool):
                raise BenchmarkContractError("probability_positive must be numeric when supplied")
            probability_value = float(probability)
            if not math.isfinite(probability_value) or not 0.0 <= probability_value <= 1.0:
                raise BenchmarkContractError("probability_positive must be finite and between 0 and 1")


def _validate_gold_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise BenchmarkContractError("Each controlled gold row requires a non-empty item_id")
        if item_id in indexed:
            raise BenchmarkContractError(f"Duplicate controlled gold item_id: {item_id}")

        state = row.get("adjudication_state")
        label = row.get("gold_label")
        if state not in ADJUDICATION_STATES:
            raise BenchmarkContractError(f"Unknown adjudication_state for {item_id}")
        if label not in GOLD_LABELS:
            raise BenchmarkContractError(f"Unknown gold_label for {item_id}")
        if state in {"DISAGREE_UNADJUDICATED", "ABSTAIN_UNRESOLVED"} and label != "UNRESOLVED":
            raise BenchmarkContractError(f"Unresolved adjudication for {item_id} cannot carry a binary gold label")
        if state in {"AGREE", "ADJUDICATED"} and label == "UNRESOLVED":
            raise BenchmarkContractError(f"Resolved adjudication for {item_id} requires a binary gold label")
        indexed[item_id] = row
    return indexed


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _score_subset(
    item_ids: Iterable[str],
    gold_by_id: Mapping[str, Mapping[str, Any]],
    prediction_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    total = 0
    positive_gold = 0
    negative_gold = 0
    true_positive = 0
    false_positive = 0
    false_negative_answered = 0
    explicit_abstention = 0
    missing_prediction = 0
    positive_abstention_or_missing = 0
    answered = 0
    brier_sum = 0.0
    probability_count = 0

    for item_id in item_ids:
        gold = gold_by_id[item_id]
        gold_label = gold["gold_label"]
        if gold_label == "UNRESOLVED":
            continue
        total += 1
        positive_gold += int(gold_label == "POSITIVE")
        negative_gold += int(gold_label == "NEGATIVE")
        prediction_row = prediction_by_id.get(item_id)
        if prediction_row is None:
            missing_prediction += 1
            if gold_label == "POSITIVE":
                positive_abstention_or_missing += 1
            continue

        prediction = prediction_row["prediction"]
        if prediction == "ABSTAIN":
            explicit_abstention += 1
            if gold_label == "POSITIVE":
                positive_abstention_or_missing += 1
        else:
            answered += 1
            if prediction == "POSITIVE" and gold_label == "POSITIVE":
                true_positive += 1
            elif prediction == "POSITIVE" and gold_label == "NEGATIVE":
                false_positive += 1
            elif prediction == "NEGATIVE" and gold_label == "POSITIVE":
                false_negative_answered += 1

        probability = prediction_row.get("probability_positive")
        if probability is not None:
            target = 1.0 if gold_label == "POSITIVE" else 0.0
            brier_sum += (float(probability) - target) ** 2
            probability_count += 1

    effective_false_negative = false_negative_answered + positive_abstention_or_missing
    return {
        "scoreable_count": total,
        "positive_gold_count": positive_gold,
        "negative_gold_count": negative_gold,
        "answered_count": answered,
        "explicit_abstention_count": explicit_abstention,
        "missing_prediction_count": missing_prediction,
        "coverage": _safe_ratio(answered, total),
        "precision": _safe_ratio(true_positive, true_positive + false_positive),
        "recall": _safe_ratio(true_positive, positive_gold),
        "false_negative_rate": _safe_ratio(effective_false_negative, positive_gold),
        "probability_coverage": _safe_ratio(probability_count, total),
        "brier_score": _safe_ratio(brier_sum, probability_count),
        "confusion": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative_answered": false_negative_answered,
            "positive_abstention_or_missing": positive_abstention_or_missing,
        },
    }


def _normalize_subgroup_values(value: Any) -> list[str]:
    if value is None:
        return ["UNKNOWN"]
    if isinstance(value, str):
        return [value or "UNKNOWN"]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value or ["UNKNOWN"]
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
    """Compute metrics; the caller remains responsible for S3 custody of gold rows."""

    validate_prediction_rows(prediction_rows)
    gold_by_id = _validate_gold_rows(controlled_gold_rows)
    prediction_by_id = {row["item_id"]: row for row in prediction_rows}
    unexpected = set(prediction_by_id) - set(gold_by_id)
    if unexpected:
        raise BenchmarkContractError(
            f"Predictions contain item_ids outside the controlled benchmark: {sorted(unexpected)}"
        )

    scoreable_ids = [item_id for item_id, row in gold_by_id.items() if row["gold_label"] != "UNRESOLVED"]
    unresolved_count = len(gold_by_id) - len(scoreable_ids)
    overall = _score_subset(scoreable_ids, gold_by_id, prediction_by_id)

    subgroup_metrics: dict[str, dict[str, Any]] = {}
    for field in subgroup_fields:
        groups: dict[str, list[str]] = {}
        for item_id in scoreable_ids:
            for value in _normalize_subgroup_values(gold_by_id[item_id].get(field)):
                groups.setdefault(value, []).append(item_id)
        subgroup_metrics[field] = {
            value: _score_subset(item_ids, gold_by_id, prediction_by_id) for value, item_ids in sorted(groups.items())
        }

    return {
        "boundary": (
            "Aggregate software metrics over caller-supplied controlled labels; no scientific "
            "truth, G2 approval, canonical S2 authority, publication authority, or v4.2 "
            "assessment effect is created."
        ),
        "total_gold_rows": len(gold_by_id),
        "unresolved_gold_count": unresolved_count,
        "overall": overall,
        "subgroups": subgroup_metrics,
    }
