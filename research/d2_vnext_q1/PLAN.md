# D2-vNext-Q1 acquisition qualification plan

**Status:** construction-only / provider execution not authorized  
**Tracking:** #290  
**Construction PR:** #291  
**Predecessor evidence:** consumed D2-vNext-S2 run `35909017872`, closeout #287, attrition forensics #289.

## Objective

D2-vNext-Q1 qualifies the reliability and observability of the source-acquisition apparatus required by a future fresh confirmatory stream. It does **not** test source-capability effects, select a 40/80/160 development budget, reinterpret D2-vNext-S2, or authorize Acceptance, registry action, D2e, deployment, or Historical Substrate activation.

The qualification endpoint is whether a frozen acquisition mechanism can produce complete, evaluator-analyzable pairs for every registered schema with a prospectively bounded resource envelope.

## Frozen supported-product mechanism

Q1 preserves the D2-vNext-S2 scientific-call mechanism unless this construction is explicitly superseded before any provider execution:

- requested model: `glm-5.3`;
- temperature: `0.8`;
- thinking: disabled;
- response format: JSON object under the exact structured completion contract;
- qualified terminal-completion adapter semantics;
- at most one bounded format-regeneration retry under the existing eligibility rule;
- no raw first-response content supplied to retry prompts or persisted in failure evidence;
- no tools, memory, persistent session, fallback model, or unregistered outbound HTTP;
- fail-closed physical-send attribution, cleanup, and accounting.

Instrumentation may observe additional bounded diagnostic state but may not change prompts, retries, acceptance semantics, or scientific outputs.

## Frozen fresh cohorts

Q1 uses namespace `rw.d2-vnext-q1-acquisition-qualification.v1`. The deterministic cohort commitments are:

- Q1-A cohort SHA-256: `21ae386da6fdba2883a331864fcaffc51f9fa8adb58aa43ee9d68519cadc3686`;
- Q1-B cohort SHA-256: `41124075eeda43439b392997b090ed7fe11275271b4bae86bc619371f86a750e`.

Q1-A and Q1-B seed sets are disjoint, and both are prospectively checked for zero overlap with registered predecessor seed namespaces. Cohort locks and shard maps regenerate byte-for-byte in credential-free CI.

## Mixed-schema sharding

Q1 removes the whole-shard schema/time coupling present in S2. Every 16-pair shard contains exactly four pairs from each registered schema:

- `threshold_at_4`: 4
- `parity_pair`: 4
- `interval_pair`: 4
- `pairwise_order`: 4

Pair order is deterministic and interleaved. Q1 uses a fresh namespace with zero seed overlap with S2 and predecessors.

## Transport/resource topology

Per 16-pair shard:

- maximum registered logical calls: `880`;
- maximum physical sends per logical call: `36`;
- maximum physical sends per shard: `1,152`;
- no cross-shard budget borrowing;
- provider shard max-parallel: `4`.

The 1,152-send shard bound corresponds to 72 physical sends per attempted pair at topology level while allowing pair-level variation. It is chosen to preserve a later 48,000-send confirmatory campaign envelope.

## Q1-A — bounded screen

Q1-A is a fresh diagnostic screen:

- 16 attempted pairs/schema;
- 64 total attempted pairs;
- 4 mixed-schema shards;
- 4,608 maximum physical sends.

Q1-A continuation requires all of:

1. credential-free construction and observability tests green;
2. all provider shards complete with clean transport/accounting integrity;
3. every terminal pair failure carries the full bounded terminal-failure record;
4. each schema has at least 12/16 complete evaluator-analyzable pairs;
5. no terminal failure is unclassified because required diagnostic state was omitted.

Q1-A observations are never pooled into the primary Q1-B completion-rate estimator. Failure of Q1-A stops the stream. Mechanism changes after Q1-A require a new qualification revision; there is no adaptive Q1-A rescue.

Q1-A classifications are frozen as:

- `D2-vNext-Q1-A0`: integrity or terminal-failure-observability failure;
- `D2-vNext-Q1-A1`: minimum screen-completion failure;
- `D2-vNext-Q1-A-PASS`: bounded screen passed and Q1-B may be submitted for a separate authorization review.

`A-PASS` does not itself authorize Q1-B execution.

Q1-A provider execution requires a separate explicit human authorization naming the exact frozen candidate SHA and authorizing at most 4,608 physical provider sends.

## Q1-B — independent validation

Q1-B is preconstructed but separately authorized only after Q1-A passes unchanged:

- 96 attempted pairs/schema;
- 384 total attempted pairs;
- 24 mixed-schema shards;
- 27,648 maximum physical sends.

To preserve execution-time observability, Q1-B is scheduled as six sequential waves of four mixed-schema shards. Shards within a wave may run in parallel up to four; wave `k+1` does not start until wave `k` completes. Every shard artifact carries an execution-wave sidecar, and the canonical aggregate preserves an execution-wave index.

The Q1-B evaluator reports acquisition completeness, terminal-failure observability, integrity, uncertainty, and resource feasibility. It must not calculate or emit developed-vs-fresh effect gates.

## Statistical qualification rule

The future confirmatory target is a probability of at least 0.95 that **all four schemas** clear the frozen `N>=88` analyzable-pair floor.

Allocate the joint failure budget by union bound:

`q_s = 1 - 0.05/4 = 0.9875`.

For each schema `s`, Q1-B computes a one-sided exact Clopper-Pearson lower confidence bound `p_L,s` with per-schema alpha `0.0125` (98.75% one-sided confidence). This provides simultaneous >=95% coverage across the four completion probabilities without assuming cross-schema independence.

For each schema derive the smallest integer `N_s >= 88` satisfying:

`P[Binomial(N_s, p_L,s) >= 88] >= 0.9875`.

S2 observations are not pooled into this estimator.

## Resource-feasibility gate

The acquisition mechanism is resource-feasible for a future confirmatory design only if:

`sum_s N_s <= 640`.

At 16 attempted pairs/shard this can be packed into at most 40 shards. Under the frozen 1,152-send shard ceiling, that is a 46,080-send topology ceiling, leaving 1,920 sends of headroom under the 48,000-send campaign boundary.

If `sum_s N_s > 640`, Q1-B returns a resource-feasibility failure. It does not authorize weakening `N=88`, dropping a schema, increasing the campaign cap post hoc, or substituting descriptive S2 effects.

## Q1-B classification and independent exchangeability review

The credential-free Q1-B evaluator freezes three machine classifications:

- `D2-vNext-Q1-B0`: integrity or terminal-failure-observability failure;
- `D2-vNext-Q1-B1`: future confirmatory resource-feasibility failure;
- `D2-vNext-Q1-B2`: resource-feasible **pending independent exchangeability review**.

`B2` is deliberately not final qualification PASS.

For a B2 result, an independent reviewer must use the frozen `D2_VNEXT_Q1_B_EXCHANGEABILITY_REVIEW_SCHEMA.json`. The review is bound to the exact provider-output and Q1-B evaluation hashes and must inspect completion by schema, shard, execution wave, plus transport/runtime metadata. Developed-vs-fresh effect sizes, scientific-gate p-values/confidence bounds, and oracle performance as capability evidence are forbidden review inputs.

The separate finalizer accepts only the frozen review verdicts:

- `PASS` -> `D2-vNext-Q1-B-PASS`;
- `INCONCLUSIVE_NONEXCHANGEABLE` -> `D2-vNext-Q1-B-INCONCLUSIVE_NONEXCHANGEABLE`.

No favorable post-hoc statistical model may replace the frozen binomial completion model. Even `B-PASS` qualifies only the tested acquisition mechanism and resource envelope; it does not authorize a future confirmatory provider run.

## Bounded terminal-failure observability

Every fatal required logical call must preserve, without raw response content:

- pair public ID and pair index;
- schema, arm, and phase;
- logical-call index;
- first-attempt runtime/completion flags, exact-parse validity, bounded parse diagnostic, physical sends, transport cleanliness, attribution integrity, and terminal-adapter reason;
- retry eligibility and whether retry was used;
- the same bounded second-attempt fields when present;
- whether an accepted exact completion existed;
- bounded error type and fingerprint.

The failure record is evidence, not a retry mechanism.

## Construction requirements

Before any provider authorization, construction must provide:

- `D2_VNEXT_Q1_CONTRACT.json`;
- `D2_VNEXT_Q1_REQUEST_PLAN.json`;
- `D2_VNEXT_Q1_SCHEMA_SUITE.json`;
- `D2_VNEXT_Q1_FAILURE_OBSERVABILITY_SCHEMA.json`;
- `D2_VNEXT_Q1_B_EXCHANGEABILITY_REVIEW_SCHEMA.json`;
- Q1-A and Q1-B sample-size/cohort-lock/shard-map commitments;
- deterministic materialization under a fresh namespace;
- enhanced bounded failure capture;
- stage-aware aggregation and a qualification-only evaluator;
- independent Q1-B finalization logic;
- credential-free fixtures for first-attempt failure, retry-eligible parse failure, retry failure, terminal-adapter rejection, accepted completion, budget/attribution defects, raw-content non-retention, and finalization boundaries;
- marker-triggered Q1-A/Q1-B workflows that remain inert while markers are absent;
- CI proving byte-for-byte materialization and absence of an execution marker.

## Governance

Construction is authorized by #290. Provider/model execution is not. There is no Q1 execution marker in the construction candidate. Q1-A and Q1-B are separate provider-execution authorization boundaries. Q1 success would qualify only the tested acquisition mechanism; it would not establish a scientific capability effect, a confirmed development budget, provider/model generalization, Acceptance, registry promotion, production readiness, or Historical Substrate activation.
