# D2-vNext-S1 — GLM-5.3 Source Capability Acquisition Calibration

## 1. Status and purpose

D2-vNext-S1 is a **fresh prospective scientific stratum** on the intended supported GLM Coding Plan substrate after issue #219 / PR #220 established bounded Hermes/Coding Plan completion. It does not rerun, repair, replace, or reinterpret historical D2d or D2d-S2. Their designs, executions, and closeouts remain immutable.

`D2e` remains reserved for a later separately frozen held-out reproduction/generalization study if this calibration identifies an acquisition protocol. This stream cannot export Capability Artifacts, mutate the Mechanism Registry, perform Acceptance, or activate Historical Substrate.

Production/default Historical Substrate remains **OFF**.

## 2. Scientific question

For the fixed supported-product stratum consisting of pinned Hermes Agent, Z.AI GLM Coding Plan, and requested model `glm-5.3`, what prospectively fixed local-experience budget among 40, 80, and 160 labeled development cases is sufficient to produce a held-out accuracy advantage greater than 10 percentage points over a fresh source agent across the four calibration schemas?

Because the supported Hermes boundary does not expose effective upstream model identity, claims bind to the **Coding Plan / requested-`glm-5.3` stratum**, not to an independently verified upstream model identity.

## 3. Fixed provider/product substrate

- provider: Z.AI
- subscription product: GLM Coding Plan
- supported environment: Hermes Agent Python library
- Hermes repository: `hermes-agent-org/hermes`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- pinned `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- endpoint base URL: `https://api.z.ai/api/coding/paas/v4`
- provider id: `zai`
- API mode: `chat_completions`
- requested model: exact `glm-5.3`
- OpenAI SDK: `2.21.0`
- httpx: `0.28.1`
- Hermes max iterations per scientific logical call: 1
- max output tokens per scientific logical call: 768
- tools: none
- context files / memory / persistent session: disabled
- provider/model fallback: disabled
- General API fallback: prohibited
- effective upstream model identity: unobserved unless exposed by the pinned supported boundary without changing semantics

The engineering success in #219/#220 is prerequisite transport/completion evidence only. It is not scientific evidence and does not authorize this campaign.

## 4. Calibration schemas

1. `threshold_at_4`: positive-control anchor; two hidden distinct coordinates define bits by value >=4, with an opaque action permutation.
2. `parity_pair`: two hidden distinct coordinates define bits by value modulo 2, with an opaque action permutation.
3. `interval_pair`: two hidden distinct coordinates define bits by membership in 2..5 inclusive, with an opaque action permutation.
4. `pairwise_order`: four coordinates form two hidden ordered pairs; each bit is 1 iff first >= second, with an opaque action permutation.

These remain calibration schemas and are permanently ineligible for later D2e held-out confirmatory use.

## 5. Experimental unit and arms

The experimental unit is one fresh latent Field task instance. All arms for a unit share the same private policy and the same fixed 32-case held-out evaluation set.

Arms:

1. `fresh`: no labeled development cases.
2. `developed_40`: independent source trajectory receiving the first 40 cases of the registered 160-case sequence.
3. `developed_80`: independent source trajectory receiving the first 80 cases.
4. `developed_160`: independent source trajectory receiving all 160 cases.
5. `oracle_instruction`: independent diagnostic trajectory supplied the exact private policy before evaluation.

Development examples are nested by prefix. Each developed budget is a separate model trajectory. Development proceeds in blocks of 8 with labeled local feedback. Evaluation uses four fixed chunks of 8 and returns no correctness feedback.

## 6. Fresh deterministic cohort

- attempted N/schema: 96
- minimum analyzable N/schema: 88
- total attempted units: 384
- seed step: 100
- schema seed bases:
  - `threshold_at_4`: 9,000,000
  - `parity_pair`: 9,200,000
  - `interval_pair`: 9,400,000
  - `pairwise_order`: 9,600,000
- development offset: +11
- evaluation offset: +41
- development sequence: 160 balanced cases
- held-out evaluation: 32 balanced cases

Construction must deterministically prove zero seed collision, zero cross-schema overlap, zero development/evaluation feature overlap, and disjointness from all registered predecessor D2 namespaces. Failed units are not replaced.

The exact cohort-pair commitment is materialized and frozen before authorization.

## 7. Sample-size planning

Primary comparison for budget `b` is:

`A_b = accuracy(developed_b) - accuracy(fresh)`.

Prospectively fixed assumptions:

- one-sided alpha: 0.05
- null materiality boundary: 0.10
- planning alternative: 0.20
- effect above null margin: 0.10
- paired SD: 0.30
- target power: 0.90
- normal-approximation required N: 77.076171
- minimum analyzable N/schema: 88
- attempted N/schema: 96

No adaptive N, replacement, imputation, or post-outcome resizing is permitted.

## 8. Confirmatory hierarchy

Within each schema, use the frozen paired normal one-sided primary statistic and one-sided 95% lower confidence bound.

Serial hierarchy:

1. test `A_160 > 0.10`;
2. only if 160 passes, test `A_80 > 0.10`;
3. only if 80 passes, test `A_40 > 0.10`.

A gate passes only when its one-sided lower confidence bound is strictly greater than 0.10. Deterministic paired percentile bootstrap intervals use fresh fixed sensitivity seeds and cannot override the primary statistic. The oracle arm is diagnostic only and cannot rescue a failed primary gate.

## 9. Positive-control continuity

`threshold_at_4` must reach and pass the 40-case gate through the full 160→80→40 hierarchy before a common acquisition budget may be selected.

If continuity fails, no common budget is selected even if another schema is favorable.

## 10. Frozen classification namespace

- `D2-vNext-S1-A0`: integrity failure or any schema below minimum analyzable N=88.
- `D2-vNext-S1-A1`: positive-control continuity not established.
- `D2-vNext-S1-A2`: positive control passes, but at least one non-control schema fails at 160.
- `D2-vNext-S1-A3`: all non-control schemas pass 160, but at least one fails 80; common confirmed budget = 160.
- `D2-vNext-S1-A4`: all pass 80, but at least one fails 40; common confirmed budget = 80.
- `D2-vNext-S1-A5`: all non-control schemas pass 40; common confirmed budget = 40.

A common budget is calibration output only. It is not schema-generalization or capability-reproduction evidence and cannot itself promote any registry node.

## 11. Execution topology and hard provider bounds

- 24 provider shards × 16 units = 384
- 6 shards/schema
- workflow max-parallel: 4
- local provider concurrency/shard: 1
- 55 scientific logical model calls per complete unit
- 21,120 registered logical model calls if all units complete
- hard physical-send ceiling: 1,000/shard
- topology-wide physical-send ceiling: 24,000
- process-wide per-shard httpx guard blocks unregistered outbound HTTP before transmission
- a shard reaching its ceiling fails closed; units are not replaced
- aggregation and evaluation are credential-free
- provider and aggregate outputs are unclassified; only the frozen evaluator assigns `D2-vNext-S1-A0..A5`
- same-request-stream workflow reruns are prohibited

The physical ceiling is intentionally close to the one-send-per-logical-call expected path and does not multiply Hermes' full retry envelope across the campaign.

## 12. Authorization and durability

Issue #221 authorizes construction, deterministic materialization, tests, credential-free CI/preexecution, exact-candidate freeze, and exact-head review only.

**Scientific campaign execution and provider/model calls are not authorized by this plan.** A future execution requires explicit human authorization naming the exact frozen candidate and explicitly covering both the scientific campaign and bounded provider execution, with a maximum of 24,000 physical provider sends. Authorization is candidate-specific and one-use only.

The sole-child authorization marker must be the only diff from the frozen candidate. Workflow reruns are prohibited after the request stream begins.

Execution authorization does not authorize merge of resulting evidence, registry promotion, Acceptance, D2e, Historical Substrate, deployment, publication, credential changes, or material spend beyond existing Coding Plan entitlement.

## 13. Prohibitions

- no D2d or D2d-S2 rerun, repair, replacement, or reinterpretation
- no historical failed-unit reuse as scientific evidence
- no failed-unit replacement or imputation
- no adaptive N
- no interim outcome-driven modifications
- no exposure-budget, threshold, or schema retuning after outcome
- no favorable-subset claim
- no same-request-stream rerun
- no D2e destination reproduction or Capability Artifact export
- no registry mutation or Acceptance-plane promotion
- no Historical Substrate activation
