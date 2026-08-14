# Resonance World — Mechanism Governance v0.1

Status: **prospective governance for new mechanism claims**. Historical experiment records remain immutable and are not retroactively rewritten to satisfy this document.

## Purpose

Mechanism-first research creates a risk of excessive decomposition: a failed or heterogeneous mechanism can be split into progressively smaller child hypotheses until some leaf appears favorable. This document defines the evidence, novelty, treatment-integrity, and promotion requirements that prevent fine-grained mechanism research from becoming underpowered or posthoc.

## 1. Registry states

A mechanism registry node moves only through explicit states:

```text
proposed
  ↓
discovery_supported
  ↓
internally_replicated
  ↓
schema_generalized
  ↓
model_generalized
  ↓
naturalistic_validated
  ↓
integration_eligible
  ↓
evolution_eligible
```

A failure at a later level does not erase valid evidence at an earlier level. The node records the highest supported scope and the boundary that failed.

Historical W/O/H results imported before this governance revision use `historical_record` until they are explicitly mapped to the new schema. `historical_record` is not a new promotion and does not grant integration or evolution eligibility.

## 2. Required statistical contract

Every inferential registry node above `proposed` must have a prospectively frozen statistical contract before confirmatory data are collected.

Required fields:

```text
estimand
experimental_unit
outcome_type
paired_or_unpaired_structure
hypothesis_direction
alpha
multiplicity_family
planned_test
confidence_interval_method
sample_size_justification
target_power
minimum_analyzable_n
expected_information_structure
SESOI_or_materiality_gate
SESOI_type
SESOI_provenance
stopping_rule
missing_or_incomplete_run_policy
replication_requirement
```

For paired binary experiments, sample-size planning must account for the expected discordant-pair rate rather than relying on total cell count alone.

The result record must report at minimum:

```text
point_estimate
confidence_interval
analyzable_n
information_or_discordance_structure
raw_p_value_if_used
adjusted_p_value_if_applicable
registered_power_assumptions
sensitivity_to_key_information_assumptions
```

Confidence intervals are required for new inferential claims even when a threshold test is primary.

## 3. Effect-size governance

A numerical threshold must be classified as one of:

- `derived_materiality` — grounded in World economics, variance, operational consequences, or another explicit derivation;
- `conventional` — a workflow or advancement criterion chosen prospectively without claiming natural significance;
- `none` — no substantive effect-size threshold is justified; uncertainty and sign/estimand still govern interpretation.

Every non-null threshold requires provenance.

Illustrative values in architecture discussions are **not eligible for direct reuse in preregistration**. Examples such as a 5 percentage-point service floor, 10% capability-loss floor, or 2× compute ceiling are illustrative shapes only until a dedicated calibration exercise derives or explicitly classifies them.

## 4. Decomposition budget

A failed or heterogeneous parent mechanism may motivate child hypotheses, but child hypotheses begin as `posthoc_motivated` and do not inherit confirmatory status.

A child can become a new confirmatory node only if:

1. it defines a distinct causal intervention;
2. its rationale is recorded prospectively and is not merely the observed sign/magnitude of the parent result;
3. it uses fresh data;
4. it has an independently justified sample-size/statistical contract;
5. sibling hypotheses are covered by a preregistered multiplicity or hierarchical-testing plan when more than one is pursued.

A single failed parent should not generate an unbounded collection of independent confirmatory siblings. Any expansion beyond the preregistered sibling family requires a new program-level rationale and fresh multiplicity plan.

## 5. Treatment-integrity constitution

Each causal treatment must specify machine-verifiable invariants showing that the claimed manipulation is actually the treatment difference.

For a claimed non-interpretive transformation, the invariant should be reversible or identity-preserving wherever possible. Example:

```text
strip_shell(shell(raw_evidence)) == raw_evidence
```

A non-interpretive shell may attach identifiers or current authority metadata if prospectively allowed, but it may not silently:

- reorder evidence;
- drop or add evidence;
- rank or curate evidence;
- compute task-relevant statistics;
- summarize semantics;
- add salience/confidence markers;
- convert historical evidence into recommendations;
- change model-visible serialization by treatment in an unregistered way.

Treatment-integrity audits run before provider calls and are preserved as provenance artifacts. A failed integrity gate prevents the confirmatory campaign from starting.

## 6. Novelty and holdout constitution

Every mechanism line must define development data and frozen holdout data appropriate to its causal object.

### Historical/knowledge tasks

Generalization ladder:

```text
G0 — new stochastic execution, same units
G1 — new instances, same schema
G2 — new schema, same abstract operator
G3 — new abstract operator/reasoning family
G4 — different model family/provider
G5 — controlled naturalistic mission
G6 — embedded World ecology
```

### Capability composition

Composition novelty ladder:

```text
C0 — same modules, new stochastic execution
C1 — unseen pairing of known modules
C2 — unseen modules with known interface types
C3 — unseen module types / capability combinations
C4 — unseen task-decomposition schema
```

At minimum, composition experiments claiming novel composability must freeze an **unseen module-pair holdout** before confirmatory execution. Stronger claims should use identity-disjoint module holdouts.

Holdout outcomes may not be consumed as `composition_history` or development features during the same confirmatory claim. Once inspected for design purposes, a holdout becomes development data for future work.

## 7. Evidence generation and scientific acceptance are separate authorities

An experiment may produce evidence and a candidate classification. It may not unilaterally promote its own registry status.

Two roles are required:

```text
proposer / experiment plane
    ↓ produces candidate evidence
acceptor / registry plane
    ↓ reviews preregistration + result + provenance
registry promotion event
```

The minimum invariant is:

```text
proposer_id != acceptor_id
```

A promotion event is append-only and records:

```text
registry_node
from_status
to_status
preregistration_hash_or_issue
candidate_result_hash
acceptor
acceptance_timestamp
review_commit_or_record
```

This applies the same constitutional principle used elsewhere in Resonance: evidence may justify authority, but it does not create authority by itself.

## 8. Model sampling characterization

Cross-model evidence must not assume that equal numeric `temperature`, `top_p`, or related provider parameters imply equivalent stochastic distributions.

Before a model enters a confirmatory model-generalization claim, run a frozen characterization suite that reports at least:

- unique-response rate;
- action/output entropy where meaningful;
- repeat-response rate;
- valid-contract/output rate;
- between-replicate variance.

The purpose is to detect degenerate or pathologically unstable sampling, not to tune providers until their output distributions become artificially identical.

Primary causal effects are estimated within each model:

```text
Delta_model = outcome_treatment - outcome_control
```

Cross-model evidence evaluates sign, effect-size uncertainty, and heterogeneity across these within-model contrasts. Raw provider settings are not treated as a common physical stochasticity scale.

## 9. Economic production and clearing

Regeneration claims must reference named production technologies rather than an undefined `C_created` term.

Initial technology classes:

| technology | primary input | candidate output | lag | default cost bearer | ownership/persistence |
|---|---|---|---|---|---|
| apprenticeship | expert + novice joint work | new novice capability | medium | source/org/shared | source-owned by default |
| returned learning | external work by migrant/seconded agent | improved returning capability | short/medium | organization + source opportunity cost | source-accessible on return |
| org-funded development | compute + curriculum/practice | new source capability | medium/long | organization | source-owned by default |
| knowledge return | external evidence/artifacts | source-accessible knowledge | short | organization | provenance-preserving shared/source access |
| temporary secondment | expert service time | organization service | immediate | source opportunity cost | no new capability by itself |
| module formation | repeated joint work | relationship/team capital | medium | organization/shared | module-bound unless separately reproduced |

Each production technology must have an explicit cost model, lag, measurement window, and cost bearer before use in a confirmatory sustainability regime.

Capability degradation must be defined relative to a matched counterfactual continuation over a preregistered window, with uncertainty around the difference. Small negative fluctuations are not automatically classified as destroyed capability.

Criticality-informed pricing requires a separate calibration/pilot before any confirmatory market regime. The pilot should estimate relationships among criticality, production cost, expected replacement capability, lag, and uncertainty/risk premium. Criticality is not automatically a hard exclusion gate.

## 10. Infrastructure fallback rules

Engineering delays may reduce claim scope but may not lower the evidentiary standard for that scope.

### Registry tooling delayed

A versioned JSON registry plus append-only acceptance record is sufficient. A UI or service is not a scientific prerequisite.

### Shared request/evaluator refactor delayed

Reuse frozen, already-audited campaign machinery rather than changing scientific transport solely for architectural elegance.

### History IR treatment delayed

The confirmatory experiment that requires it does not run. Treatment construction is part of the scientific intervention, not optional infrastructure.

### Full schema generator delayed

A manually authored, prospectively frozen unseen-schema suite is allowed if author/reviewer separation is preserved. Its generalization ceiling must be declared prospectively (for example, G2). A later generator-derived replication is a separate promotion opportunity.

### Multi-model infrastructure delayed

A single-model study may proceed only with a single-model claim. It cannot promote to `model_generalized` until a separate registered model-generalization study is complete.

## 11. H8-specific pre-execution requirement

Any H8 design using a "thin shell" must include a pre-provider audit proving that the non-interpretive shell performs no unregistered curation or interpretation.

The audit must check at minimum:

- evidence cardinality identical;
- evidence content identical;
- evidence order identical;
- evidence identifiers/slots identical;
- no added derived scientific fields;
- no removed scientific fields;
- deterministic shell inversion reconstructs the original evidence payload exactly.

The canonical architecture must not predeclare "institutions preserve structure; agents interpret" as an established principle before H8. At present that is a working hypothesis only.

## 12. Promotion rule

A mechanism earns architectural status through the conjunction:

```text
causal isolation
+ adequate prospective information / sample size
+ uncertainty reporting
+ fresh-data replication
+ appropriate novelty
+ independent acceptance
```

A favorable point estimate alone is insufficient.
