"""Validators for Release-A A-G reconstruction protocol and packet.

Freezes the A-G reconstruction checklist that binds the exact A8 Product
Population Release Package digest, then executes automated reconstruction
walks from A8 through upstream digests to source packets for each required
headline. A-G does not authorize Release B/C/D.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Any, cast

from neuroai_workbench.a3_capability_recall import A3_STUDY_PACKET_SHA256, load_default_a3_capability_recall_study
from neuroai_workbench.a4_multilingual_sensitivity import (
    A4_STUDY_PACKET_SHA256,
    load_default_a4_multilingual_sensitivity_study,
)
from neuroai_workbench.a6_saturation_analysis import A6_STUDY_PACKET_SHA256, load_default_a6_coverage_saturation_report
from neuroai_workbench.a7_population_estimation import (
    A7_STUDY_PACKET_SHA256,
    VALID_NO_ESTIMATE_OUTCOME,
    load_default_a7_population_estimation_report,
)
from neuroai_workbench.a8_release_package import (
    A8_CONTRACT_SHA256,
    A8_PACKAGE_ID,
    A8_PACKAGE_SHA256,
    CHECKPOINT_SHA256,
    D4_WORKING_DISTRIBUTION,
    F9_LEDGER_SHA256,
    N_OBSERVED,
    OBSERVED_OFFERING_IDS,
    POPULATION_VIEW_ID,
    UNRESOLVED_CANDIDATE_COUNT,
    UNRESOLVED_REGISTER_SHA256,
    load_default_a8_package_manifest_contract,
    load_default_a8_product_population_release_package,
)
from neuroai_workbench.product_discovery_frames import (
    A1_INITIAL_KNOWN_IDENTITY_SHA256,
    A2_JURISDICTION_SCOPE,
    A2_KNOWLEDGE_TIME_CUTOFF,
    A2_LANGUAGE_SCOPE_ID,
    A2_WORLD_TIME_CUTOFF,
    DEFAULT_ANALYSIS_UNIVERSE_ID,
    PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS,
    ProductDiscoveryError,
)

RESOURCE_PACKAGE = "neuroai_workbench.resources.discovery"

AG_PROTOCOL_RESOURCE = "RELEASE_A_AG_RECONSTRUCTION_PROTOCOL.v1.0.json"
AG_PROTOCOL_SCHEMA_RESOURCE = "RELEASE_A_AG_RECONSTRUCTION_PROTOCOL.schema.json"
AG_PROTOCOL_ID = "RELEASE_A_AG_RECONSTRUCTION_PROTOCOL_v1.0"
AG_STUDY_ID = "RELEASE_A_AG_RECONSTRUCTION_PACKET_v1.0"

AG_PROTOCOL_SHA256 = "5fba335b37459d0b474f9b868d14275f8bf62372332aba2d6cb1a9b565aebb76"

REQUIRED_RECONSTRUCTION_FIELDS = (
    "counted_object",
    "exact_identity",
    "source_observations",
    "source_frames",
    "language_jurisdiction_scope",
    "world_knowledge_cutoffs",
    "discovery_stopping_rule",
    "observed_vs_estimated",
    "model_assumptions",
    "uncertainty",
    "unresolved_evidence",
    "publication_authority",
)

REQUIRED_HEADLINE_IDS = (
    "N_OBSERVED_A_P1",
    "N_ESTIMATED_A_P1",
    "DELTA_N_CAPABILITY",
    "DELTA_N_MULTILINGUAL",
    "D4_WORKING_INCLUDE",
    "UNRESOLVED_CANDIDATES_RETAINED",
    "FRAME_STOP_STATE_A6",
)

AG_PROTOCOL_BOUNDARY = (
    "A-G reconstruction protocol freezes the Release-A reconstruction checklist "
    "and binds the exact A8 Product Population Release Package digest before any "
    "reconstruction packet is emitted. It requires reconstructability of the "
    "twelve declared fields for each required headline from immutable artifacts. "
    "Freeze alone does not emit a PASSED or UNPASSED A-G outcome, authorize "
    "Release B/C/D, establish S2 publication authority, or create v4.2 "
    "assessment effect. A7 fail-closed N_observed=6 with no N_estimated is "
    "preserved. F9 exhaustion is not global completeness; open-world "
    "saturation is not a census."
)


def content_digest(material: Mapping[str, Any], *, exclude: str) -> str:
    """Return deterministic SHA-256 for a freeze artifact, excluding a self-digest field."""

    payload = {key: value for key, value in material.items() if key != exclude}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_resource(resource_name: str, *, package: str = RESOURCE_PACKAGE) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files(package).joinpath(resource_name).read_text(encoding="utf-8")),
    )


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductDiscoveryError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProductDiscoveryError(f"{label} must be an array")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductDiscoveryError(f"{label} must be a non-empty string")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ProductDiscoveryError(f"{label} must be a boolean")
    return value


def _require_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProductDiscoveryError(f"{label} must be an integer")
    return value


def ag_freeze_does_not_emit_outcome() -> str:
    """Freeze alone never implies a PASSED or UNPASSED A-G reconstruction outcome."""

    return "PREREGISTERED_AWAITING_RECONSTRUCTION_PACKET"


def load_default_ag_reconstruction_protocol() -> dict[str, Any]:
    """Load the frozen A-G reconstruction protocol."""

    protocol = _load_resource(AG_PROTOCOL_RESOURCE)
    validate_ag_reconstruction_protocol(protocol)
    if protocol["protocol_sha256"] != AG_PROTOCOL_SHA256:
        raise ProductDiscoveryError("Loaded A-G protocol digest drifted from frozen AG_PROTOCOL_SHA256")
    return protocol


def validate_ag_reconstruction_protocol(protocol: Mapping[str, Any]) -> None:
    """Validate the frozen A-G reconstruction protocol against A8 bindings."""

    required = (
        "protocol_id",
        "protocol_sha256",
        "status",
        "study_id",
        "census_registered_at",
        "a8_package_id",
        "a8_package_sha256",
        "a8_contract_sha256",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "language_scope_id",
        "jurisdiction_scope",
        "population_view_id",
        "n_observed_declared",
        "n_estimated_declared",
        "unresolved_candidate_count_declared",
        "d4_working_include_declared",
        "d4_working_total_declared",
        "observed_offering_ids",
        "required_reconstruction_fields",
        "required_headline_ids",
        "headline_reconstruction_bindings",
        "fail_closed_rules",
        "estimator_exclusion_policy",
        "execution_gate",
        "predeclaration_rule",
        "boundary",
    )
    missing = [field for field in required if field not in protocol]
    if missing:
        raise ProductDiscoveryError("A-G reconstruction protocol missing fields: " + ", ".join(missing))

    if protocol["protocol_id"] != AG_PROTOCOL_ID:
        raise ProductDiscoveryError(f"protocol_id must be {AG_PROTOCOL_ID}")
    if protocol["status"] != "FROZEN_v1.0":
        raise ProductDiscoveryError("status must be FROZEN_v1.0")
    if protocol["study_id"] != AG_STUDY_ID:
        raise ProductDiscoveryError(f"study_id must be {AG_STUDY_ID}")
    if content_digest(protocol, exclude="protocol_sha256") != protocol["protocol_sha256"]:
        raise ProductDiscoveryError("protocol_sha256 does not match content digest")
    if protocol["boundary"] != AG_PROTOCOL_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    if protocol["a8_package_id"] != A8_PACKAGE_ID:
        raise ProductDiscoveryError(f"a8_package_id must be {A8_PACKAGE_ID}")
    if protocol["a8_package_sha256"] != A8_PACKAGE_SHA256:
        raise ProductDiscoveryError("a8_package_sha256 must equal frozen A8 package digest")
    if protocol["a8_contract_sha256"] != A8_CONTRACT_SHA256:
        raise ProductDiscoveryError("a8_contract_sha256 must equal frozen A8 contract digest")
    if protocol["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("analysis_universe_id must equal frozen A2 analysis universe")
    if protocol["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff drift")
    if protocol["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff drift")
    if protocol["language_scope_id"] != A2_LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("language_scope_id drift")
    if protocol["jurisdiction_scope"] != A2_JURISDICTION_SCOPE:
        raise ProductDiscoveryError("jurisdiction_scope drift")
    if protocol["population_view_id"] != POPULATION_VIEW_ID:
        raise ProductDiscoveryError(f"population_view_id must be {POPULATION_VIEW_ID}")
    if _require_int(protocol["n_observed_declared"], "n_observed_declared") != N_OBSERVED:
        raise ProductDiscoveryError(f"n_observed_declared must be {N_OBSERVED}")
    if protocol["n_estimated_declared"] is not None:
        raise ProductDiscoveryError("n_estimated_declared must remain null under A7 fail-closed")
    if _require_int(protocol["unresolved_candidate_count_declared"], "unresolved_candidate_count_declared") != (
        UNRESOLVED_CANDIDATE_COUNT
    ):
        raise ProductDiscoveryError("unresolved_candidate_count_declared drift")
    if (
        _require_int(protocol["d4_working_include_declared"], "d4_working_include_declared")
        != D4_WORKING_DISTRIBUTION["INCLUDE"]
    ):
        raise ProductDiscoveryError("d4_working_include_declared drift")
    if (
        _require_int(protocol["d4_working_total_declared"], "d4_working_total_declared")
        != D4_WORKING_DISTRIBUTION["TOTAL"]
    ):
        raise ProductDiscoveryError("d4_working_total_declared drift")
    if tuple(protocol["observed_offering_ids"]) != OBSERVED_OFFERING_IDS:
        raise ProductDiscoveryError("observed_offering_ids drift")

    fields = _require_list(protocol["required_reconstruction_fields"], "required_reconstruction_fields")
    if tuple(fields) != REQUIRED_RECONSTRUCTION_FIELDS:
        raise ProductDiscoveryError("required_reconstruction_fields drift")

    headlines = _require_list(protocol["required_headline_ids"], "required_headline_ids")
    if tuple(headlines) != REQUIRED_HEADLINE_IDS:
        raise ProductDiscoveryError("required_headline_ids drift")

    bindings = _require_mapping(protocol["headline_reconstruction_bindings"], "headline_reconstruction_bindings")
    if set(bindings.keys()) != set(REQUIRED_HEADLINE_IDS):
        raise ProductDiscoveryError("headline_reconstruction_bindings key set drift")
    for headline_id in REQUIRED_HEADLINE_IDS:
        binding = _require_mapping(bindings[headline_id], headline_id)
        _require_str(binding.get("a8_component_path"), f"{headline_id}.a8_component_path")
        _require_str(binding.get("upstream_digest_field"), f"{headline_id}.upstream_digest_field")
        _require_str(binding.get("expected_value_description"), f"{headline_id}.expected_value_description")
        field_checklist = _require_list(binding.get("required_fields"), f"{headline_id}.required_fields")
        if tuple(field_checklist) != REQUIRED_RECONSTRUCTION_FIELDS:
            raise ProductDiscoveryError(f"{headline_id} must require all twelve reconstruction fields")

    fail_closed = _require_mapping(protocol["fail_closed_rules"], "fail_closed_rules")
    for field in (
        "missing_upstream_digest_is_unpassed",
        "invented_n_estimated_is_rejected",
        "completeness_overclaim_is_rejected",
        "mixed_universe_is_rejected",
        "estimator_contamination_f7_f9_f11_is_rejected",
        "unresolved_required_field_is_unpassed",
    ):
        if not _require_bool(fail_closed.get(field), field):
            raise ProductDiscoveryError(f"fail_closed_rules.{field} must be true")

    exclusion = _require_mapping(protocol["estimator_exclusion_policy"], "estimator_exclusion_policy")
    excluded = _require_list(exclusion.get("excluded_frame_ids"), "excluded_frame_ids")
    if set(excluded) != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ProductDiscoveryError("estimator exclusion must be exactly F7/F9/F11")
    if not _require_bool(
        exclusion.get("reject_primary_estimator_contamination"), "reject_primary_estimator_contamination"
    ):
        raise ProductDiscoveryError("reject_primary_estimator_contamination must be true")

    gate = _require_mapping(protocol["execution_gate"], "execution_gate")
    for field in (
        "requires_frozen_protocol_before_packet",
        "freeze_alone_does_not_emit_outcome",
        "does_not_authorize_release_b_c_d",
        "does_not_establish_s2_publication_authority",
        "does_not_create_v4_2_assessment_effect",
        "does_not_mutate_rau",
        "does_not_allocate_canonical_identity",
        "does_not_reopen_closed_discovery_fitting",
        "preserves_a7_fail_closed",
        "f9_exhaustion_is_not_global_completeness",
        "open_world_saturation_is_not_census",
        "reconstruction_not_paperwork_signoff",
    ):
        if not _require_bool(gate.get(field), field):
            raise ProductDiscoveryError(f"execution_gate.{field} must be true")

    predeclaration = _require_str(protocol.get("predeclaration_rule"), "predeclaration_rule")
    lowered = predeclaration.lower()
    if "twelve" not in lowered and "12" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must require the twelve reconstruction fields")
    if "a8" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must bind the A8 package")
    if "b/c/d" not in lowered and "release b" not in lowered:
        raise ProductDiscoveryError("predeclaration_rule must refuse authorizing Release B/C/D")


AG_PACKET_RESOURCE = "RELEASE_A_AG_RECONSTRUCTION_PACKET.v1.0.json"
AG_PACKET_ID = "RELEASE_A_AG_RECONSTRUCTION_PACKET_v1.0"
AG_PACKET_SHA256 = "33dc577617518df8f88a6faf38ef0b6b6b0c06ec91e004776cf74d64d9f69c92"
PUBLICATION_AUTHORITY_VALUE = "NO_S2_PUBLICATION_AUTHORITY_CONTROLLED_RESEARCH_PACKET_ONLY"
EXPECTED_A6_STOP_STATE = "SATURATION_UNDER_DECLARED_PROTOCOL"

AG_PACKET_BOUNDARY = (
    "Repository-safe A-G reconstruction packet under the frozen A-G protocol and "
    "exact A8 package digest. Automated checks walk A8 to upstream digests and "
    "source packets for each required headline and resolve the twelve "
    "reconstruction fields. Outcome is PASSED only when every required field "
    "resolves from immutable artifacts; otherwise UNPASSED. Does not authorize "
    "Release B/C/D, establish S2 publication authority, or create v4.2 assessment "
    "effect. A7 fail-closed N_observed=6 with no N_estimated is preserved. F9 "
    "exhaustion is not global completeness; open-world saturation is not a census."
)


def _resolved_field(value: Any, *, binding: str, digest_or_ref: str) -> dict[str, Any]:
    return {
        "resolved": True,
        "value": value,
        "binding": binding,
        "digest_or_ref": digest_or_ref,
    }


def _unresolved_field(*, reason: str) -> dict[str, Any]:
    return {
        "resolved": False,
        "value": None,
        "binding": None,
        "digest_or_ref": None,
        "unresolved_reason": reason,
    }


def _common_scope_fields() -> dict[str, dict[str, Any]]:
    return {
        "language_jurisdiction_scope": _resolved_field(
            f"{A2_LANGUAGE_SCOPE_ID}/{A2_JURISDICTION_SCOPE}",
            binding="A2 language_scope_id + analysis_jurisdiction_scope",
            digest_or_ref=DEFAULT_ANALYSIS_UNIVERSE_ID,
        ),
        "world_knowledge_cutoffs": _resolved_field(
            f"{A2_WORLD_TIME_CUTOFF}/{A2_KNOWLEDGE_TIME_CUTOFF}",
            binding="A8/A2 world_time_cutoff + knowledge_time_cutoff",
            digest_or_ref=A8_PACKAGE_SHA256,
        ),
        "publication_authority": _resolved_field(
            PUBLICATION_AUTHORITY_VALUE,
            binding="A8 status CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE; no S2 authority",
            digest_or_ref=A8_PACKAGE_SHA256,
        ),
    }


def _headline_row_complete(fields: Mapping[str, Mapping[str, Any]]) -> bool:
    return all(bool(fields[name].get("resolved")) for name in REQUIRED_RECONSTRUCTION_FIELDS)


def reconstruct_headline_evidence(
    headline_id: str,
    *,
    a8_package: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Walk A8 → upstream digests → source packets for one required headline."""

    components = _require_mapping(a8_package["components"], "components")
    bindings = _require_mapping(contract["upstream_digest_bindings"], "upstream_digest_bindings")
    common = _common_scope_fields()
    uncertainty_entries = components["source_coverage_uncertainty_register"]["entries"]
    unresolved_register = components["explicit_unknown_unresolved_register"]

    if headline_id == "N_OBSERVED_A_P1":
        registry = components["product_registry"]
        digest = bindings.get("product_registry_sha256")
        if digest != registry.get("resource_sha256"):
            fields = {
                name: _unresolved_field(reason="missing or drifted product_registry digest")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        identity_digest = registry.get("identity_registry_sha256")
        if a8_package.get("observed_offering_set_sha256") != A1_INITIAL_KNOWN_IDENTITY_SHA256:
            fields = {
                name: _unresolved_field(reason="observed offering set digest drift")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        fields = {
            "counted_object": _resolved_field(
                "canonical PRODUCT/OFFERING identities under A-P1",
                binding="headline_counts.N_OBSERVED_A_P1.denominator_label",
                digest_or_ref=A8_PACKAGE_SHA256,
            ),
            "exact_identity": _resolved_field(
                list(OBSERVED_OFFERING_IDS),
                binding="a8.observed_offering_ids + product identity registry",
                digest_or_ref=str(identity_digest),
            ),
            "source_observations": _resolved_field(
                "A1 seed Product Registry analytical projection rows",
                binding="components.product_registry.resource",
                digest_or_ref=str(digest),
            ),
            "source_frames": _resolved_field(
                "A1 seed registry (pre-multi-frame discovery denominator)",
                binding="A1 seed + A2 analysis universe",
                digest_or_ref=DEFAULT_ANALYSIS_UNIVERSE_ID,
            ),
            "discovery_stopping_rule": _resolved_field(
                "A1 seed freeze; discovery increments measured separately in A2–A6",
                binding="A8 product_registry component note",
                digest_or_ref=str(digest),
            ),
            "observed_vs_estimated": _resolved_field(
                "DIRECT_OBSERVATION_ONLY",
                binding="n_observed reported separately from n_estimated",
                digest_or_ref=A8_PACKAGE_SHA256,
            ),
            "model_assumptions": _resolved_field(
                "No unseen-population model enters N_observed",
                binding="A8 claim class OBSERVED_FACT",
                digest_or_ref=A8_PACKAGE_SHA256,
            ),
            "uncertainty": _resolved_field(
                [entry["uncertainty_id"] for entry in uncertainty_entries],
                binding="source_coverage_uncertainty_register",
                digest_or_ref=A8_PACKAGE_SHA256,
            ),
            "unresolved_evidence": _resolved_field(
                unresolved_register.get("unresolved_candidate_count"),
                binding="explicit_unknown_unresolved_register",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            **common,
        }
        return _evidence_row(headline_id, N_OBSERVED, fields, [A8_PACKAGE_SHA256, str(digest)])

    if headline_id == "N_ESTIMATED_A_P1":
        a7_component = components["a7_population_estimation_report"]
        digest = bindings.get("a7_estimation_report_sha256")
        if digest != a7_component.get("packet_sha256") or digest != A7_STUDY_PACKET_SHA256:
            fields = {
                name: _unresolved_field(reason="missing or drifted a7 estimation report digest")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        a7 = load_default_a7_population_estimation_report()
        if a7.get("n_estimated") is not None or a7_component.get("n_estimated") is not None:
            raise ProductDiscoveryError("invented n_estimated rejected under A-G fail-closed rules")
        if a7.get("estimation_outcome") != "FAIL_CLOSED":
            fields = {
                name: _unresolved_field(reason="a7 estimation_outcome not FAIL_CLOSED")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256, str(digest)])
        fields = {
            "counted_object": _resolved_field(
                "unseen PRODUCT/OFFERING population under A-P1 (no estimate admitted)",
                binding="headline_counts.N_ESTIMATED_A_P1.denominator_label",
                digest_or_ref=str(digest),
            ),
            "exact_identity": _resolved_field(
                list(OBSERVED_OFFERING_IDS),
                binding="a7.observed_offering_ids (observed separately)",
                digest_or_ref=A1_INITIAL_KNOWN_IDENTITY_SHA256,
            ),
            "source_observations": _resolved_field(
                "estimator-eligible capture history under frozen A7 dataset",
                binding="a7.capture_history_dataset_sha256",
                digest_or_ref=str(a7.get("capture_history_dataset_sha256")),
            ),
            "source_frames": _resolved_field(
                a7["assumptions"]["primary_estimation_frames"],
                binding="a7.assumptions.primary_estimation_frames",
                digest_or_ref=str(digest),
            ),
            "discovery_stopping_rule": _resolved_field(
                a7.get("fail_closed_outcome"),
                binding="a7.fail_closed_outcome under preregistered acceptance criteria",
                digest_or_ref=str(digest),
            ),
            "observed_vs_estimated": _resolved_field(
                "ESTIMATED_COMPONENT_NULL_FAIL_CLOSED",
                binding="n_estimated is null; n_observed reported separately",
                digest_or_ref=str(digest),
            ),
            "model_assumptions": _resolved_field(
                a7.get("assumptions"),
                binding="a7.assumptions + model_specification_sha256",
                digest_or_ref=str(a7.get("model_specification_sha256")),
            ),
            "uncertainty": _resolved_field(
                a7.get("fail_closed_reasons"),
                binding="a7.fail_closed_reasons + interval_or_sensitivity",
                digest_or_ref=str(digest),
            ),
            "unresolved_evidence": _resolved_field(
                a7.get("classes_likely_poorly_observed"),
                binding="a7.classes_likely_poorly_observed",
                digest_or_ref=str(digest),
            ),
            **common,
        }
        return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256, str(digest)])

    if headline_id == "DELTA_N_CAPABILITY":
        a3_component = components["a3_capability_first_recall_study"]
        digest = bindings.get("a3_study_sha256")
        if digest != a3_component.get("packet_sha256") or digest != A3_STUDY_PACKET_SHA256:
            fields = {
                name: _unresolved_field(reason="missing or drifted a3 study digest")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        a3 = load_default_a3_capability_recall_study()
        value = a3.get("delta_n_capability")
        if value != a3_component.get("delta_n_capability"):
            fields = {
                name: _unresolved_field(reason="delta_n_capability mismatch versus A8 component")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256, str(digest)])
        fields = {
            "counted_object": _resolved_field(
                "exact offering IDs in capability-expanded arm absent from conventional arm",
                binding="a3.denominator / A8 a3 component denominator_label",
                digest_or_ref=str(digest),
            ),
            "exact_identity": _resolved_field(
                a3.get("unique_capability_offering_ids", []),
                binding="a3 unique capability-only offering IDs",
                digest_or_ref=str(digest),
            ),
            "source_observations": _resolved_field(
                "A3 capability-first recall study captures under frozen preregistration",
                binding="a3 packet + preregistration digests",
                digest_or_ref=str(a3_component.get("preregistration_sha256")),
            ),
            "source_frames": _resolved_field(
                ["F1", "F2", "F3", "F4", "F5", "F6"],
                binding="conventional F1-F5 versus capability-expanded F6",
                digest_or_ref=str(digest),
            ),
            "discovery_stopping_rule": _resolved_field(
                "A3 study complete under frozen preregistration; no A4+ from this packet",
                binding="a3.boundary / next_required_state",
                digest_or_ref=str(digest),
            ),
            "observed_vs_estimated": _resolved_field(
                "DIRECT_OBSERVATION_DERIVED_DELTA",
                binding="derived quantitative result over observed offering IDs",
                digest_or_ref=str(digest),
            ),
            "model_assumptions": _resolved_field(
                "Exact-ID increment only; no identity allocation by implication",
                binding="a3.authority_controls",
                digest_or_ref=str(digest),
            ),
            "uncertainty": _resolved_field(
                "delta_n_capability remains zero under declared capability expansion",
                binding="a3.key_result",
                digest_or_ref=str(digest),
            ),
            "unresolved_evidence": _resolved_field(
                unresolved_register.get("unresolved_candidate_count"),
                binding="A8 unresolved register retained alongside A3",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            **common,
        }
        return _evidence_row(headline_id, value, fields, [A8_PACKAGE_SHA256, str(digest)])

    if headline_id == "DELTA_N_MULTILINGUAL":
        a4_component = components["a4_multilingual_coverage_sensitivity_report"]
        digest = bindings.get("a4_study_sha256")
        if digest != a4_component.get("packet_sha256") or digest != A4_STUDY_PACKET_SHA256:
            fields = {
                name: _unresolved_field(reason="missing or drifted a4 study digest")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        a4 = load_default_a4_multilingual_sensitivity_study()
        value = a4.get("delta_n_multilingual")
        if value != a4_component.get("delta_n_multilingual"):
            fields = {
                name: _unresolved_field(reason="delta_n_multilingual mismatch versus A8 component")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256, str(digest)])
        strata = a4_component.get("language_jurisdiction_strata_sha256")
        fields = {
            "counted_object": _resolved_field(
                "exact offering IDs in English+native arm absent from English arm",
                binding="a4.denominator / A8 a4 component denominator_label",
                digest_or_ref=str(digest),
            ),
            "exact_identity": _resolved_field(
                a4.get("unique_native_offering_ids", []),
                binding="a4 unique native-only offering IDs",
                digest_or_ref=str(digest),
            ),
            "source_observations": _resolved_field(
                "A4 multilingual coverage sensitivity study under frozen preregistration",
                binding="a4 packet + preregistration digests",
                digest_or_ref=str(a4_component.get("preregistration_sha256")),
            ),
            "source_frames": _resolved_field(
                ["F8"],
                binding="local-language frame contribution under EN_PLUS_PRIORITY_NATIVE_v1",
                digest_or_ref=str(strata),
            ),
            "discovery_stopping_rule": _resolved_field(
                "A4 study complete under frozen preregistration; no A5+ from this packet alone",
                binding="a4.boundary / next_required_state",
                digest_or_ref=str(digest),
            ),
            "observed_vs_estimated": _resolved_field(
                "DIRECT_OBSERVATION_DERIVED_DELTA",
                binding="derived quantitative result over observed offering IDs",
                digest_or_ref=str(digest),
            ),
            "model_assumptions": _resolved_field(
                "Language/jurisdiction strata frozen before sensitivity readout",
                binding="language_jurisdiction_strata_sha256",
                digest_or_ref=str(strata),
            ),
            "uncertainty": _resolved_field(
                "delta_n_multilingual remains zero under declared strata",
                binding="a4.key_result",
                digest_or_ref=str(digest),
            ),
            "unresolved_evidence": _resolved_field(
                unresolved_register.get("unresolved_candidate_count"),
                binding="A8 unresolved register retained alongside A4",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            **common,
        }
        return _evidence_row(headline_id, value, fields, [A8_PACKAGE_SHA256, str(digest), str(strata)])

    if headline_id == "D4_WORKING_INCLUDE":
        d4 = components["d4_reference_standard_summary"]
        version = bindings.get("d4_reference_standard_version")
        if version != d4.get("reference_standard_version"):
            fields = {
                name: _unresolved_field(reason="missing or drifted d4 version binding")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        include = d4["working_distribution"]["INCLUDE"]
        total = d4["working_distribution"]["TOTAL"]
        fields = {
            "counted_object": _resolved_field(
                "D4 working-reference boundary cases with INCLUDE disposition",
                binding="d4.working_distribution.INCLUDE over TOTAL",
                digest_or_ref=str(version),
            ),
            "exact_identity": _resolved_field(
                d4.get("reference_standard_id"),
                binding="D4_PRODUCT_REFERENCE_STANDARD_v1.0 version-only binding",
                digest_or_ref=str(version),
            ),
            "source_observations": _resolved_field(
                d4.get("source_doc"),
                binding="docs/methodology/d4-product-reference-standard-v1.0.md",
                digest_or_ref=str(version),
            ),
            "source_frames": _resolved_field(
                "D4 product reference standard (measurement foundation, not discovery frame)",
                binding="d4_reference_standard_summary",
                digest_or_ref=str(version),
            ),
            "discovery_stopping_rule": _resolved_field(
                "FROZEN_WORKING_REFERENCE; package does not re-adjudicate D4 cases",
                binding="d4.validation_state + note",
                digest_or_ref=str(version),
            ),
            "observed_vs_estimated": _resolved_field(
                "DIRECT_OBSERVATION_WORKING_SUMMARY",
                binding="OBSERVED_FACT working distribution",
                digest_or_ref=str(version),
            ),
            "model_assumptions": _resolved_field(
                "Bind version and working summary only; do not invent D4 case results",
                binding="A8 contract d4_binding_policy",
                digest_or_ref=A8_CONTRACT_SHA256,
            ),
            "uncertainty": _resolved_field(
                "Working-reference summary only; not a product-population census",
                binding="d4.note",
                digest_or_ref=str(version),
            ),
            "unresolved_evidence": _resolved_field(
                {
                    "BORDERLINE": d4["working_distribution"]["BORDERLINE"],
                    "ABSTAIN": d4["working_distribution"]["ABSTAIN"],
                },
                binding="d4.working_distribution residual dispositions",
                digest_or_ref=str(version),
            ),
            **common,
        }
        return _evidence_row(headline_id, include, fields, [A8_PACKAGE_SHA256, str(version)], denominator=total)

    if headline_id == "UNRESOLVED_CANDIDATES_RETAINED":
        digest = a8_package.get("a2_checkpoint_sha256")
        if (
            digest != CHECKPOINT_SHA256
            or unresolved_register.get("unresolved_register_sha256") != UNRESOLVED_REGISTER_SHA256
        ):
            fields = {
                name: _unresolved_field(reason="missing or drifted unresolved register / checkpoint digest")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        count = unresolved_register.get("unresolved_candidate_count")
        fields = {
            "counted_object": _resolved_field(
                "unresolved candidates retained under A2 checkpoint (not products)",
                binding="unresolved_candidate_count_denominator_label",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            "exact_identity": _resolved_field(
                "candidate_key + frame_id pairs; no canonical PRODUCT/OFFERING allocation",
                binding="explicit_unknown_unresolved_register.candidates",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            "source_observations": _resolved_field(
                unresolved_register.get("by_frame"),
                binding="A2 checkpoint unresolved_candidates projected into A8 register",
                digest_or_ref=str(digest),
            ),
            "source_frames": _resolved_field(
                [row["frame_id"] for row in unresolved_register.get("by_frame", [])],
                binding="unresolved by_frame inventory",
                digest_or_ref=str(digest),
            ),
            "discovery_stopping_rule": _resolved_field(
                "A2 bounded-frame checkpoint freeze retains unresolved set",
                binding="a2_checkpoint_id/sha256",
                digest_or_ref=str(digest),
            ),
            "observed_vs_estimated": _resolved_field(
                "DIRECT_OBSERVATION_OF_UNRESOLVED_CANDIDATES",
                binding="candidates are not estimated products",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            "model_assumptions": _resolved_field(
                "Unresolved candidates never enter N_observed or N_estimated",
                binding="A8 forbidden UNQUALIFIED_HETEROGENEOUS_PRODUCT_COUNT",
                digest_or_ref=A8_PACKAGE_SHA256,
            ),
            "uncertainty": _resolved_field(
                "416 unresolved candidates remain after A2–A7",
                binding="source_coverage_uncertainty_register + unresolved register",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            "unresolved_evidence": _resolved_field(
                count,
                binding="explicit_unknown_unresolved_register.unresolved_candidate_count",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            **common,
        }
        return _evidence_row(headline_id, count, fields, [A8_PACKAGE_SHA256, str(digest), UNRESOLVED_REGISTER_SHA256])

    if headline_id == "FRAME_STOP_STATE_A6":
        a6_component = components["a6_coverage_saturation_report"]
        digest = bindings.get("a6_study_sha256")
        if digest != a6_component.get("packet_sha256") or digest != A6_STUDY_PACKET_SHA256:
            fields = {
                name: _unresolved_field(reason="missing or drifted a6 study digest")
                for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256])
        a6 = load_default_a6_coverage_saturation_report()
        stop = a6["stop_state_evidence"]["final_stop_state"]
        if stop != EXPECTED_A6_STOP_STATE or a6_component.get("final_stop_state") != EXPECTED_A6_STOP_STATE:
            fields = {
                name: _unresolved_field(reason="a6 final_stop_state drift") for name in REQUIRED_RECONSTRUCTION_FIELDS
            }
            return _evidence_row(headline_id, None, fields, [A8_PACKAGE_SHA256, str(digest)])
        if a6["authority_controls"].get("protocol_saturation_is_not_global_completeness") is not True:
            raise ProductDiscoveryError("completeness overclaim rejected under A-G fail-closed rules")
        fields = {
            "counted_object": _resolved_field(
                "protocol stop-state under declared A6 coverage/saturation rules",
                binding="a6.stop_state_evidence.final_stop_state",
                digest_or_ref=str(digest),
            ),
            "exact_identity": _resolved_field(
                a6.get("final_known_identity_ids", list(OBSERVED_OFFERING_IDS)),
                binding="a6.final_known_identity_set_sha256",
                digest_or_ref=str(a6.get("final_known_identity_set_sha256")),
            ),
            "source_observations": _resolved_field(
                "A6 coverage/saturation report under frozen preregistration",
                binding="a6 packet + preregistration digests",
                digest_or_ref=str(a6_component.get("preregistration_sha256")),
            ),
            "source_frames": _resolved_field(
                {
                    "saturation": a6["stop_state_evidence"].get("frames_with_saturation_under_declared_protocol"),
                    "bounded_exhaustion": a6["stop_state_evidence"].get("frames_with_bounded_source_exhaustion"),
                    "budget_termination": a6["stop_state_evidence"].get("frames_with_budget_coverage_termination"),
                },
                binding="a6.stop_state_evidence frame inventories",
                digest_or_ref=str(digest),
            ),
            "discovery_stopping_rule": _resolved_field(
                stop,
                binding="SATURATION_UNDER_DECLARED_PROTOCOL; not a census",
                digest_or_ref=str(digest),
            ),
            "observed_vs_estimated": _resolved_field(
                "BOUNDED_INFERENCE_PROTOCOL_STOP",
                binding="A6 claim class BOUNDED_INFERENCE; not an unseen-population estimate",
                digest_or_ref=str(digest),
            ),
            "model_assumptions": _resolved_field(
                {
                    "protocol_saturation_is_not_global_completeness": True,
                    "f9_ledger_sha256": F9_LEDGER_SHA256,
                    "estimator_excluded_frames": sorted(PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS),
                },
                binding="a6.authority_controls + F9 ledger binding",
                digest_or_ref=str(digest),
            ),
            "uncertainty": _resolved_field(
                a6["stop_state_evidence"].get("interpretation"),
                binding="a6.stop_state_evidence.interpretation",
                digest_or_ref=str(digest),
            ),
            "unresolved_evidence": _resolved_field(
                unresolved_register.get("unresolved_candidate_count"),
                binding="A8 unresolved register retained after A6 stop",
                digest_or_ref=UNRESOLVED_REGISTER_SHA256,
            ),
            **common,
        }
        return _evidence_row(headline_id, stop, fields, [A8_PACKAGE_SHA256, str(digest)])

    raise ProductDiscoveryError(f"unsupported A-G headline_id: {headline_id}")


def _evidence_row(
    headline_id: str,
    reconstructed_value: Any,
    fields: Mapping[str, Mapping[str, Any]],
    upstream_chain: list[str],
    *,
    denominator: Any = None,
) -> dict[str, Any]:
    ordered_fields = {name: fields[name] for name in REQUIRED_RECONSTRUCTION_FIELDS}
    complete = _headline_row_complete(ordered_fields)
    row: dict[str, Any] = {
        "headline_id": headline_id,
        "reconstructed_value": reconstructed_value,
        "reconstruction_status": "RESOLVED" if complete else "UNRESOLVED",
        "fields": ordered_fields,
        "upstream_digest_chain": upstream_chain,
    }
    if denominator is not None:
        row["denominator"] = denominator
    return row


def reject_adversarial_reconstruction_claims(packet: Mapping[str, Any]) -> None:
    """Fail closed on invented estimates, completeness overclaims, mixed universe, and F7/F9/F11 contamination."""

    if packet.get("n_estimated") is not None:
        raise ProductDiscoveryError("invented n_estimated rejected under A-G fail-closed rules")
    if packet.get("analysis_universe_id") != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("mixed universe rejected under A-G fail-closed rules")
    authority = _require_mapping(packet.get("authority_controls"), "authority_controls")
    if authority.get("does_not_authorize_release_b_c_d") is not True:
        raise ProductDiscoveryError("Release B/C/D authorization rejected under A-G")
    if authority.get("f9_exhaustion_is_not_global_completeness") is not True:
        raise ProductDiscoveryError("completeness overclaim rejected under A-G fail-closed rules")
    if authority.get("open_world_saturation_is_not_census") is not True:
        raise ProductDiscoveryError("completeness overclaim rejected under A-G fail-closed rules")
    exclusion = _require_list(packet.get("estimator_excluded_frame_ids"), "estimator_excluded_frame_ids")
    if set(exclusion) != PRIMARY_ESTIMATION_EXCLUDED_FRAME_IDS:
        raise ProductDiscoveryError("estimator contamination from F7/F9/F11 rejected under A-G")
    if (
        packet.get("outcome") == "PASSED"
        and authority.get("reconstruction_complete_for_required_headlines") is not True
    ):
        raise ProductDiscoveryError("PASSED outcome requires reconstruction_complete_for_required_headlines")


def build_ag_reconstruction_evidence_table() -> list[dict[str, Any]]:
    """Execute the live A8 → upstream reconstruction walk for all required headlines."""

    a8_package = load_default_a8_product_population_release_package()
    contract = load_default_a8_package_manifest_contract()
    return [
        reconstruct_headline_evidence(headline_id, a8_package=a8_package, contract=contract)
        for headline_id in REQUIRED_HEADLINE_IDS
    ]


def determine_ag_outcome(evidence_table: list[Mapping[str, Any]]) -> str:
    """Return PASSED only when every required headline fully resolves."""

    if len(evidence_table) != len(REQUIRED_HEADLINE_IDS):
        return "UNPASSED"
    by_id = {row["headline_id"]: row for row in evidence_table}
    for headline_id in REQUIRED_HEADLINE_IDS:
        row = by_id.get(headline_id)
        if row is None or row.get("reconstruction_status") != "RESOLVED":
            return "UNPASSED"
        fields = _require_mapping(row.get("fields"), f"{headline_id}.fields")
        if not _headline_row_complete(fields):
            return "UNPASSED"
    return "PASSED"


def load_default_ag_reconstruction_packet() -> dict[str, Any]:
    """Load the frozen A-G reconstruction packet."""

    packet = _load_resource(AG_PACKET_RESOURCE)
    validate_ag_reconstruction_packet(packet)
    if packet["packet_sha256"] != AG_PACKET_SHA256:
        raise ProductDiscoveryError("Loaded A-G packet digest drifted from frozen AG_PACKET_SHA256")
    return packet


def validate_ag_reconstruction_packet(packet: Mapping[str, Any]) -> None:
    """Validate the A-G reconstruction packet against live A8 reconstruction walks."""

    required = (
        "packet_id",
        "packet_sha256",
        "status",
        "assembled_on",
        "protocol_id",
        "protocol_sha256",
        "a8_package_id",
        "a8_package_sha256",
        "a8_contract_sha256",
        "analysis_universe_id",
        "world_time_cutoff",
        "knowledge_time_cutoff",
        "language_scope_id",
        "jurisdiction_scope",
        "population_view_id",
        "n_observed",
        "n_estimated",
        "estimator_excluded_frame_ids",
        "evidence_table",
        "outcome",
        "authority_controls",
        "key_result",
        "next_required_state",
        "boundary",
    )
    missing = [field for field in required if field not in packet]
    if missing:
        raise ProductDiscoveryError("A-G reconstruction packet missing fields: " + ", ".join(missing))

    if packet["packet_id"] != AG_PACKET_ID:
        raise ProductDiscoveryError(f"packet_id must be {AG_PACKET_ID}")
    if packet["status"] != "CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE":
        raise ProductDiscoveryError("status must be CONTROLLED_RESEARCH_PACKET_REPOSITORY_SAFE")
    if packet["protocol_id"] != AG_PROTOCOL_ID:
        raise ProductDiscoveryError(f"protocol_id must be {AG_PROTOCOL_ID}")
    if packet["protocol_sha256"] != AG_PROTOCOL_SHA256:
        raise ProductDiscoveryError("protocol_sha256 drift")
    if content_digest(packet, exclude="packet_sha256") != packet["packet_sha256"]:
        raise ProductDiscoveryError("packet_sha256 does not match content digest")
    if packet["boundary"] != AG_PACKET_BOUNDARY:
        raise ProductDiscoveryError("boundary text drift")

    if packet["a8_package_id"] != A8_PACKAGE_ID:
        raise ProductDiscoveryError(f"a8_package_id must be {A8_PACKAGE_ID}")
    if packet["a8_package_sha256"] != A8_PACKAGE_SHA256:
        raise ProductDiscoveryError("a8_package_sha256 must equal frozen A8 package digest")
    if packet["a8_contract_sha256"] != A8_CONTRACT_SHA256:
        raise ProductDiscoveryError("a8_contract_sha256 must equal frozen A8 contract digest")
    if packet["analysis_universe_id"] != DEFAULT_ANALYSIS_UNIVERSE_ID:
        raise ProductDiscoveryError("mixed universe rejected under A-G fail-closed rules")
    if packet["world_time_cutoff"] != A2_WORLD_TIME_CUTOFF:
        raise ProductDiscoveryError("world_time_cutoff drift")
    if packet["knowledge_time_cutoff"] != A2_KNOWLEDGE_TIME_CUTOFF:
        raise ProductDiscoveryError("knowledge_time_cutoff drift")
    if packet["language_scope_id"] != A2_LANGUAGE_SCOPE_ID:
        raise ProductDiscoveryError("language_scope_id drift")
    if packet["jurisdiction_scope"] != A2_JURISDICTION_SCOPE:
        raise ProductDiscoveryError("jurisdiction_scope drift")
    if packet["population_view_id"] != POPULATION_VIEW_ID:
        raise ProductDiscoveryError(f"population_view_id must be {POPULATION_VIEW_ID}")
    if _require_int(packet["n_observed"], "n_observed") != N_OBSERVED:
        raise ProductDiscoveryError(f"n_observed must be {N_OBSERVED}")
    if packet["n_estimated"] is not None:
        raise ProductDiscoveryError("invented n_estimated rejected under A-G fail-closed rules")

    reject_adversarial_reconstruction_claims(packet)

    live_table = build_ag_reconstruction_evidence_table()
    live_outcome = determine_ag_outcome(live_table)
    evidence = _require_list(packet["evidence_table"], "evidence_table")
    if len(evidence) != len(REQUIRED_HEADLINE_IDS):
        raise ProductDiscoveryError("evidence_table length drift")
    for expected, observed in zip(live_table, evidence, strict=True):
        if observed.get("headline_id") != expected["headline_id"]:
            raise ProductDiscoveryError("evidence_table headline order drift")
        if observed.get("reconstruction_status") != expected["reconstruction_status"]:
            raise ProductDiscoveryError(f"{expected['headline_id']} reconstruction_status drift")
        if observed.get("reconstructed_value") != expected["reconstructed_value"]:
            raise ProductDiscoveryError(f"{expected['headline_id']} reconstructed_value drift")
        obs_fields = _require_mapping(observed.get("fields"), "fields")
        for field_name in REQUIRED_RECONSTRUCTION_FIELDS:
            live_field = expected["fields"][field_name]
            packet_field = _require_mapping(obs_fields.get(field_name), field_name)
            if bool(packet_field.get("resolved")) != bool(live_field.get("resolved")):
                raise ProductDiscoveryError(f"{expected['headline_id']}.{field_name} resolved flag drift")
            if packet_field.get("resolved") and packet_field.get("digest_or_ref") != live_field.get("digest_or_ref"):
                raise ProductDiscoveryError(f"{expected['headline_id']}.{field_name} digest_or_ref drift")
            if packet_field.get("resolved") and packet_field.get("binding") != live_field.get("binding"):
                raise ProductDiscoveryError(f"{expected['headline_id']}.{field_name} binding drift")

    if packet["outcome"] != live_outcome:
        raise ProductDiscoveryError("outcome must match live reconstruction walk")
    if packet["outcome"] not in {"PASSED", "UNPASSED"}:
        raise ProductDiscoveryError("outcome must be PASSED or UNPASSED")

    authority = _require_mapping(packet["authority_controls"], "authority_controls")
    for field in (
        "does_not_authorize_release_b_c_d",
        "does_not_establish_s2_publication_authority",
        "does_not_create_v4_2_assessment_effect",
        "preserves_a7_fail_closed",
        "f9_exhaustion_is_not_global_completeness",
        "open_world_saturation_is_not_census",
        "reconstruction_not_paperwork_signoff",
        "reconstruction_complete_for_required_headlines",
    ):
        if not _require_bool(authority.get(field), field):
            raise ProductDiscoveryError(f"authority_controls.{field} must be true")

    key = _require_mapping(packet["key_result"], "key_result")
    if key.get("outcome") != packet["outcome"]:
        raise ProductDiscoveryError("key_result.outcome mismatch")
    if key.get("n_observed") != N_OBSERVED:
        raise ProductDiscoveryError("key_result.n_observed drift")
    if key.get("n_estimated") is not None:
        raise ProductDiscoveryError("key_result must not invent n_estimated")
    if key.get("a7_fail_closed_outcome") != VALID_NO_ESTIMATE_OUTCOME:
        raise ProductDiscoveryError("key_result.a7_fail_closed_outcome drift")
    if packet["next_required_state"] != "RELEASE_A_COMPLETE_AG_PASSED_NO_BCD_AUTHORIZATION":
        if packet["outcome"] == "PASSED":
            raise ProductDiscoveryError("PASSED packet next_required_state must refuse B/C/D authorization")
        if packet["next_required_state"] != "A-G_UNPASSED_RECONSTRUCTION_GAPS_REQUIRE_SUCCESSOR_FIX":
            raise ProductDiscoveryError("UNPASSED next_required_state drift")
