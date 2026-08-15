# D1 confirmatory plan — reproduce a developed individual specialist capability

Status: **prospective confirmatory lock; no confirmatory outcomes inspected**.

Parent issue: #160. Program base: PR #158. D1-0 development calibration uses only seeds `10000..10063` and is permanently excluded from confirmatory evidence.

## Scientific question

Can a capability that emerged through experience in a source Field be characterized as a bounded Capability Artifact and deliberately reproduced in a fresh destination Field without copying source-private capability state?

D1 is restricted to the controlled deterministic individual-specialist skill/practice substrate. It does not test general LLM learning, teams, institutions, naturalistic domain transfer, or environment spawning.

## D1-0 calibration basis

The repaired development-only calibration preserves the 90% product-fidelity convention prospectively fixed before the repaired hosted run. Development estimates are used only for power/margin calibration.

The absolute P2 non-inferiority margin is frozen at:

```text
0.05931396484374999
```

This equals 10% of the D1-0 mean source-developed uplift (`0.5931396484375`). The 90% retention criterion is **conventional**, not derived materiality or a natural economic threshold.

Calibration recommended `n=32`; D1 confirmatory uses **36 independent source/destination Field pairs** so the three skill aliases are exactly balanced at 12 pairs each and the sample exceeds the conventional planning floor. Under D1-0 planning assumptions, estimated power at n=36 is 1.0 for P1 and approximately 0.99999998 for P2. These are planning calculations, not outcome claims.

## Frozen confirmatory population

Confirmatory Field-pair seeds:

```text
30000, 30001, ..., 30035
```

They are disjoint from all D1-0 development seeds. No confirmatory pair is executed before the apparatus lock and exact `[D1-RUN]` candidate are posted prospectively on #160.

Each Field pair contains:

1. `source_developed` — a fresh source population develops under the frozen ecology and a specialist is selected;
2. `reproduced_protocol` — a fresh destination population receives only the Capability Artifact contract and develops under it;
3. `fresh_no_development` — a matched fresh destination baseline;
4. `private_state_oracle` — diagnostic private-state copy, permanently product-ineligible and excluded from all confirmatory gates.

The experimental unit is one independent source/destination Field pair. The final outcome is heldout specialist success rate over 256 trials.

## Capability Artifact boundary

The artifact may expose:

- behavioral target inferred from public source history;
- public evidence digest;
- required task ecology;
- required substrate/success law;
- development and binary-feedback protocol;
- resources;
- stopping rule;
- evaluation contract.

It may not expose or transmit:

- source agent identity;
- source or source-environment seed;
- private practice state;
- source conversation state;
- evaluator truth;
- evaluation answers.

In this deterministic substrate, a raw source seed is treated as reconstructive private information and is forbidden. The destination execution path must consume the artifact contract; the source-private oracle is evaluated on a separate diagnostic path.

Artifact target-inference errors, if any, are **scientific reproduction failures**, not apparatus failures: the destination will be evaluated on the source capability target and an incorrect artifact will reduce reproduced performance.

## Statistical contract

Fixed-sequence family at one-sided alpha `0.05`:

```text
P0 source development
  ↓ only if passed
P1 destination acquisition
  ↓ only if passed
P2 reproduction fidelity
```

This gatekeeping sequence controls the familywise claim path without posthoc rescue.

For each P0/P1/P2 estimand, the primary estimate is the mean paired Field-level difference. The evaluator reports:

- point estimate;
- sample SD and standard error;
- two-sided 95% normal-approximation CI;
- one-sided 95% normal-approximation lower confidence bound;
- one-sided normal-approximation p-value;
- fixed-seed 100,000-replicate percentile-bootstrap two-sided 95% CI;
- fixed-seed percentile-bootstrap one-sided 95% lower bound.

A scientific gate passes only when **both** the registered normal lower bound and bootstrap lower bound exceed the registered null boundary. The bootstrap is a preregistered robustness requirement, not a secondary rescue analysis.

### P0 — source capability production

```text
estimand = mean(source_developed - fresh_no_development)
null boundary = 0
SESOI_type = none
```

P0 establishes whether there is actually a developed source capability to reproduce.

### P1 — destination acquisition

```text
estimand = mean(reproduced_protocol - fresh_no_development)
null boundary = 0
SESOI_type = none
```

P1 asks whether the frozen artifact/protocol creates capability in a fresh destination rather than merely describing it.

### P2 — reproduction fidelity

```text
estimand = mean(reproduced_protocol - source_developed)
null boundary = -0.05931396484374999
margin type = conventional
relative product convention = retain at least 90% of D1-0 source-developed uplift
```

P2 is non-inferiority on the absolute Field-level score difference. A descriptive fidelity ratio `(reproduced-fresh)/(source-fresh)` is also reported but is not the inferential gate.

## Stopping, missingness, and decomposition

- fixed 36 Field pairs; no early stopping;
- any missing or duplicate confirmatory pair is `D1-S4` integrity failure/unclassifiable;
- all three skill aliases are reported descriptively, but no alias subgroup may rescue a failed pooled primary gate;
- oracle performance is descriptive only;
- no tuning after confirmatory output inspection is authorized.

## Classification

```text
D1-S0  source capability not established
D1-S1  source established; destination acquisition not established
D1-S2  acquisition established; reproduction fidelity not established
D1-S3  capability reproduction supported within registered controlled scope
D1-S4  integrity/apparatus failure; scientifically unclassifiable
```

D1-S3, if observed, is initial discovery support only. Registry status may not be self-promoted by the experiment. A separately preregistered fresh D1b cohort is required before `internally_replicated` status.

## Claim ceiling

A D1-S3 result would support only:

> In the registered deterministic Field skill/practice substrate, Resonance prospectively characterized a simple individual specialist capability and reproduced its heldout behavioral effect in a fresh Field without passing source-private capability state through the Capability Artifact.

It would not establish stochastic/model-based capability learning, team or institutional reproduction, naturalistic transfer, or self-creating environments.

Production/default Historical Substrate remains OFF.
