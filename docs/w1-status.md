# W1 Campaign Status

Status: **COMPLETE — REPLICATED PORTABLE CAPABILITY IN THE CURRENT SKILL-PRACTICE MODEL**

Authoritative Actions run: `31458203811`
Merged implementation: PR #12

## Scope

W1 tested whether public evidence from an agent's home Resonance Field can predict performance after transferring that agent's privately acquired intrinsic practice state into unfamiliar destination tasks.

This is a bounded result for the current deterministic Field skill-practice model. It is not evidence of foundation-model weight transfer, unrestricted cross-domain intelligence, or general LLM-agent cognition.

## Source amendment

The original W1 sketch proposed reusing the W0 Experiment-001 cohort. Before destination outcomes were used, inspection of the current Field runtime showed that learned competence is represented by private `practice_by_skill` state. The W0 cohort predates that state mechanism and was therefore retained as federation/provenance precedent rather than used as the W1 developmental population.

W1 instead developed:

- discovery sources: seeds `101/202/303/404/505`, 5 Fields x 12 agents = 60 stateful agents;
- W1-04 training Fields: `101/202/303`;
- W1-04 held-out discovery Fields: `404/505`;
- W1-07 unseen replication sources: seeds `707/808/909`, 3 Fields x 12 agents = 36 agents.

The replication Fields were developed only after the predictor had been frozen.

## Transfer boundary

The Agent Capsule carried intrinsic `practice_by_skill` only. The selection model could not read that private vector. Selection used public home evidence, including task success, bidding history, experience, and specialization measurements.

Zero-shot transfer did not import home-private substrate/history or home reputation.

## Seven experiments

1. W1-01 — Home baseline: complete
2. W1-02 — Naive zero-shot transfer: complete
3. W1-03 — Random-transfer control: complete
4. W1-04 — Passport/public-evidence predicted transfer: **PASS**
5. W1-05 — Domain-shift stress: **PASS / confirmatory**
6. W1-06 — Bounded adaptation: **PASS / confirmatory**
7. W1-07 — Unseen replication: **PASS**

## W1-04 discovery result

- selected-vs-random pooled lift: **3.8639 percentage points**
- Spearman rank correlation: **0.5237**
- positive held-out Fields: **2/2**

The preregistered W1-04 discovery gate passed.

## W1-05 domain-shift result

- alias/unseen-surface family lift: **4.5584 points**
- 25% compositional shift lift: **4.0592 points**
- 50% compositional shift lift: **4.1048 points**
- positive Fields: **2/2** for every tested family

## W1-06 bounded adaptation

- selected mean success: **74.77%**
- all-agent mean success: **73.50%**
- selected mean expected improvement over adaptation: **36.28 points**
- mean latency to +6-point expected capability: **5.5 trials**

## W1-07 unseen replication

- selected-vs-random pooled lift: **2.5188 percentage points**
- Spearman rank correlation: **0.4510**
- positive Fields: **2/3**
- seed 707 lift: **-3.1391 points**
- seed 808 lift: **+5.3689 points**
- seed 909 lift: **+5.3266 points**

The preregistered W1-07 replication gate passed, but portability was not universal: one of three unseen replication Fields showed negative selection lift.

## Authoritative model

Frozen model SHA-256 from the authoritative `main` run:

`a60dd422ebb83ca1e5cf5f0be81e8c31d80a5ffc1f6f237065f0be58d7f93644`

## Conclusion

Within the current deterministic skill-practice architecture, public home-Field evidence contains enough signal to identify agents whose privately acquired competence transfers better than random selection to preregistered unfamiliar destination tasks. The result survived held-out discovery and an unseen replication cohort, while also revealing meaningful Field-level heterogeneity.
