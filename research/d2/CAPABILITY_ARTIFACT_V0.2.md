# Capability Artifact v0.2 — D2 treatment contract

Status: **prospective D2 treatment specification; pre-provider**.

The Capability Artifact is a public production contract. It may describe the conditions and procedure by which a capability is developed. It must not contain the source agent's private learned capability state or the hidden answer the destination is supposed to learn locally.

## Required top-level fields

```text
schema
artifact_id
capability_class
behavioral_objective
source_public_evidence
required_environment
required_task_ecology
development_protocol
feedback_contract
memory_update_contract
provider_contract
resource_requirements
stopping_rule
evaluation_contract
known_dependencies
known_failure_conditions
permitted_use_modes
forbidden_transfers
provenance
```

For D2 the `capability_class` is `individual_model_mediated_specialist`.

## Permitted semantics

The artifact may encode:

- the observable capability objective;
- action/input/output schemas;
- the family of development tasks, without source examples;
- how destination-local examples are generated;
- when and what objective feedback is returned;
- how the agent is permitted to update its private strategy/memory state;
- development call/episode budget;
- stopping rule;
- evaluation interface and scoring rule, without holdout cases/answers;
- provider/model/sampling requirements after prospective freeze;
- environmental/tool dependencies;
- public source-evidence digests and provenance;
- bounded known failure conditions.

## Forbidden semantics

The following are forbidden exports even if renaming or serialization tricks are used:

```text
source_agent_identity
source_conversation_state
source_private_strategy_state
source_private_memory
source_development_examples
source_seed
source_environment_seed
hidden_task_truth
hidden_policy
evaluator_answers
confirmatory_holdout_cases
confirmatory_holdout_answers
```

The artifact must not contain an equivalent prescriptive policy such as a lookup table, executable rule, encoded answer key, or reversible digest from which hidden task truth can be reconstructed.

## Destination-locality requirement

The reproduced arm receives the artifact, then develops from **destination-local** examples and feedback. Source development examples do not cross the boundary.

The artifact may specify the generator family and curriculum distribution but not the realized source sample.

## Description-only control

The `description_only` arm receives the same behavioral objective, action schema, provider contract, and equal logical-call budget as `reproduced`, but does not receive outcome-bearing development feedback or the artifact's production-specific curriculum/feedback schedule.

Any remaining compute difference must be declared prospectively or the treatment-integrity gate fails.

## Private strategy state

Private strategy state is allowed to evolve within a Field. It is an agent-local state object generated from that Field's own experience. It may be used in subsequent local development/evaluation calls according to the frozen memory-update contract.

It may not be exported from Source A to Destination B.

The source and destination private-state digests must differ by construction and are recorded only for integrity/provenance; the state content itself must not enter the public artifact.

## Export audit

Before any confirmatory provider call, the apparatus must canonicalize the artifact and perform:

1. exact forbidden-key scan;
2. exact source identity/seed scan;
3. exact source example identifier scan;
4. hidden-policy/answer serialization scan;
5. reversible-content audit for any encoded payloads;
6. schema allowlist validation;
7. canonical artifact SHA-256 freeze.

The audit record is committed/posted before confirmatory execution. Any failure is D2-S4 / scientifically unclassifiable until repaired prospectively before outcome generation.

## Product semantics

This artifact tests the **reproduction** mode of a broader Resonance capability. It does not imply that all capabilities must be reproducible. Future use modes may include in-place service, access/licensing, secondment, migration, composition, and reproduction.
