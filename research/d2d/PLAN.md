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

1. `threshold_at_4`: positive-control anchor. Two hidden distinct coordinates define two bits, each 1 iff the value is at least 4; the state is mapped by a fresh opaque permutation to the four actions.
2. `parity_pair`: two hidden distinct coordinates; each bit is coordinate value modulo 2; fresh opaque action permutation.
3. `interval_pair`: two hidden distinct coordinates; each bit is 1 iff the value lies in 2..5 inclusive; fresh opaque action permutation.
4. `pairwise_order`: four coordinates partitioned into two hidden ordered pairs; each bit is 1 iff first >= second; fresh opaque action permutation.

The three D2c schemas are used deliberately as calibration schemas after the D2c negative result. All four D2d schemas are permanently excluded from a future D2e held-out confirmatory schema set.

## 5. Experimental unit and paired arms

The experimental unit is a fresh latent Field task instance within one schema family. All arms for a unit share the same hidden policy and same 32-case held-out evaluation set.

Arms:

1. `fresh`: no labeled development cases.
2. `developed_40`: independent source agent receiving the first 40 cases of the registered 160-case development sequence.
3. `developed_80`: independent source agent receiving the first 80 cases of the same registered sequence.
4. `developed_160`: independent source agent receiving all 160 cases.
5. `oracle_instruction`: independent model instance given the exact private rule/selectors/action permutation before evaluation. This is a diagnostic task-solvability ceiling only.

The developed agents are independent model trajectories, but their examples are **nested by prefix**. This holds development-example realization fixed while varying exposure budget: the 40-case set is a prefix of the 80-case set, which is a prefix of the 160-case set. Earlier evaluation checkpoints therefore cannot contaminate later budgets, because each budget uses a separate agent.

Development is batched in blocks of 8 cases. Evaluation uses four fixed chunks of 8 cases and gives no correctness feedback.

## 6. Cohort and deterministic namespaces

- attempted N per schema: 96
- minimum analyzable N per schema: 88
- total attempted task instances: 384
- seed step: 100 per local task instance
- schema seed bases:
  - `threshold_at_4`: 5,000,000
  - `parity_pair`: 5,200,000
  - `interval_pair`: 5,400,000
  - `pairwise_order`: 5,600,000
- development-sequence seed offset: +11
- evaluation seed offset: +41

These namespaces are prospectively disjoint from D2-C1/C2/D2b and D2c. Development and evaluation feature identities are disjoint within every task instance. Cross-schema seed overlap is prohibited. No failed task instance is replaced.

Frozen deterministic cohort-pair hash: `a9c2077d4e76825d9ef1f6b245caf0231f5a4a3b1dc00cc0032793add8f9ea19`.

## 7. Sample-size planning

Primary comparison for budget `b` is the paired difference `A_b = accuracy(developed_b) - accuracy(fresh)`.

The materiality null boundary is 0.10. Planning assumptions are:

- one-sided alpha = 0.05
- planning alternative = 0.20
- effect above null margin = 0.10
- planning paired SD = 0.30
- target power = 0.90

The normal approximation gives approximately 77.1 analyzable pairs. The registered minimum is 88 and attempted N is 96 per schema, providing margin for bounded failures without replacement or adaptive N. No post-outcome resizing is allowed.

## 8. Confirmatory inferential hierarchy

Within each schema, use the paired normal one-sided statistic and one-sided 95% lower confidence bound.

Serial hierarchy:

1. test `A_160 > 0.10`;
2. only if 160 passes, test `A_80 > 0.10`;
3. only if 80 passes, test `A_40 > 0.10`.

A gate passes only if the one-sided lower confidence bound is strictly greater than 0.10. The strongest-to-lower hierarchy prospectively identifies the lowest enumerated exposure budget that is sufficient without post-hoc dose selection.

Deterministic paired percentile bootstrap intervals are sensitivity analyses only and cannot override the primary statistic. The oracle arm is descriptive/diagnostic only and cannot rescue a failed acquisition gate. Oracle failure alone does not make a primary pair unanalyzable.

## 9. Positive-control continuity gate

`threshold_at_4` is a positive-control anchor to the earlier D2 line. For the D2d envelope to be interpreted as calibration of schema difficulty rather than apparatus discontinuity, the threshold schema must successfully enter and pass the serial 40-case gate, which necessarily requires its 160- and 80-case gates to have passed first.

If this continuity gate fails, no common acquisition budget is selected even if other schemas show favorable descriptive values.

## 10. Frozen classification

- `D2d-A0`: integrity failure or any schema below minimum analyzable N=88.
- `D2d-A1`: positive-control continuity not established.
- `D2d-A2`: positive control passes, but at least one non-control schema fails at 160; no common acquisition protocol established through 160.
- `D2d-A3`: all non-control schemas pass 160, but at least one fails 80; common confirmed budget = 160.
- `D2d-A4`: all pass 80, but at least one fails 40; common confirmed budget = 80.
- `D2d-A5`: all non-control schemas pass 40 after the serial hierarchy; common confirmed budget = 40.

The common confirmed budget is a calibration output only. It is not evidence for `schema_generalized`, does not change `d2_stochastic_capability_reproduction`, and does not authorize production behavior.

## 11. Execution topology and durability

- 24 provider shards x 16 task instances = 384
- 6 shards per schema
- provider local concurrency = 1
- workflow max-parallel = 4
- 55 logical calls per complete pair: 4 fresh evaluation + 9 developed_40 + 14 developed_80 + 24 developed_160 + 4 oracle
- 21,120 registered logical calls before transport retries
- maximum 8 physical attempts per logical call under the validated D2 transport
- minimum request interval 0.35 seconds
- aggregation and evaluation are credential-free
- provider and aggregation outputs are unclassified; the frozen evaluator is the sole classifier
- same-request-stream workflow reruns are prohibited

One missing full 16-pair shard leaves at most 80 analyzable task instances in that schema, below the registered minimum 88. A favorable common-budget result therefore cannot survive a wholly missing shard.

## 12. D2e firewall

A future D2e may occur only after D2d evidence is preserved and an acquisition protocol is frozen prospectively. D2e must use entirely new held-out schema families not used in D2d. The D2d calibration schemas are ineligible as D2e confirmatory schemas.

D2e may then restore the reproduction design: fresh, description-only, reproduced, and source-developed arms with P0→P1→P2 gatekeeping under the frozen D2d-selected acquisition budget.

If D2d cannot establish a common protocol even at 160 cases, the research program returns to the agent learning/memory/adaptation substrate rather than retrying reproduction.

## 13. Prohibitions

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

## 14. Authorization boundary

Issue #198 authorizes construction, deterministic materialization, unit testing, and zero-provider preexecution auditing only.

**Substantive D2d provider execution is not authorized.** A future provider campaign requires a separately frozen exact scientific candidate and a new explicit authorization followed by a sole-child `research/d2d/RUN_D2D_SOURCE_ACQUISITION` marker commit. The scientific candidate itself retains `provider_execution_authorized=false`; authority exists only in that future sole-child marker.

Production/default Historical Substrate remains **OFF**.
