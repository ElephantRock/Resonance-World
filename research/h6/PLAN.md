# H6 — Relevance Gating of Institutional Memory State

Preregistration: #154  
Frozen World base: `935e0463acc88f7f7756861d734eeba7b4efb034`  
H5 immutable source candidate: `7afa2d139049b1fdb80de2a95d76b49430b6a046`  
ContextGraph release: `b896891108fd954869a8cd0423f6e8440ab0cdc0`  
Branch: `experiment/h6-relevance-gated-memory`

H6 is a new confirmatory mechanism-identification study motivated only after H5 was frozen as `historical_substrate_institutional_mediation_failed`. It asks whether an institutional state channel has a relevance-dependent effect: useful when it summarizes task-relevant routine history, but harmful when the same state channel is present with no decision-relevant content.

## Frozen panel

H6 reuses the same 12 opaque unit truths and the same six canonical g3 records per unit from the H5 fixture lineage. No new scientific fact is introduced. It runs six fresh stochastic replicate cohorts and four 2×2 factorial arms, with exactly two analyst calls plus one chair call per organization decision cell:

- 12 units × 6 replicates × 4 arms = 288 organization cells;
- 288 × 3 = 864 logical `glm-5-turbo` calls before transport retries.

All calls are isolated. H6 member identities are fresh and carry no conversation state from H5.

## Treatments

Factor F — governance framing: `static` versus `persistent`.

Factor S — institutional state channel: `no_state` versus `with_state`.

Arms:

1. `static_no_state`
2. `persistent_no_state`
3. `static_with_state`
4. `persistent_with_state`

Role routing, authority governance, offered actions, authority notices, canonical evidence, model settings, call count, and output budget are held constant across all arms. Only the registered framing/state factors vary.

For `routine_transfer`, `with_state` contains the deterministic trusted-procedure digest reconstructible from the same public canonical records. For `cross_role_composition` and `authority_conflict`, `with_state` contains only `status=not_applicable`, carrying no task fact. Thus state-channel presence on non-routine units manipulates representation/attention load rather than information.

## Evidence-interface normalization

H5 Gate 10 exposed free-form evidence-ID output noise. H6 removes that common-mode interface confound prospectively by exposing canonical evidence as local slots E1–E6. Analysts may cite only their allocated slots; the chair may cite any E1–E6 slot. The evaluator maps slots deterministically back to frozen record IDs. This normalization is identical in all arms and changes no scientific evidence.

## Model and transport

- model `glm-5-turbo`
- endpoint `https://api.z.ai/api/coding/paas/v4/chat/completions`
- `do_sample=true`
- temperature 0.8
- thinking disabled
- stream false
- JSON object output
- output cap 96 tokens

H6 prospectively starts with the H5-proven transport profile: 2.0-second global physical-request start interval, concurrency 2, maximum 12 transient HTTP/timeout/JSON-shape/vocabulary attempts, and long 429 backoff respecting `Retry-After` within the registered cap. No retry may depend on scientific correctness.

## Primary mechanism signature

Two exact one-sided paired discordance/McNemar tests with Holm FWER α=0.05:

**P1 — relevant-state benefit.** On `routine_transfer`, pool across governance framing and compare matched `with_state` versus `no_state` for each `(unit, replicate, framing)` pair. Paired n=48. Required direction: `with_state > no_state`.

**P2 — irrelevant-state burden.** On `cross_role_composition` plus `authority_conflict`, pool across governance framing and compare matched `no_state` versus `with_state` for each `(unit, replicate, framing)` pair. Paired n=96. Required direction: `no_state > with_state`.

PASS requires both contrasts to be Holm-rejected in the registered direction and each absolute correctness difference to be at least 0.10. P1 must also point positive in at least five of six replicate cohorts. No secondary contrast can rescue a failed primary gate.

Secondary diagnostics decompose persistent-framing effects and state effects within each non-routine family.

## Gates

Gates 0–15 are frozen in #154: safety boundary, fixture identity, fresh successor state, information parity, equal compute, exact 2×2 protocol, authority separation, call isolation, transport, evaluator-private exclusion, evidence-slot integrity, state reconstruction/no-new-information parity, P1, P2, replicate/causal audit integrity, and byte-identical two-run frozen evaluation.

PASS: `historical_substrate_relevance_gated_memory_mechanism_pass`.

FAIL: `historical_substrate_relevance_gated_memory_mechanism_failed`.

A complete FAIL is preserved without confirmatory retuning. Transport-incomplete attempts without a complete live artifact/evaluator are unclassifiable.

Production/default Historical Substrate remains disabled regardless of outcome.
