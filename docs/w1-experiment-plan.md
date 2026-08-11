# W1 — Portable Capability Discovery Campaign

## Objective

Determine whether capability measured inside an agent's home Resonance Field predicts performance after bounded transfer into unfamiliar evaluation environments.

W1 does not recruit or permanently migrate agents. It evaluates portable capability while preserving the source Field boundary established by W0.

## Primary discovery claim

W1 may claim portable capability only if evidence-backed home measurements predict destination performance better than random selection under matched model, task information, tool access, and compute budgets.

## Experimental sequence

### W1-01 — Home baseline

Establish each candidate agent's home-ecology performance and capability profile from immutable W0 evidence.

Outputs:
- home task success;
- action specialization;
- trace-production profile;
- calibration metrics where available;
- collaboration dependence;
- candidate ranking features.

### W1-02 — Naive zero-shot transfer

Evaluate selected agents in an unfamiliar destination environment with no adaptation period and no access to home-private state.

Primary outcome:
- destination success relative to home success.

### W1-03 — Random-transfer control

Compare selected high-signal agents against random agents from the same source populations under identical destination tasks and compute budgets.

Primary outcome:
- transfer lift over random selection.

### W1-04 — Passport-predicted transfer

Fit a pre-registered predictor using only W0 Agent Passport features and test whether it ranks destination performance on held-out candidates.

Decision checkpoint:
- if the predictor fails to outperform random ranking, W1 records no portable-capability discovery and later experiments become diagnostic rather than confirmatory.

### W1-05 — Domain-shift stress

Increase semantic/task-distribution distance between source and destination environments.

Primary outcome:
- degradation curve as destination distance increases.

### W1-06 — Bounded adaptation

Allow a fixed, equal adaptation budget after zero-shot evaluation.

Primary outcomes:
- adaptation latency;
- recovery fraction;
- whether home capability predicts adaptation speed.

### W1-07 — Unseen replication

Freeze the selection rule and evaluate on new seeds, new source Fields, and an unseen destination task family with no tuning after unblinding.

Primary outcome:
- replicated transfer advantage under holdout.

## Candidate scientific gates

The discovery checkpoint after W1-04 requires all of the following:

1. destination performance is measured on tasks not present in the source evidence used for selection;
2. selected candidates outperform random controls under matched resources;
3. the ranking signal is computed before destination outcomes are revealed;
4. no home-private substrate state is imported into the zero-shot destination arm;
5. each claim resolves to immutable source and destination evidence;
6. results are replicated across multiple source seeds rather than a single Field.

W1-07 is required before promoting the result from discovery to replicated finding.

## Experimental cells

Target 3–5 independent seeds per condition. The seven experiments are expected to produce roughly 40–70 cells depending on the number of destination task families retained after the W1-04 decision checkpoint.

## Non-goals

W1 does not test:
- permanent migration;
- organizations;
- recruitment markets;
- team transfer;
- corporate memory;
- inter-field trade;
- world economics.

Those remain W2+ questions.
