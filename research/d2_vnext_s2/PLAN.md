# D2-vNext-S2 — Fresh GLM-5.3 Source Capability Acquisition Calibration

## 1. Status and purpose

D2-vNext-S2 is a **fresh prospective scientific source-acquisition stratum** after the preserved D2-vNext-S1 (#221) non-inferential A0 outcome and the subsequent engineering qualification sequence culminating in #276 `PASS`.

It does not rerun, repair, rescue, replace, continue, or reinterpret #221, D2d, D2d-S2, or any consumed engineering request stream. Historical designs, executions, failures, and closeouts remain immutable. The #276 result is prerequisite execution-contract evidence only; it is not scientific evidence.

`D2e` remains reserved for a later separately frozen destination reproduction/generalization study if this calibration identifies an acquisition protocol. This stream cannot export Capability Artifacts, mutate the Mechanism Registry, perform Acceptance, or activate Historical Substrate.

Production/default Historical Substrate remains **OFF**.

## 2. Scientific question

For the fixed supported-product stratum consisting of pinned Hermes Agent, Z.AI GLM Coding Plan, and requested model `glm-5.3`, what prospectively fixed local-experience budget among 40, 80, and 160 labeled development cases is sufficient to produce a held-out accuracy advantage greater than 10 percentage points over a fresh source agent across the four registered source-acquisition schemas?

Claims bind to the **Coding Plan / requested-`glm-5.3` stratum**. Effective upstream model identity remains unobserved unless the pinned supported-product boundary exposes it without changing execution semantics.

## 3. Fixed provider/product and structured-completion substrate

- provider: Z.AI
- subscription product: GLM Coding Plan
- endpoint base URL: `https://api.z.ai/api/coding/paas/v4`
- provider/API/requested model: `zai` / `chat_completions` / exact `glm-5.3`
- Hermes repository: `hermes-agent-org/hermes`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package: `0.8.0`
- pinned `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- pinned `pyproject.toml` blob: `95a1dfddd74bc399dd7f23f8d0143852b5689463`
- OpenAI SDK: `2.21.0`; httpx: `0.28.1`
- each Hermes invocation: `max_iterations=2`, `max_tokens=768`, temperature `0.8`, thinking disabled
- request override: `response_format={"type":"json_object"}`
- tools, context files, memory, persistent session, and fallback provider/model: disabled
- exact terminal-completion adapter blob: `ba16d2eb4b7255437c8ab224e91d5ed093897990`
- exact provider-send guard blob: `4b8896235d8048523d007400d0acfe85470f628c`

The response contract preserves the #273 non-answer positional JSON skeleton and silent final self-check: exactly one JSON object, `actions` as a square-bracket array of exactly eight action strings from `KAPPA|MICA|ORBIT|VELA`, optional ASCII `strategy` <=512 characters, and no other top-level keys. There is no literal valid answer-shaped exemplar.

### Bounded format regeneration

For each scientific logical call:

1. invoke the pinned Hermes substrate once;
2. accept an exact-parser-valid effective completion immediately, with no retry;
3. do not retry an empty, transport-unclean, attribution-ambiguous, JSON-mode compatibility-rejected, or otherwise apparatus-ambiguous first result;
4. only after a clean, non-empty, exactly attributed, failure-flag-free first result rejected by the unchanged exact parser, permit exactly one fresh Hermes invocation;
5. the retry receives the original presented cases plus only the bounded parser diagnostic class; raw first-response content is never quoted, transformed, repaired, extracted, persisted for repair, or propagated;
6. no third invocation, recursive retry, parser projection, key dropping, embedded-JSON extraction, syntax repair, coercion, object-to-array conversion, vocabulary/count widening, or response-body mutation is permitted.

The accepted invocation must satisfy the unchanged #251 effective-completion semantics. Hermes native `completed` is never mutated.

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

Fresh namespace: `rw.d2-vnext-s2-source-acquisition.v1`.

- attempted N/schema: 96
- minimum analyzable N/schema: 88
- total attempted units: 384
- seed step: 100
- schema seed bases:
  - `threshold_at_4`: 10,000,000
  - `parity_pair`: 10,200,000
  - `interval_pair`: 10,400,000
  - `pairwise_order`: 10,600,000
- development offset: +11
- evaluation offset: +41
- development sequence: 160 balanced cases
- held-out evaluation: 32 balanced cases

Construction must deterministically prove zero seed collision, zero cross-schema overlap, zero development/evaluation feature overlap, and disjointness from every predecessor D2 namespace represented in the repository. Failed units are not replaced.

The exact cohort-pair commitment is materialized and frozen before execution authorization.

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

No adaptive N, replacement, imputation, post-outcome resizing, schema dropping, favorable-subset rescue, or interim outcome-driven modification is permitted.

## 8. Confirmatory hierarchy

Within each schema, use the frozen paired normal one-sided primary statistic and one-sided 95% lower confidence bound.

Serial hierarchy:

1. test `A_160 > 0.10`;
2. only if 160 passes, test `A_80 > 0.10`;
3. only if 80 passes, test `A_40 > 0.10`.

A gate passes only when its one-sided lower confidence bound is strictly greater than 0.10. Deterministic paired percentile bootstrap intervals use fresh fixed sensitivity seeds and cannot override the primary statistic. The oracle arm is diagnostic only and cannot rescue a failed primary gate.

## 9. Positive-control continuity and classification

`threshold_at_4` must reach and pass the 40-case gate through the full 160→80→40 hierarchy before a common acquisition budget may be selected.

- `D2-vNext-S2-A0`: integrity failure or any schema below minimum analyzable N=88.
- `D2-vNext-S2-A1`: positive-control continuity not established.
- `D2-vNext-S2-A2`: positive control passes, but at least one non-control schema fails at 160.
- `D2-vNext-S2-A3`: all non-control schemas pass 160, but at least one fails 80; common confirmed budget = 160.
- `D2-vNext-S2-A4`: all pass 80, but at least one fails 40; common confirmed budget = 80.
- `D2-vNext-S2-A5`: all non-control schemas pass 40; common confirmed budget = 40.

A common budget is calibration output only. It is not schema-generalization or capability-reproduction evidence and cannot itself promote any registry node.

## 10. Execution topology and hard provider bounds

- 24 provider shards × 16 units = 384
- 6 shards/schema
- workflow max-parallel: 4
- local provider concurrency/shard: 1
- 55 scientific logical calls per complete unit
- 21,120 registered logical calls if all units complete
- at most two Hermes invocations per logical call under the exact bounded retry trigger
- hard physical-send ceiling: **36 per logical call**
- hard physical-send ceiling: **2,000 per shard**
- topology-wide hard physical-send ceiling: **48,000**
- unregistered outbound HTTP is blocked before transmission
- exact logical attribution is mandatory across primary and optional retry invocations
- all pinned Hermes provider workers must drain before HTTP hooks are restored
- aggregation and evaluation are credential-free
- provider and aggregate outputs are unclassified; only the frozen evaluator assigns `D2-vNext-S2-A0..A5`
- same-request-stream workflow reruns are prohibited

The campaign ceiling is a fail-closed safety cap, not an expected spend estimate. The expected path remains materially below it because format regeneration is conditional.

## 11. Evidence/privacy

Persist scientific outcomes plus bounded execution observability needed for audit: accepted attempt index, first-attempt parse validity/diagnostic, retry-used flag, second-attempt parse validity/diagnostic when used, completion flags, per-invocation/final SHA and length metadata, physical-send ledger, and scientific scores.

Do not persist raw credentials, raw provider error bodies/messages, or raw first-attempt response content solely for repair. Raw first-response content is never propagated to the retry prompt.

## 12. Authorization and durability

Issue #279 authorizes construction, deterministic materialization, tests, credential-free CI/preexecution, exact-candidate freeze, and exact-head review only.

**Scientific campaign execution and provider/model calls are not authorized by this plan.** Execution requires a separate explicit human authorization naming the exact frozen marker-absent candidate SHA and explicitly authorizing this scientific campaign and bounded provider execution up to the exact hard cap of **48,000 physical provider sends**. Authorization is candidate-specific and one-use only.

The sole-child authorization marker must be the only diff from the frozen candidate. Workflow reruns are prohibited after the request stream begins.

Execution authorization does not authorize evidence merge, registry promotion, Acceptance, D2e, Historical Substrate, deployment, publication, billing/purchase, credential changes, or permission changes.

## 13. Prohibitions

- no #221, D2d, D2d-S2, or consumed engineering stream rerun/rescue/replacement/reinterpretation
- no predecessor scientific task/seed/response reuse as an S2 observation
- no failed-unit replacement or imputation
- no adaptive N or post-outcome resizing
- no interim outcome-driven modification
- no threshold/schema retuning after outcome
- no favorable-subset claim
- no same-request-stream rerun or marker cycling
- no D2e destination reproduction or Capability Artifact export
- no registry mutation or Acceptance-plane promotion
- no Historical Substrate activation
