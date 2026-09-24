# D2-vNext-S2 prospective acquisition-qualification contract — draft

**Status:** `DRAFT / NOT AUTHORIZED`  
**Purpose:** define the evidence required before constructing any fresh successor confirmatory source-acquisition stream. This document does not authorize provider/model execution, sample-size changes to the consumed D2-vNext-S2 stream, Acceptance, registry action, D2e, or Historical Substrate activation.

## 1. Frozen boundary

The consumed run `35909017872` remains `D2-vNext-S2-A0` — `acquisition_envelope_integrity_or_minimum_n_failure`. Its N=88/schema minimum, cohort, outcomes, and evaluator classification are immutable. No qualification result may add, replace, impute, or reinterpret pairs in that run.

## 2. Qualification objective

The next executable stage, if separately authorized, should answer an engineering/scientific-method question:

> Can the intended supported-product acquisition path produce complete, evaluator-analyzable pairs for each registered schema at a prospectively characterized rate, with sufficient observability and bounded resource cost to make a later confirmatory stream analyzable by design?

The qualification stage is **not** permitted to test the developed-vs-fresh scientific effect or choose N based on observed effect magnitude.

## 3. Quantities to freeze before qualification execution

A qualification authorization should freeze at least:

- schema definitions and any intended successor changes;
- supported product, model request identity, transport/runtime revisions, and response-format contract;
- attempted qualification units per schema or a prospective sequential stopping rule;
- bounded terminal-failure observability fields;
- resource ceilings: logical calls, physical sends, wall-clock, and cost where relevant;
- estimator for per-schema completion probability and uncertainty;
- target clearance probability for the **future confirmatory** minimum `N>=88` per schema;
- rule for converting qualified completion rates into future attempted N;
- whether oversampling/replenishment is permitted and, if so, its outcome-independent mechanics;
- qualification pass/fail/inconclusive criteria;
- exact evidence package and hashes required for closeout.

## 4. Required bounded failure observability

Before provider execution, the runner should be able to persist the following when a required logical call is not accepted, without preserving raw response content unless independently authorized:

```text
pair_id
schema_id
arm
phase
logical_call_index
first_attempt: completion flags + parse diagnostic + transport-clean
retry_eligible
retry_used
second_attempt: completion flags + parse diagnostic + transport-clean (if used)
accepted_exact_completion
terminal adapter reason
logical attribution integrity
bounded error type/hash
```

The instrumentation must remain observational: it must not add extra scientific retries or modify prompt content merely to improve completion yield unless that change is itself prospectively frozen as part of the qualification mechanism.

## 5. Acquisition metric

For schema `s`, define the qualification completion indicator `C_{s,i}=1` only when the pair reaches the same evaluator-analyzable completeness contract intended for the future confirmatory stream. Estimate `p_s=P(C_{s,i}=1)` with an explicitly frozen interval procedure.

A future attempted N for schema `s` should be justified against:

```text
P[ Binomial(N_s, p_s) >= 88 ] >= q_s
```

or a more conservative model if the qualification data show shard dependence, overdispersion, temporal drift, or non-exchangeability. A single campaign-wide completion rate is not sufficient when schema yields differ materially.

## 6. Clearance probability is a pending design decision

This draft deliberately does **not** freeze `q_s` or the joint all-schema target. Candidate sensitivity points are 90%, 95%, and 99% per schema. If the project requires a probability `Q` that all four schemas clear, the contract must state how `Q` maps to schema-level targets or model the joint distribution directly; it must not silently equate a per-schema 95% target with 95% joint clearance.

For context only, if the single consumed run's completion rates were incorrectly treated as stationary future `p_s`, the diagnostic attempted-N sensitivities for reaching 88 successes are:

| Per-schema clearance target | threshold_at_4 | parity_pair | interval_pair | pairwise_order |
|---|---:|---:|---:|---:|
| 90% | 153 | 127 | 158 | 595 |
| 95% | 157 | 130 | 162 | 616 |
| 99% | 164 | 135 | 170 | 656 |

Using the lower endpoint of each schema's 95% exact binomial interval instead yields:

| Per-schema clearance target | threshold_at_4 | parity_pair | interval_pair | pairwise_order |
|---|---:|---:|---:|---:|
| 90% | 185 | 149 | 194 | 1012 |
| 95% | 190 | 153 | 199 | 1049 |
| 99% | 200 | 159 | 209 | 1119 |

These numbers are **diagnostic warnings, not a sizing recommendation**. In particular, the pairwise-order values show that scaling the current stream mechanically would be inefficient and scientifically weak. The acquisition mechanism should be qualified before a new confirmatory N is frozen.

## 7. Qualification gates

A useful non-binding gate structure is:

1. **Q0 — Instrumentation integrity:** terminal failure stage/diagnostic observability is demonstrated with credential-free fixtures and cannot alter scientific outcomes.
2. **Q1 — Transport/runtime integrity:** supported-product routing, attribution, send accounting, cleanup, and fail-closed ceilings pass.
3. **Q2 — Schema completion envelope:** each schema has enough qualification observations to estimate completion yield under the frozen mechanism; evidence of shard/time heterogeneity is explicitly assessed.
4. **Q3 — Resource feasibility:** a prospectively sized future confirmatory stream can meet the selected all-schema clearance target within declared send/compute/cost ceilings under conservative attrition assumptions.
5. **Q4 — Fresh-stream construction authorization:** only after Q0–Q3 are reviewed may a new confirmatory cohort, seed namespace, sample size, and execution marker be constructed under a separate project decision.

Failure of Q0–Q3 should produce an engineering/methodological result, not an adaptive confirmatory rescue.

## 8. Oversampling and replenishment

If a future design uses more than 88 attempted opportunities or permits replenishment, the rule must be frozen before outcomes and must not depend on developed-vs-fresh scores. Acceptable mechanics would need to operate on acquisition/completion state only and preserve the intended sampling population. Any rule that selectively replaces pairs based on scientific outcome is prohibited.

## 9. Claim ceiling

A successful acquisition qualification would establish only that a particular frozen acquisition mechanism has a measured completion envelope under the tested supported-product conditions. It would not establish source-capability acquisition, a confirmed development budget, provider/model generalization, naturalistic validity, team/organization/institution effects, Acceptance, registry promotion, or production readiness.

## 10. Decision required before execution

Before any qualification workflow can be authorized, an authoritative project decision still needs to select the qualification cohort size/stopping rule, clearance target, instrumentation revision, resource ceilings, and supported-product revision. Until then this document is a design candidate only.
