# D2d — Source Capability Acquisition Envelope

## 1. Status and purpose

D2d is a fresh, prospectively specified calibration study motivated by the valid D2c `D2c-S1` result. D2c failed at the upstream P0 source-development gate in all three held-out schemas, so D2d isolates the source capability-acquisition process before any further Capability Artifact generalization test.

D2d is **not** a rerun, repair, rescue, or favorable-subset analysis of D2c. It does not test destination reproduction, does not export Capability Artifacts, and cannot change the Mechanism Registry.

## 2. Scientific question

For the fixed Z.AI `glm-5-turbo` single-agent Field substrate, what prospectively fixed local-experience budget among 40, 80, and 160 labeled development cases is sufficient to produce a held-out accuracy advantage greater than 10 percentage points over a fresh agent across the calibration schema suite?

The output of D2d is an acquisition protocol candidate for a later D2e held-out reproduction study, not a schema-generalization claim.

## 3. Fixed model substrate

- provider: Z.AI
- model: `glm-5-turbo`
- temperature: 0.8
- thinking: disabled
- structured JSON responses
- four opaque actions: `KAPPA`, `MICA`, `ORBIT`, `VELA`
- feature domain: four integer features `f0..f3`, values 0..7
- no evaluation feedback
- private selectors/action mapping remain local secrets except in the explicit oracle diagnostic arm
- no model-weight learning claim

## 4. Calibration schemas

### 4.1 `threshold_at_4`

Positive-control anchor. Two hidden distinct feature coordinates define two latent bits; each bit is 1 iff the corresponding feature value is at least 4. The 2-bit state is mapped by a fresh opaque permutation to the four action tokens.

### 4.2 `parity_pair`

Two hidden distinct coordinates; each latent bit is the coordinate value modulo 2; fresh opaque action permutation.

### 4.3 `interval_pair`

Two hidden distinct coordinates; each latent bit is 1 iff the coordinate value lies in 2..5 inclusive; fresh opaque action permutation.

### 4.4 `pairwise_order`

All four coordinates are partitioned into two hidden ordered pairs; each latent bit is 1 iff the first coordinate is greater than or equal to the second; fresh opaque action permutation.

The three D2c schemas are used here deliberately as calibration schemas after the D2c negative result. They are permanently excluded from a future D2e held-out confirmatory schema set.

## 5. Experimental unit and paired arms

The experimental unit is a fresh latent Field task instance within one schema family. All arms for a unit share the same hidden policy and the same 32-case held-out evaluation set.

Arms:

1. `fresh` — no labeled development cases.
2. `developed_40` — independent source agent with 40 labeled local development cases.
3. `developed_80` — independent source agent with 80 labeled local development cases.
4. `developed_160` — independent source agent with 160 labeled local development cases.
5. `oracle_instruction` — independent model instance given the exact private rule/selectors/action permutation before evaluation. This is a diagnostic task-solvability ceiling only.

The 40/80/160 agents are independent rather than sequential checkpoints of one persistent agent. This prevents an earlier evaluation checkpoint from contaminating later exposure conditions and makes each exposure budget a clean prospective intervention.

Development is batched in blocks of 8 cases. Evaluation uses four fixed chunks of 8 cases and gives no correctness feedback.

## 6. Cohort and deterministic namespaces

- attempted N per schema: 96
- minimum analyzable N per schema: 88
- total attempted task instances: 384
- seed step: 100 per local pair
- schema seed bases:
  - threshold_at_4: 5,000,000
  - parity_pair: 5,200,000
  - interval_pair: 5,400,000
  - pairwise_order: 5,600,000

These namespaces are prospectively disjoint from D2-C1/C2/D2b and D2c. Development/evaluation feature identities must be disjoint within every arm/task instance. Cross-schema seed overlap is prohibited.

No failed task instance is replaced.

## 7. Sample-size planning

Primary comparison for budget `b` is the paired difference

`A_b = accuracy(developed_b) - accuracy(fresh)`.

The materiality null boundary is 0.10. Planning assumptions are:

- one-sided alpha = 0.05
- planning alternative = 0.20
- effect above null margin = 0.10
- planning paired SD = 0.30
- target power = 0.90

The normal approximation gives approximately 77.1 analyzable pairs. The registered minimum is 88 and attempted N is 96 per schema, providing margin for bounded failures without replacement or adaptive N.

These assumptions define the prospective calibration contract; no post-outcome resizing is allowed.

## 8. Confirmatory inferential hierarchy

Within each schema, use the paired normal one-sided statistic and one-sided 95% lower confidence bound.

Serial hierarchy:

1. test `A_160 > 0.10`;
2. only if 160 passes, test `A_80 > 0.10`;
3. only if 80 passes, test `A_40 > 0.10`.

A gate passes only if the one-sided lower confidence bound is strictly greater than 0.10.

The hierarchy is strongest-to-lower exposure because the scientific decision is the **lowest prospectively enumerated budget that is confirmatorily sufficient**. A lower budget is never promoted into the confirmatory decision unless all stronger-budget gates above it have passed.

Deterministic paired percentile bootstrap intervals are sensitivity analyses only and cannot override the primary statistic.

The oracle arm is descriptive/diagnostic only and cannot rescue a failed acquisition gate.

## 9. Positive-control continuity gate

`threshold_at_4` is a positive-control anchor to the earlier D2 line. For the D2d acquisition envelope to be interpreted as a calibration of schema difficulty rather than an apparatus discontinuity, `threshold_at_4` must pass the registered `developed_40 - fresh > 0.10` gate.

If this continuity gate fails, the program is classified as acquisition-apparatus continuity failure and no common acquisition budget is selected, even if other schemas show favorable descriptive values.

## 10. Program-level decision

After integrity/minimum-N and the positive-control continuity gate:

- if any non-control schema fails `A_160`, no common acquisition protocol is established;
- if all non-control schemas pass 160 but at least one fails 80, common confirmed budget = 160;
- if all pass 80 but at least one fails 40, common confirmed budget = 80;
- if all pass 40, common confirmed budget = 40.

The common confirmed budget is a calibration output only. It is not evidence for `schema_generalized`, does not change `d2_stochastic_capability_reproduction`, and does not authorize production behavior.

## 11. D2e firewall

A future D2e may occur only after D2d evidence is preserved and the acquisition protocol is frozen prospectively.

D2e must use entirely new held-out schema families that were not used in D2d. The D2d calibration schemas (`threshold_at_4`, `parity_pair`, `interval_pair`, `pairwise_order`) are ineligible as D2e confirmatory schemas.

D2e may then restore the reproduction design: fresh, description-only, reproduced, and source-developed arms with P0→P1→P2 gatekeeping under the frozen D2d-selected acquisition budget.

If D2d cannot establish a common protocol even at 160 cases, the research program returns to the agent learning/memory/adaptation substrate rather than retrying reproduction.

## 12. Prohibitions

- no D2c rerun or repair
- no destination reproduction in D2d
- no Capability Artifact export in D2d
- no replacement or imputation
- no adaptive N
- no interim outcome-based decisions
- no exposure-budget retuning
- no threshold retuning
- no schema dropping
- no favorable-subset claim
- no same-request-stream workflow rerun after provider execution begins
- no reuse of D2d calibration schemas as D2e held-out confirmatory schemas
- no Mechanism Registry mutation
- no Historical Substrate activation

## 13. Authorization boundary

Construction, deterministic materialization, unit testing, and zero-provider preexecution auditing are authorized under issue #198.

**Substantive D2d provider execution is not authorized.** A future provider campaign requires a separately frozen exact scientific candidate and a new explicit authorization followed by a sole-child run marker commit. Until that event, no provider-execution marker may exist.

Production/default Historical Substrate remains **OFF**.
