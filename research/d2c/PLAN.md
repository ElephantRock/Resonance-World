# D2c — schema generalization of stochastic capability reproduction

Status: **prospective apparatus construction; zero substantive D2c provider calls authorized**.

Preregistration: issue #192.
Registry node: `d2_stochastic_capability_reproduction` at `internally_replicated`.
Base evidence: D2-C2 + D2b, independently accepted on issue #190.

## Purpose

D2c tests the next governance rung: whether the already internally replicated stochastic capability-reproduction mechanism generalizes across prospectively frozen task schemas while holding the provider/model and reproduction mechanism fixed.

D2c is not a new mechanism node and is not a rerun, repair, or replacement for D2-C1, D2-C2, or D2b. The only future promotion that D2c may make eligible for independent review is:

`internally_replicated -> schema_generalized`

## Novelty level

The study is prospectively bounded to governance novelty level **G2: new schema, same abstract operator**.

All D2c schemas retain the same abstract operator:

1. four public integer features `f0..f3`, each in `0..7`;
2. a hidden local rule converts the features into two latent bits;
3. a fresh opaque one-to-one mapping converts the two-bit state into one of `KAPPA`, `MICA`, `ORBIT`, `VELA`;
4. source and destination agents must infer their local hidden policy through local outcome-bearing development experience;
5. the public Capability Artifact communicates production conditions but never source-private policy parameters or learned strategy.

The latent feature-to-bit schema changes prospectively across three new families:

- `parity_pair`;
- `interval_pair`;
- `pairwise_order`.

The legacy D2 threshold-at-4 family is not counted as a D2c test schema.

## Frozen mechanism invariants

D2c retains the validated D2 treatment structure:

- provider: Z.AI;
- model: `glm-5-turbo`;
- temperature: `0.8`;
- thinking: disabled;
- structured JSON response;
- action vocabulary: `KAPPA`, `MICA`, `ORBIT`, `VELA`;
- four arms: `fresh`, `description_only`, `reproduced`, `source_developed`;
- Capability Artifact v0.2 semantics and export-safety boundary;
- source development: 40 cases, five batches of eight;
- destination development: 40 cases, five batches of eight;
- held-out evaluation: 32 cases, four chunks of eight;
- local outcome-bearing feedback only during labeled development;
- no evaluation feedback;
- source-private strategy/policy state is never exported.

The generic task-ecology description for each schema is visible to all arms, as in D2. The reproduced arm additionally receives the public Capability Artifact; description-only receives unlabeled local practice but no Artifact and no correctness labels.

## Frozen schema suite

### parity_pair

Two undisclosed distinct coordinates are selected. Each contributes one bit equal to `value mod 2`. The coordinate identities and action permutation are local secrets.

### interval_pair

Two undisclosed distinct coordinates are selected. Each contributes one bit indicating whether the value lies in the registered interval `2..5` inclusive. The coordinate identities and action permutation are local secrets.

### pairwise_order

The four coordinates are partitioned into two undisclosed ordered pairs. Each contributes one bit indicating whether the first coordinate in that pair is greater than or equal to the second. The pair identities/order and action permutation are local secrets.

## Fresh data contract

Each schema has exactly 180 fresh paired Source/Destination Fields, for 540 attempted pairs total.

Seed bases:

- parity_pair: `4,200,000`;
- interval_pair: `4,400,000`;
- pairwise_order: `4,600,000`.

Within each schema, local pair index `j in 0..179` uses `base + 100*j` with source/destination/evaluation offsets `+1/+2/+3`.

The materializer must prove:

- zero overlap with D2-C1 (`1,200,000` namespace), D2-C2 (`2,200,000`), and D2b (`3,200,000`);
- zero cross-schema D2c seed overlap;
- zero source/destination feature overlap within every pair;
- zero development/evaluation feature overlap within every pair;
- exact 540-pair identity and exact deterministic 27-shard coverage.

## Inferential contract

The experimental unit is one fresh paired Source/Destination Field pair within one schema.

For each schema independently:

- attempted N: 180;
- minimum analyzable N: 165;
- P0: `source_developed - fresh`, conventional threshold `+0.10`;
- P1: `reproduced - description_only`, conventional threshold `+0.10`;
- P2: `reproduced - 0.90 * source_developed`, threshold `0`;
- one-sided alpha `0.05`;
- serial gatekeeping `P0 -> P1 -> P2`;
- paired normal primary statistic and one-sided lower confidence bound;
- deterministic paired percentile bootstrap sensitivity, 50,000 reps, prospectively fixed seed `2026090101`, sensitivity only.

No replacement, imputation, interim outcome decision, adaptive sample size, threshold retuning, or same-request-stream rerun is allowed.

### Program-level generalization rule

D2c supports candidate G2 schema generalization **only if all three schemas independently satisfy integrity, minimum N, P0, P1, and P2**.

This is a conjunctive intersection-union decision. No average effect, pooled effect, or favorable schema may rescue a failed schema. Each schema uses the same serial alpha-0.05 gate; the all-schema conjunction does not introduce a compensatory multiplicity family.

## Sample-size justification

The planning alternative is conventional and prospective, not estimated from D2-C2 or D2b outcomes:

- P0/P1 planning effect: `+0.20`, tested against `+0.10`;
- P2 transformed planning effect: `+0.10`, tested against `0`;
- planning paired SD: `0.40` for all gates;
- target power: `0.90` one-sided at alpha `0.05`.

The normal approximation requires approximately 138 analyzable pairs for a 0.10 margin at SD 0.40. The frozen minimum N=165 yields approximately 0.941 power under that planning alternative; N=180 yields approximately 0.956. The larger attempted N also provides limited apparatus-loss tolerance without adaptive replacement.

## Execution durability

After scientific-candidate freeze and separate authorization, the intended topology is:

- 27 deterministic provider shards x 20 pairs;
- nine shards per schema;
- local provider concurrency 1;
- workflow matrix max-parallel 4;
- 240-minute shard timeout;
- max eight transport attempts per logical call;
- minimum request-start interval 0.35 s;
- 31 logical calls per fully completed pair;
- 16,740 logical calls campaign-wide before retries;
- no shard/job rerun after provider execution begins;
- missing shard records 20 registered failed attempted pairs without regeneration;
- credential-free aggregation;
- frozen credential-free evaluator as sole scientific classifier.

A fully missing shard in one schema leaves at most N=160 for that schema, below minimum N=165, so any full missing shard necessarily prevents a favorable D2c schema-generalization classification. This is deliberate: a schema-generalization claim cannot silently drop an entire schema shard.

## Candidate classifications

- `D2c-S0`: integrity failure or any schema below minimum analyzable N;
- `D2c-S1`: apparatus valid, but at least one schema fails P0;
- `D2c-S2`: all schemas pass P0, but at least one schema fails P1;
- `D2c-S3`: all schemas pass P0/P1, but at least one schema fails P2;
- `D2c-S4`: all three new schemas independently pass P0/P1/P2; candidate G2 schema generalization supported.

The evaluator is the sole classifier. Provider shards and aggregation remain unclassified.

## Promotion rule

`D2c-S4` is necessary but not sufficient for `schema_generalized`. Evidence must first be preserved on `main`, then a separate independent Acceptance-plane reviewer must adjudicate exactly:

`internally_replicated -> schema_generalized`

No D2c workflow may mutate the Mechanism Registry.

## Claim ceiling

Even `D2c-S4` supports only the registered **single-model synthetic individual-agent G2 schema-generalization** claim for Z.AI `glm-5-turbo` under the frozen three-schema suite.

It does not establish G3 abstract-operator generalization, model/provider generalization, naturalistic validity, team/swarm/relationship/institution reproduction, capability composition, market viability, autonomous environment spawning, production readiness, or production Historical Substrate authorization.

Production/default Historical Substrate remains **OFF**.
