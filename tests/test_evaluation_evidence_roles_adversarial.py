from __future__ import annotations

import copy

import pytest

import neuroai_workbench.evaluation_evidence_roles as eer


def _authority_fields() -> dict[str, object]:
    return {
        "g2_passed": False,
        "canonical_s2_authority": False,
        "publication_authority": False,
        "assessment_effect": "NONE",
    }


def _population_component() -> dict[str, object]:
    return {
        "component_id": "POPULATION-AUDIT",
        "evidence_role": eer.POPULATION_PROBABILITY_AUDIT,
        "population_generalizable": True,
        "metric_families": ["BINARY_CLASSIFICATION", "PREVALENCE"],
        "population_estimands": ["include_prevalence"],
        "denominator_semantics": "Finite frame units",
        "sampling_design_type": eer.PROBABILITY_SAMPLING_DESIGN,
        "target_population_frame_id": "FRAME-1",
        "target_population_frame_sha256": "1" * 64,
        "sampling_design_id": "DESIGN-1",
        "sampling_design_sha256": "2" * 64,
        "inclusion_probability_manifest_sha256": "3" * 64,
        "estimator_id": "ESTIMATOR-1",
        "estimator_sha256": "4" * 64,
        "uncertainty_method_id": "UNCERTAINTY-1",
        "uncertainty_method_sha256": "5" * 64,
        "certainty_cells_allowed": True,
        "challenge_enrichment": False,
        "s3_design_custody": True,
    }


def _challenge_component() -> dict[str, object]:
    return {
        "component_id": "CHALLENGE-1",
        "evidence_role": eer.CHALLENGE_CONSTRUCT_COVERAGE,
        "population_generalizable": False,
        "metric_families": ["BINARY_CLASSIFICATION", "FOUR_WAY_ROUTING"],
        "diagnostic_targets": ["failure_mode_coverage"],
        "sampling_design_type": eer.CHALLENGE_SAMPLING_DESIGN,
        "required_strata": sorted(eer.REQUIRED_STRATA["PATENT"]),
        "challenge_enrichment": True,
        "population_frame_id": None,
        "inclusion_probability_manifest_sha256": None,
        "estimator_id": None,
        "uncertainty_method_id": None,
        "prevalence_reporting_allowed": False,
        "population_recall_reporting_allowed": False,
        "s3_design_custody": True,
    }


def _plan() -> dict[str, object]:
    return {
        "schema_version": eer.EVALUATION_PLAN_SCHEMA_VERSION,
        "plan_type": eer.EVALUATION_PLAN_TYPE,
        "plan_id": "PATENT-EVALUATION-PLAN",
        "benchmark_kind": "PATENT",
        "benchmark_id": "PATENT-BENCHMARK",
        "d1_canonical_json_sha256": eer.APPROVED_D1_CANONICAL_SHA256,
        "binary_projection_id": eer.BINARY_PROJECTION_ID,
        "required_strata": sorted(eer.REQUIRED_STRATA["PATENT"]),
        "components": [_population_component(), _challenge_component()],
        "component_pooling_policy": eer.NO_CROSS_ROLE_POOLING,
        "development_tuning_boundary": eer.DEV_TUNING_BOUNDARY,
        "s3_design_custody": True,
        **_authority_fields(),
    }


def _freeze_binding(plan: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": eer.EVIDENCE_BINDING_SCHEMA_VERSION,
        "binding_type": eer.FREEZE_BINDING_TYPE,
        "binding_id": "FREEZE-BINDING-1",
        "benchmark_kind": "PATENT",
        "benchmark_id": "PATENT-BENCHMARK",
        "freeze_manifest_sha256": "a" * 64,
        "evaluation_plan_sha256": eer.evaluation_plan_identity_sha256(plan),
        "bound_at": "2026-09-08T04:00:00Z",
        **_authority_fields(),
    }


def _run_binding(plan: dict[str, object], freeze_binding: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": eer.EVIDENCE_BINDING_SCHEMA_VERSION,
        "binding_type": eer.RUN_BINDING_TYPE,
        "binding_id": "RUN-BINDING-1",
        "run_manifest_sha256": "b" * 64,
        "freeze_evaluation_binding_sha256": eer.evidence_binding_identity_sha256(freeze_binding),
        "evaluation_plan_sha256": eer.evaluation_plan_identity_sha256(plan),
        "component_id": "CHALLENGE-1",
        "evidence_role": eer.CHALLENGE_CONSTRUCT_COVERAGE,
        "aggregate_result_sha256": "c" * 64,
        "population_generalizable": False,
        "cross_role_pooling": False,
        "export_policy": eer.AGGREGATE_ONLY,
        "bound_at": "2026-09-08T04:30:00Z",
        **_authority_fields(),
    }


def test_exact_field_guard_rejects_missing_and_extra_fields() -> None:
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="missing required fields"):
        eer._require_exact_fields({}, frozenset({"a"}), "object")
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported fields"):
        eer._require_exact_fields({"a": 1, "b": 2}, frozenset({"a"}), "object")
    eer._require_exact_fields({"a": 1}, frozenset({"a"}), "object")


@pytest.mark.parametrize("value", [None, 3, "", "   "])
def test_nonempty_string_guard_rejects_invalid_values(value: object) -> None:
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="non-empty string"):
        eer._require_nonempty_string({"field": value}, "field")
    assert eer._require_nonempty_string({"field": "value"}, "field") == "value"


@pytest.mark.parametrize("value", [None, 3, "0" * 63, "g" * 64])
def test_sha256_helpers_fail_closed(value: object) -> None:
    assert not eer._is_sha256(value)
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="SHA-256"):
        eer._require_sha256({"digest": value}, "digest")
    assert eer._is_sha256("a" * 64)
    assert eer._require_sha256({"digest": "a" * 64}, "digest") == "a" * 64


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("bad-time", "RFC 3339"),
        ("2026-09-08T04:00:00", "UTC"),
        ("2026-09-08T04:00:00+01:00", "UTC"),
    ],
)
def test_timestamp_guard_rejects_invalid_or_non_utc(value: str, message: str) -> None:
    with pytest.raises(eer.EvaluationEvidenceRoleError, match=message):
        eer._require_utc_timestamp({"at": value}, "at")
    eer._require_utc_timestamp({"at": "2026-09-08T04:00:00Z"}, "at")


@pytest.mark.parametrize(
    "value",
    [None, "x", ["ok", 1], [""], ["dup", "dup"]],
)
def test_string_list_guard_rejects_malformed_values(value: object) -> None:
    with pytest.raises(eer.EvaluationEvidenceRoleError):
        eer._require_string_list(value, "items")


def test_string_list_guard_handles_empty_policy_and_exact_set() -> None:
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="must not be empty"):
        eer._require_string_list([], "items")
    assert eer._require_string_list([], "items", nonempty=False) == []
    assert eer._require_string_list(["a", "b"], "items") == ["a", "b"]
    eer._require_exact_string_set(["b", "a"], frozenset({"a", "b"}), "items")
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="contain exactly"):
        eer._require_exact_string_set(["a"], frozenset({"a", "b"}), "items")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("g2_passed", True, "g2_passed"),
        ("canonical_s2_authority", True, "canonical_s2_authority"),
        ("publication_authority", True, "publication_authority"),
        ("assessment_effect", "MUTATE", "assessment_effect"),
    ],
)
def test_authority_guard_rejects_every_escalation(field: str, value: object, message: str) -> None:
    payload = _authority_fields()
    payload[field] = value
    with pytest.raises(eer.EvaluationEvidenceRoleError, match=message):
        eer._require_no_authority_escalation(payload)
    eer._require_no_authority_escalation(_authority_fields())


def test_metric_family_guard_accepts_declared_roles_and_rejects_unknown_metrics() -> None:
    eer._validate_metric_families(["PREVALENCE"], role=eer.POPULATION_PROBABILITY_AUDIT)
    eer._validate_metric_families(["ABSTENTION"], role=eer.CHALLENGE_CONSTRUCT_COVERAGE)
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported"):
        eer._validate_metric_families(["MAGIC_METRIC"], role=eer.POPULATION_PROBABILITY_AUDIT)
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported"):
        eer._validate_metric_families(["PREVALENCE"], role=eer.CHALLENGE_CONSTRUCT_COVERAGE)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("component_id", "", "component_id"),
        ("evidence_role", eer.CHALLENGE_CONSTRUCT_COVERAGE, "evidence_role"),
        ("population_generalizable", False, "population_generalizable=true"),
        ("metric_families", ["UNKNOWN"], "unsupported"),
        ("population_estimands", [], "population_estimands"),
        ("denominator_semantics", "", "denominator_semantics"),
        ("sampling_design_type", eer.CHALLENGE_SAMPLING_DESIGN, "sampling_design_type"),
        ("target_population_frame_id", "", "target_population_frame_id"),
        ("target_population_frame_sha256", None, "target_population_frame_sha256"),
        ("sampling_design_id", "", "sampling_design_id"),
        ("sampling_design_sha256", None, "sampling_design_sha256"),
        ("inclusion_probability_manifest_sha256", None, "inclusion_probability_manifest_sha256"),
        ("estimator_id", "", "estimator_id"),
        ("estimator_sha256", None, "estimator_sha256"),
        ("uncertainty_method_id", "", "uncertainty_method_id"),
        ("uncertainty_method_sha256", None, "uncertainty_method_sha256"),
        ("certainty_cells_allowed", "yes", "certainty_cells_allowed"),
        ("challenge_enrichment", True, "challenge-enriched"),
        ("s3_design_custody", False, "controlled S3"),
    ],
)
def test_population_component_rejects_each_claim_integrity_break(
    field: str,
    value: object,
    message: str,
) -> None:
    component = _population_component()
    component[field] = value
    with pytest.raises(eer.EvaluationEvidenceRoleError, match=message):
        eer._validate_population_component(component)


def test_population_component_rejects_field_shape_changes() -> None:
    missing = _population_component()
    missing.pop("estimator_sha256")
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="missing required fields"):
        eer._validate_population_component(missing)
    extra = _population_component()
    extra["secret_population_claim"] = True
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported fields"):
        eer._validate_population_component(extra)
    eer._validate_population_component(_population_component())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("component_id", "", "component_id"),
        ("evidence_role", eer.POPULATION_PROBABILITY_AUDIT, "evidence_role"),
        ("population_generalizable", True, "population_generalizable=false"),
        ("metric_families", ["PREVALENCE"], "unsupported"),
        ("diagnostic_targets", [], "diagnostic_targets"),
        ("sampling_design_type", eer.PROBABILITY_SAMPLING_DESIGN, "sampling_design_type"),
        ("required_strata", ["WRONG"], "required_strata"),
        ("challenge_enrichment", False, "challenge_enrichment=true"),
        ("population_frame_id", "FRAME", "population_frame_id"),
        ("inclusion_probability_manifest_sha256", "1" * 64, "inclusion_probability_manifest_sha256"),
        ("estimator_id", "ESTIMATOR", "estimator_id"),
        ("uncertainty_method_id", "UNCERTAINTY", "uncertainty_method_id"),
        ("prevalence_reporting_allowed", True, "prevalence"),
        ("population_recall_reporting_allowed", True, "population recall"),
        ("s3_design_custody", False, "controlled S3"),
    ],
)
def test_challenge_component_rejects_each_generalization_escape(
    field: str,
    value: object,
    message: str,
) -> None:
    component = _challenge_component()
    component[field] = value
    with pytest.raises(eer.EvaluationEvidenceRoleError, match=message):
        eer._validate_challenge_component(component, benchmark_kind="PATENT")


def test_challenge_component_rejects_field_shape_changes() -> None:
    missing = _challenge_component()
    missing.pop("challenge_enrichment")
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="missing required fields"):
        eer._validate_challenge_component(missing, benchmark_kind="PATENT")
    extra = _challenge_component()
    extra["population_prevalence"] = 0.5
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported fields"):
        eer._validate_challenge_component(extra, benchmark_kind="PATENT")
    eer._validate_challenge_component(_challenge_component(), benchmark_kind="PATENT")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "9", "schema_version"),
        ("plan_type", "WRONG", "plan_type"),
        ("plan_id", "", "plan_id"),
        ("benchmark_kind", "WRONG", "benchmark_kind"),
        ("benchmark_id", "", "benchmark_id"),
        ("d1_canonical_json_sha256", "0" * 64, "approved D1"),
        ("binary_projection_id", "WRONG", "binary projection"),
        ("required_strata", ["WRONG"], "required_strata"),
        ("components", [], "non-empty list"),
        ("component_pooling_policy", "POOL", eer.NO_CROSS_ROLE_POOLING),
        ("development_tuning_boundary", "TUNED_ON_HELDOUT", "held-out isolation"),
        ("s3_design_custody", False, "controlled S3"),
        ("g2_passed", True, "g2_passed"),
        ("canonical_s2_authority", True, "canonical_s2_authority"),
        ("publication_authority", True, "publication_authority"),
        ("assessment_effect", "MUTATE", "assessment_effect"),
    ],
)
def test_plan_rejects_invalid_top_level_semantics(field: str, value: object, message: str) -> None:
    plan = _plan()
    plan[field] = value
    with pytest.raises(eer.EvaluationEvidenceRoleError, match=message):
        eer.validate_evaluation_plan(plan)


def test_plan_rejects_shape_component_role_and_duplicate_errors() -> None:
    missing = _plan()
    missing.pop("plan_id")
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="missing required fields"):
        eer.validate_evaluation_plan(missing)
    extra = _plan()
    extra["population_claim"] = True
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported fields"):
        eer.validate_evaluation_plan(extra)
    malformed = _plan()
    malformed["components"] = ["not-an-object"]
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="Every evaluation component"):
        eer.validate_evaluation_plan(malformed)
    bad_role = _plan()
    bad_role["components"] = [copy.deepcopy(_challenge_component())]
    bad_role["components"][0]["evidence_role"] = "UNKNOWN"
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="evidence_role"):
        eer.validate_evaluation_plan(bad_role)
    duplicate = _plan()
    duplicate["components"] = [_challenge_component(), copy.deepcopy(_challenge_component())]
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unique"):
        eer.validate_evaluation_plan(duplicate)
    eer.validate_evaluation_plan(_plan())


def test_component_lookup_is_exact() -> None:
    plan = _plan()
    assert eer._component_by_id(plan, "CHALLENGE-1")["evidence_role"] == eer.CHALLENGE_CONSTRUCT_COVERAGE
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="not present"):
        eer._component_by_id(plan, "MISSING")


def _patch_freeze_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eer, "validate_freeze_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(eer, "manifest_identity_sha256", lambda value: "a" * 64)


def test_freeze_binding_validates_exact_plan_and_freeze_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_freeze_dependencies(monkeypatch)
    plan = _plan()
    freeze: dict[str, object] = {
        "benchmark_kind": "PATENT",
        "benchmark_id": "PATENT-BENCHMARK",
    }
    binding = _freeze_binding(plan)
    eer.validate_freeze_evaluation_binding(
        binding,
        freeze_manifest=freeze,
        public_contract={},
        evaluation_plan=plan,
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "9", "schema_version"),
        ("binding_type", "WRONG", "binding_type"),
        ("binding_id", "", "binding_id"),
        ("benchmark_kind", "PRODUCT", "benchmark_kind"),
        ("benchmark_id", "OTHER", "benchmark_id"),
        ("freeze_manifest_sha256", "0" * 64, "freeze_manifest_sha256"),
        ("evaluation_plan_sha256", "0" * 64, "evaluation_plan_sha256"),
        ("bound_at", "bad", "RFC 3339"),
        ("g2_passed", True, "g2_passed"),
        ("canonical_s2_authority", True, "canonical_s2_authority"),
        ("publication_authority", True, "publication_authority"),
        ("assessment_effect", "MUTATE", "assessment_effect"),
    ],
)
def test_freeze_binding_rejects_binding_mutations(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    _patch_freeze_dependencies(monkeypatch)
    plan = _plan()
    freeze: dict[str, object] = {
        "benchmark_kind": "PATENT",
        "benchmark_id": "PATENT-BENCHMARK",
    }
    binding = _freeze_binding(plan)
    binding[field] = value
    with pytest.raises(eer.EvaluationEvidenceRoleError, match=message):
        eer.validate_freeze_evaluation_binding(
            binding,
            freeze_manifest=freeze,
            public_contract={},
            evaluation_plan=plan,
        )


def test_freeze_binding_rejects_plan_freeze_kind_and_id_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_freeze_dependencies(monkeypatch)
    freeze: dict[str, object] = {
        "benchmark_kind": "PATENT",
        "benchmark_id": "PATENT-BENCHMARK",
    }
    plan = _plan()
    binding = _freeze_binding(plan)
    changed = copy.deepcopy(plan)
    changed["benchmark_kind"] = "PRODUCT"
    changed["required_strata"] = sorted(eer.REQUIRED_STRATA["PRODUCT"])
    changed["components"] = []
    with pytest.raises(eer.EvaluationEvidenceRoleError):
        eer.validate_freeze_evaluation_binding(
            binding,
            freeze_manifest=freeze,
            public_contract={},
            evaluation_plan=changed,
        )

    changed = _plan()
    changed["benchmark_id"] = "OTHER"
    changed_binding = _freeze_binding(changed)
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="benchmark_id"):
        eer.validate_freeze_evaluation_binding(
            changed_binding,
            freeze_manifest=freeze,
            public_contract={},
            evaluation_plan=changed,
        )


def _patch_run_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eer, "validate_held_out_run_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(eer, "validate_freeze_evaluation_binding", lambda *args, **kwargs: None)
    monkeypatch.setattr(eer, "manifest_identity_sha256", lambda value: "b" * 64)


def test_run_binding_validates_exact_component_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run_dependencies(monkeypatch)
    plan = _plan()
    freeze_binding = _freeze_binding(plan)
    binding = _run_binding(plan, freeze_binding)
    run_manifest = {"aggregate_result_sha256": "c" * 64}
    eer.validate_component_run_binding(
        binding,
        run_manifest=run_manifest,
        freeze_manifest={},
        freeze_evaluation_binding=freeze_binding,
        public_contract={},
        evaluation_plan=plan,
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "9", "schema_version"),
        ("binding_type", "WRONG", "binding_type"),
        ("binding_id", "", "binding_id"),
        ("run_manifest_sha256", "0" * 64, "run_manifest_sha256"),
        ("freeze_evaluation_binding_sha256", "0" * 64, "freeze_evaluation_binding_sha256"),
        ("evaluation_plan_sha256", "0" * 64, "evaluation_plan_sha256"),
        ("component_id", "MISSING", "not present"),
        ("evidence_role", eer.POPULATION_PROBABILITY_AUDIT, "evidence_role"),
        ("population_generalizable", True, "population_generalizable"),
        ("aggregate_result_sha256", "0" * 64, "aggregate_result_sha256"),
        ("cross_role_pooling", True, "cross_role_pooling"),
        ("export_policy", "RAW", "export_policy"),
        ("bound_at", "bad", "RFC 3339"),
        ("g2_passed", True, "g2_passed"),
        ("canonical_s2_authority", True, "canonical_s2_authority"),
        ("publication_authority", True, "publication_authority"),
        ("assessment_effect", "MUTATE", "assessment_effect"),
    ],
)
def test_run_binding_rejects_mutations(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    _patch_run_dependencies(monkeypatch)
    plan = _plan()
    freeze_binding = _freeze_binding(plan)
    binding = _run_binding(plan, freeze_binding)
    binding[field] = value
    with pytest.raises(eer.EvaluationEvidenceRoleError, match=message):
        eer.validate_component_run_binding(
            binding,
            run_manifest={"aggregate_result_sha256": "c" * 64},
            freeze_manifest={},
            freeze_evaluation_binding=freeze_binding,
            public_contract={},
            evaluation_plan=plan,
        )


def test_run_binding_rejects_field_shape_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run_dependencies(monkeypatch)
    plan = _plan()
    freeze_binding = _freeze_binding(plan)
    binding = _run_binding(plan, freeze_binding)
    binding.pop("component_id")
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="missing required fields"):
        eer.validate_component_run_binding(
            binding,
            run_manifest={"aggregate_result_sha256": "c" * 64},
            freeze_manifest={},
            freeze_evaluation_binding=freeze_binding,
            public_contract={},
            evaluation_plan=plan,
        )

    binding = _run_binding(plan, freeze_binding)
    binding["raw_labels"] = ["oracle"]
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported fields"):
        eer.validate_component_run_binding(
            binding,
            run_manifest={"aggregate_result_sha256": "c" * 64},
            freeze_manifest={},
            freeze_evaluation_binding=freeze_binding,
            public_contract={},
            evaluation_plan=plan,
        )


def test_freeze_binding_rejects_field_shape_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_freeze_dependencies(monkeypatch)
    plan = _plan()
    freeze: dict[str, object] = {
        "benchmark_kind": "PATENT",
        "benchmark_id": "PATENT-BENCHMARK",
    }
    binding = _freeze_binding(plan)
    binding.pop("binding_id")
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="missing required fields"):
        eer.validate_freeze_evaluation_binding(
            binding,
            freeze_manifest=freeze,
            public_contract={},
            evaluation_plan=plan,
        )

    binding = _freeze_binding(plan)
    binding["raw_membership"] = ["oracle"]
    with pytest.raises(eer.EvaluationEvidenceRoleError, match="unsupported fields"):
        eer.validate_freeze_evaluation_binding(
            binding,
            freeze_manifest=freeze,
            public_contract={},
            evaluation_plan=plan,
        )


def test_identity_digests_change_when_semantics_change() -> None:
    plan = _plan()
    digest = eer.evaluation_plan_identity_sha256(plan)
    changed = copy.deepcopy(plan)
    changed["plan_id"] = "OTHER"
    assert eer.evaluation_plan_identity_sha256(changed) != digest

    binding = _freeze_binding(plan)
    binding_digest = eer.evidence_binding_identity_sha256(binding)
    changed_binding = copy.deepcopy(binding)
    changed_binding["binding_id"] = "OTHER"
    assert eer.evidence_binding_identity_sha256(changed_binding) != binding_digest
