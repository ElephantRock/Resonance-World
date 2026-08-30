# D2-C2 prospective execution-repair scaffold

Status: **prospective scaffold only; zero D2-C2 provider calls authorized.**

Program authority: issue #180.
Parent program issue: #167.

## Why C2 exists

D2-C1 (`workflow 31895957256`) passed its marker/candidate integrity gate and entered provider execution, but the monolithic provider process was cancelled at the frozen 300-minute job timeout before it emitted a provider artifact. The frozen evaluator therefore never ran and no inferential D2 result exists from C1.

C1 is immutable and cannot be rerun. The exact C1 request stream, seed namespace, and authorization marker are retired.

D2-C2 is a fresh-data successor on the same scientific D2 mechanism node. It repairs only execution durability and workflow topology. It does not use unavailable C1 scientific outcomes to tune the mechanism.

## Scientific contract ceiling

C2 carries forward the C1 scientific contract unless a separate prospective amendment is justified and frozen before any C2 provider observation:

- Z.AI `glm-5-turbo`, temperature 0.8, thinking disabled;
- four arms: fresh, description-only, reproduced, source-developed;
- 40 source-local and 40 destination-local development cases;
- five development batches of eight;
- 32 held-out evaluation cases in chunks of eight;
- Capability Artifact v0.2 export boundary;
- P0 SESOI +0.10, P1 SESOI +0.10, P2 90% source-accuracy preservation;
- one-sided alpha 0.05 with serial P0 -> P1 -> P2 gatekeeping;
- 360 attempted fresh Field pairs, minimum analyzable N 330;
- no pair replacement, imputation, interim efficacy/futility stopping, threshold retuning, or outcome-adaptive N increase;
- evaluator remains credential-free and is the only inferential classifier;
- no automatic registry promotion;
- production/default Historical Substrate remains OFF.

## Fresh cohort namespace

C1's confirmatory seed namespace beginning at 1,200,000 is retired.

C2 prospectively reserves:

```text
base = 2,200,000
step = 100
source offset = +1
destination offset = +2
evaluation offset = +3
```

The exact 360-pair C2 cohort/holdout must be generated and hash-frozen on the final scientific candidate before any authorization marker or provider call. C2 must reuse no C1 case identifier, identity, seed, request ID, or holdout.

## Durable shard topology

Target provider topology:

- 18 deterministic shards;
- 20 registered pair indices per shard;
- shard 0 = pairs 0..19, shard 1 = 20..39, ..., shard 17 = 340..359;
- local provider-call concurrency = 1 per shard;
- matrix `max-parallel = 4` so aggregate provider-call concurrency never exceeds four;
- target provider timeout = 240 minutes per shard;
- no provider shard/job rerun after execution starts;
- each successful shard emits an unclassified immutable artifact for exactly its registered range.

A credential-free aggregator must run even when one or more provider shards fail. It may synthesize only **failure placeholders for missing registered pair indices**; it may never synthesize actions, scores, strategies, provider calls, or successful pair records.

The aggregator must produce one canonical 360-attempt provider-output object and enforce:

```text
union(pair_indices) == {0, ..., 359}
no duplicate indices
no foreign indices
no shard range drift
no cohort-hash drift
no model/request-plan drift
no classified shard input
no production Historical Substrate
```

If a shard artifact is missing, its 20 registered pairs are explicit failed attempted pairs. One missing full shard leaves at most N=340; two missing full shards leave at most N=320 and therefore force D2-S4 under the unchanged minimum-N rule.

## Zero-provider implementation gates

Before a candidate can be called frozen, tests/audits must prove at minimum:

1. the 18×20 shard map exactly covers 0..359 once;
2. shard selection cannot alter pair seeds/cases or arm semantics;
3. each shard has the same per-pair logical-call contract as C1;
4. local concurrency 1 + matrix max-parallel 4 preserves aggregate concurrency <=4;
5. aggregator canonicalization is deterministic;
6. missing-shard placeholders contain no scientific outcome data;
7. duplicate/foreign/mismatched shard data fail closed;
8. evaluator reruns byte-identically over canonical provider output;
9. provider credentials are absent from preexecution audit, aggregation, and evaluation jobs;
10. the candidate contains no D2-C2 authorization marker.

## Authorization separation

No executable D2-C2 marker is defined by this scaffold. No provider workflow should trigger from this document or from issue #180.

After the complete C2 apparatus, request plan, sample-size record, cohort lock, shard map, aggregator, evaluator, and tests are frozen and pass general CI plus a dedicated zero-provider audit, the exact candidate SHA must be posted prospectively to issue #180. Only then may a subsequent commit add the sole authorization marker as the only post-lock change.

## C1 preservation pointer

The machine-readable C1 failure closeout is `research/d2/D2_CONFIRMATORY_C1_CLOSEOUT.json`. It records the cancelled workflow, absence of provider artifacts, skipped evaluator, null evaluator classification, no-rerun rule, and unchanged registry/Historical Substrate authority.
