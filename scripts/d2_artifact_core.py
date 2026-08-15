"""Zero-provider D2 Capability Artifact construction and integrity checks."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

SCHEMA = "d2-capability-artifact-v0.2"
CAPABILITY_CLASS = "individual_model_mediated_specialist"

ALLOWED_TOP_LEVEL_KEYS = {
    "schema",
    "artifact_id",
    "capability_class",
    "behavioral_objective",
    "source_public_evidence",
    "required_environment",
    "required_task_ecology",
    "development_protocol",
    "feedback_contract",
    "memory_update_contract",
    "provider_contract",
    "resource_requirements",
    "stopping_rule",
    "evaluation_contract",
    "known_dependencies",
    "known_failure_conditions",
    "permitted_use_modes",
    "forbidden_transfers",
    "provenance",
}

FORBIDDEN_TRANSFER_KEYS = {
    "source_agent_identity",
    "source_conversation_state",
    "source_private_strategy_state",
    "source_private_memory",
    "source_development_examples",
    "source_seed",
    "source_environment_seed",
    "hidden_task_truth",
    "hidden_policy",
    "evaluator_answers",
    "confirmatory_holdout_cases",
    "confirmatory_holdout_answers",
}

FORBIDDEN_POLICY_LABELS = {
    "answer_key",
    "lookup_table",
    "prescriptive_policy",
    "hidden_mapping",
}


@dataclass(frozen=True)
class ExportAudit:
    passed: bool
    canonical_sha256: str
    unexpected_top_level_keys: tuple[str, ...]
    missing_top_level_keys: tuple[str, ...]
    forbidden_key_occurrences: tuple[str, ...]
    forbidden_policy_labels: tuple[str, ...]
    source_identity_leaks: tuple[str, ...]
    source_seed_leaks: tuple[str, ...]
    source_example_id_leaks: tuple[str, ...]
    hidden_truth_token_leaks: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "canonical_sha256": self.canonical_sha256,
            "unexpected_top_level_keys": list(self.unexpected_top_level_keys),
            "missing_top_level_keys": list(self.missing_top_level_keys),
            "forbidden_key_occurrences": list(self.forbidden_key_occurrences),
            "forbidden_policy_labels": list(self.forbidden_policy_labels),
            "source_identity_leaks": list(self.source_identity_leaks),
            "source_seed_leaks": list(self.source_seed_leaks),
            "source_example_id_leaks": list(self.source_example_id_leaks),
            "hidden_truth_token_leaks": list(self.hidden_truth_token_leaks),
        }


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def _serialized(value: Any) -> str:
    return canonical_bytes(value).decode("utf-8")


def make_artifact(
    *,
    artifact_id: str,
    behavioral_objective: dict[str, Any],
    source_public_evidence: dict[str, Any],
    required_environment: dict[str, Any],
    required_task_ecology: dict[str, Any],
    development_protocol: dict[str, Any],
    feedback_contract: dict[str, Any],
    memory_update_contract: dict[str, Any],
    provider_contract: dict[str, Any],
    resource_requirements: dict[str, Any],
    stopping_rule: dict[str, Any],
    evaluation_contract: dict[str, Any],
    known_dependencies: list[str],
    known_failure_conditions: list[str],
    permitted_use_modes: list[str],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    artifact = {
        "schema": SCHEMA,
        "artifact_id": artifact_id,
        "capability_class": CAPABILITY_CLASS,
        "behavioral_objective": behavioral_objective,
        "source_public_evidence": source_public_evidence,
        "required_environment": required_environment,
        "required_task_ecology": required_task_ecology,
        "development_protocol": development_protocol,
        "feedback_contract": feedback_contract,
        "memory_update_contract": memory_update_contract,
        "provider_contract": provider_contract,
        "resource_requirements": resource_requirements,
        "stopping_rule": stopping_rule,
        "evaluation_contract": evaluation_contract,
        "known_dependencies": known_dependencies,
        "known_failure_conditions": known_failure_conditions,
        "permitted_use_modes": permitted_use_modes,
        "forbidden_transfers": sorted(FORBIDDEN_TRANSFER_KEYS),
        "provenance": provenance,
    }
    return artifact


def audit_artifact(
    artifact: dict[str, Any],
    *,
    source_agent_ids: Iterable[str] = (),
    source_seeds: Iterable[int | str] = (),
    source_example_ids: Iterable[str] = (),
    hidden_truth_tokens: Iterable[str] = (),
) -> ExportAudit:
    top_keys = set(artifact)
    unexpected = tuple(sorted(top_keys - ALLOWED_TOP_LEVEL_KEYS))
    missing = tuple(sorted(ALLOWED_TOP_LEVEL_KEYS - top_keys))

    all_keys = set(_walk_keys(artifact))
    # Forbidden names are allowed exactly once inside the explicit declaration list,
    # but never as object keys carrying data.
    forbidden_key_occurrences = tuple(sorted(all_keys & FORBIDDEN_TRANSFER_KEYS))
    forbidden_policy_labels = tuple(sorted(all_keys & FORBIDDEN_POLICY_LABELS))

    text = _serialized(artifact)

    def leaks(values: Iterable[object]) -> tuple[str, ...]:
        found: list[str] = []
        for value in values:
            token = str(value)
            if token and token in text:
                found.append(token)
        return tuple(sorted(set(found)))

    source_identity_leaks = leaks(source_agent_ids)
    source_seed_leaks = leaks(source_seeds)
    source_example_id_leaks = leaks(source_example_ids)
    hidden_truth_token_leaks = leaks(hidden_truth_tokens)

    schema_ok = artifact.get("schema") == SCHEMA
    class_ok = artifact.get("capability_class") == CAPABILITY_CLASS
    declared_forbidden = set(artifact.get("forbidden_transfers", []))
    forbidden_declaration_ok = declared_forbidden == FORBIDDEN_TRANSFER_KEYS

    passed = all(
        (
            schema_ok,
            class_ok,
            forbidden_declaration_ok,
            not unexpected,
            not missing,
            not forbidden_key_occurrences,
            not forbidden_policy_labels,
            not source_identity_leaks,
            not source_seed_leaks,
            not source_example_id_leaks,
            not hidden_truth_token_leaks,
        )
    )

    return ExportAudit(
        passed=passed,
        canonical_sha256=sha256(artifact),
        unexpected_top_level_keys=unexpected,
        missing_top_level_keys=missing,
        forbidden_key_occurrences=forbidden_key_occurrences,
        forbidden_policy_labels=forbidden_policy_labels,
        source_identity_leaks=source_identity_leaks,
        source_seed_leaks=source_seed_leaks,
        source_example_id_leaks=source_example_id_leaks,
        hidden_truth_token_leaks=hidden_truth_token_leaks,
    )


def assert_export_safe(
    artifact: dict[str, Any],
    **audit_kwargs: Any,
) -> ExportAudit:
    audit = audit_artifact(artifact, **audit_kwargs)
    if not audit.passed:
        raise AssertionError(json.dumps(audit.as_dict(), sort_keys=True))
    return audit
