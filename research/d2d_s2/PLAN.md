# D2d-S2 — Fresh Source Capability Acquisition Calibration

## 1. Status and purpose

D2d-S2 is a **fresh, prospectively specified scientific stream** created after the historical D2d campaign completed non-inferentially because its provider transport produced zero usable responses. D2d-S2 does not rerun, repair, replace, or reinterpret D2d. The D2d plan, execution record, and closeout remain immutable.

D2d-S2 isolates the same source-capability-acquisition question on a fresh deterministic cohort and binds provider execution to the hardened General API transport that was prospectively requalified in issue #206 / merged PR #207. The engineering qualification is prerequisite transport evidence only; it is not scientific evidence and does not authorize this campaign.

The label `D2e` remains reserved for the later held-out reproduction/generalization study described by the frozen D2d program. D2d-S2 cannot test destination reproduction, cannot export Capability Artifacts, and cannot mutate the Mechanism Registry.

Production/default Historical Substrate remains **OFF**.

## 2. Scientific question

For the fixed Z.AI `glm-5-turbo` single-agent Field substrate, what prospectively fixed local-experience budget among 40, 80, and 160 labeled development cases is sufficient to produce a held-out accuracy advantage greater than 10 percentage points over a fresh agent across the four calibration schemas?

The output is an acquisition-protocol candidate for a later separately frozen D2e study, not a schema-generalization or capability-reproduction claim.

## 3. Fixed model and transport substrate

- provider: Z.AI
- endpoint: `https://api.z.ai/api/paas/v4/chat/completions`
- model: `glm-5-turbo`
- temperature: 0.8
- thinking: disabled
- structured JSON response format
- max output tokens per logical call: 768
- HTTPS redirects: rejected, not followed
- explicit HTTP 200 required
- exact returned model identity required
- strict JSON parsing; non-standard constants are rejected
- absolute response-body read deadline: 90 seconds
- exactly **one physical HTTPS attempt per logical call**; no transport retry
- minimum request interval per provider shard: 0.35 seconds
- raw credentials and raw provider error messages are never persisted

The no-retry rule is a prospective D2d-S2 transport choice. It matches the one-attempt hardened transport property established by the engineering requalification and treats transport failure as a failed pair rather than selectively replacing or rescuing a scientific unit. The registered attempted N=96 and minimum analyzable N=88 provide bounded failure margin without adaptive N.

## 4. Calibration schemas

1. `threshold_at_4`: positive-control anchor. Two hidden distinct coordinates define two bits, each 1 iff value >=4; a fresh opaque permutation maps the four latent states to `KAPPA`, `MICA`, `ORBIT`, `VELA`.
2. `parity_pair`: two hidden distinct coordinates; each bit is coordinate value modulo 2; fresh opaque action permutation.
3. `interval_pair`: two hidden distinct coordinates; each bit is 1 iff value lies in 2..5 inclusive; fresh opaque action permutation.
4. `pairwise_order`: four coordinates partitioned into two hidden ordered pairs; each bit is 1 iff first >= second; fresh opaque action permutation.

These are calibration schemas, not future held-out D2e schemas. All four are permanently ineligible for a later D2e confirmatory schema set.

## 5. Experimental unit and paired arms

The experimental unit is one fresh latent Field task instance within a schema. All arms for a unit share the same private policy and the same fixed 32-case held-out evaluation set.

Arms:

1. `fresh`: no labeled development cases.
2. `developed_40`: independent source agent receiving the first 40 cases of the registered 160-case development sequence.
3. `developed_80`: independent source agent receiving the first 80 cases of that sequence.
4. `developed_160`: independent source agent receiving all 160 cases.
5. `oracle_instruction`: independent diagnostic model instance supplied the exact private rule/selectors/action mapping before evaluation.

Each developed budget uses a separate model trajectory. Development examples are nested by prefix, holding example realization fixed while varying exposure. Development occurs in blocks of 8. Evaluation uses four fixed chunks of 8 and returns no correctness feedback.

## 6. Fresh deterministic cohort

- attempted N per schema: 96
- minimum analyzable N per schema: 88
- total attempted task instances: 384
- seed step: 100
- fresh schema seed bases:
  - `threshold_at_4`: 6,000,000
  - `parity_pair`: 6,200,000
  - `interval_pair`: 6,400,000
  - `pairwise_order`: 6,600,000
- development seed offset: +11
- evaluation seed offset: +41
- development sequence: 160 balanced cases
- evaluation: 32 balanced cases

These namespaces are disjoint from D2-C1/C2, D2b, D2c, and historical D2d. Development and evaluation feature identities are disjoint within each task instance. Cross-schema seed overlap is prohibited. Failed units are not replaced.

Frozen cohort-pair commitment: `d74348dc2d15e2b1c1959726faa9ae473e01a3aeed46bcdc3b1c240e918b3d9f`.

## 7. Sample-size planning

Primary comparison for budget `b` is the paired difference

`A_b = accuracy(developed_b) - accuracy(fresh)`.

Planning assumptions are prospectively fixed:

- one-sided alpha: 0.05
- null materiality boundary: 0.10
- planning alternative: 0.20
- effect above null margin: 0.10
- planning paired SD: 0.30
- target power: 0.90

The normal approximation requires about 77.1 analyzable pairs. Minimum analyzable N is fixed at 88 and attempted N at 96 per schema. No post-outcome resizing, imputation, or replacement is permitted.

## 8. Confirmatory inferential hierarchy

Within each schema, use the same paired normal one-sided primary statistic and one-sided 95% lower confidence bound as the frozen D2d design.

Serial hierarchy:

1. test `A_160 > 0.10`;
2. only if 160 passes, test `A_80 > 0.10`;
3. only if 80 passes, test `A_40 > 0.10`.

A gate passes only when its one-sided lower confidence bound is strictly greater than 0.10. The strongest-to-lower hierarchy prospectively selects the smallest enumerated sufficient exposure without outcome-based dose selection.

Deterministic paired percentile bootstrap intervals use fixed sensitivity seeds `2026090601` through `2026090604` by schema order. They are sensitivity analyses only and cannot override the primary statistic. The oracle arm is diagnostic only and cannot rescue a failed primary gate.

## 9. Positive-control continuity gate

`threshold_at_4` is the positive-control anchor. For a common acquisition protocol to be selected, it must reach and pass the 40-case gate, which necessarily requires its 160- and 80-case gates to pass first.

If this continuity gate fails, no common acquisition budget is selected even if another schema is favorable.

## 10. Frozen classification

- `D2d-S2-A0`: integrity failure or any schema below minimum analyzable N=88.
- `D2d-S2-A1`: positive-control continuity not established.
- `D2d-S2-A2`: positive control passes, but at least one non-control schema fails at 160; no common protocol established through 160.
- `D2d-S2-A3`: all non-control schemas pass 160, but at least one fails 80; common confirmed budget = 160.
- `D2d-S2-A4`: all pass 80, but at least one fails 40; common confirmed budget = 80.
- `D2d-S2-A5`: all non-control schemas pass 40 after the serial hierarchy; common confirmed budget = 40.

A common budget is calibration output only. It is not evidence for schema generalization and cannot itself promote `d2_stochastic_capability_reproduction`.

## 11. Execution topology

- 24 provider shards × 16 task instances = 384
- 6 shards per schema
- provider local concurrency per shard: 1
- workflow max-parallel: 4
- 55 logical calls per complete task instance
- 21,120 registered logical calls if all task instances complete
- one physical attempt per logical call; maximum 21,120 physical attempts if all complete
- aggregation and evaluation are credential-free
- provider and aggregation outputs are unclassified; only the frozen evaluator assigns `D2d-S2-A0..A5`
- same-request-stream workflow reruns are prohibited

One wholly missing 16-pair shard leaves at most 80 analyzable units in the affected schema, below the minimum 88, so a favorable common-budget classification cannot survive a missing whole shard.

## 12. Authorization and durability

Issue #208 authorizes construction, deterministic materialization, tests, credential-free CI/preexecution auditing, exact-candidate freeze, and exact-head review only.

**Scientific provider execution is not authorized by this plan.** The frozen candidate retains `provider_execution_authorized=false`. A future execution requires separate explicit human authorization naming the exact candidate SHA. Only then may a sole-child marker be committed at `research/d2d_s2/RUN_D2D_S2_SOURCE_ACQUISITION` containing the candidate SHA, issue 208, and the exact authorization string required by the workflow.

The provider workflow verifies that marker commit is the sole child diff from the named candidate and rejects workflow reruns (`github.run_attempt != 1`).

External discretionary spend remains unauthorized until that explicit execution authorization. The authorization request must surface the registered maximum of 21,120 provider calls.

## 13. Prohibitions

- no D2d rerun, repair, replacement, or reinterpretation
- no D2c rerun or repair
- no destination reproduction or Capability Artifact export
- no failed-unit replacement or imputation
- no adaptive N
- no interim outcome-based decisions
- no exposure-budget retuning
- no threshold retuning
- no schema dropping
- no favorable-subset claim
- no same-request-stream workflow rerun after provider execution begins
- no reuse of these schemas as D2e held-out confirmatory schemas
- no Mechanism Registry mutation or Acceptance-plane promotion in this operation
- no Historical Substrate activation

Production/default Historical Substrate remains **OFF**.
