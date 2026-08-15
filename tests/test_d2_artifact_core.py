from __future__ import annotations

import pytest

from scripts.d2_artifact_core import assert_export_safe, audit_artifact, make_artifact


def valid_artifact():
    return make_artifact(
        artifact_id="d2-test-artifact",
        behavioral_objective={"objective": "choose the correct action from observable features"},
        source_public_evidence={"summary_digest": "public-summary-sha"},
        required_environment={"action_vocabulary": ["A", "B", "C"]},
        required_task_ecology={"generator": "frozen-hidden-policy-family", "source_examples_exported": False},
        development_protocol={"episodes": 12, "curriculum": "destination-local"},
        feedback_contract={"type": "binary_objective_outcome"},
        memory_update_contract={"type": "bounded_private_strategy", "export_allowed": False},
        provider_contract={"provider": "zai", "model": "TBD_AFTER_D2_0"},
        resource_requirements={"logical_calls": "TBD_AFTER_D2_0"},
        stopping_rule={"type": "fixed_budget", "value": "TBD_AFTER_D2_0"},
        evaluation_contract={"holdout": "frozen_unseen", "scoring": "exact_action_accuracy"},
        known_dependencies=["issue-165-acceptance", "issue-167"],
        known_failure_conditions=["invalid structured output", "artifact leakage"],
        permitted_use_modes=["reproduction"],
        provenance={"study": "D2"},
    )


def test_valid_artifact_passes_export_audit():
    artifact = valid_artifact()
    audit = assert_export_safe(
        artifact,
        source_agent_ids=["source-agent-17"],
        source_seeds=[99117],
        source_example_ids=["source-example-001"],
        hidden_truth_tokens=["SECRET_POLICY_TOKEN"],
    )
    assert audit.passed is True


def test_source_identity_leak_fails():
    artifact = valid_artifact()
    artifact["source_public_evidence"]["note"] = "source-agent-17"
    audit = audit_artifact(artifact, source_agent_ids=["source-agent-17"])
    assert audit.passed is False
    assert audit.source_identity_leaks == ("source-agent-17",)


def test_forbidden_private_state_key_fails():
    artifact = valid_artifact()
    artifact["development_protocol"]["source_private_strategy_state"] = "do not export"
    audit = audit_artifact(artifact)
    assert audit.passed is False
    assert "source_private_strategy_state" in audit.forbidden_key_occurrences


def test_hidden_truth_token_fails():
    artifact = valid_artifact()
    artifact["known_failure_conditions"].append("SECRET_POLICY_TOKEN")
    audit = audit_artifact(artifact, hidden_truth_tokens=["SECRET_POLICY_TOKEN"])
    assert audit.passed is False
    assert audit.hidden_truth_token_leaks == ("SECRET_POLICY_TOKEN",)


def test_prescriptive_policy_label_fails():
    artifact = valid_artifact()
    artifact["development_protocol"]["answer_key"] = {"x": "A"}
    audit = audit_artifact(artifact)
    assert audit.passed is False
    assert audit.forbidden_policy_labels == ("answer_key",)


def test_unexpected_top_level_key_fails():
    artifact = valid_artifact()
    artifact["extra"] = "not allowed"
    with pytest.raises(AssertionError):
        assert_export_safe(artifact)
