# D2b plan — fresh stochastic capability-reproduction replication

Status: **prospective replication; no D2b provider outcome exists at plan freeze**.

Preregistration: issue #186.
Parent discovery study: D2-C2 / issue #180.
Accepted mechanism node: `d2_stochastic_capability_reproduction` at `discovery_supported`.

## Purpose

D2b is the fresh replication required before D2 may be considered for `internally_replicated`. It deliberately follows the D1→D1b precedent: preserve the scientific apparatus, create a new disjoint cohort, and do not retune from the favorable parent confirmatory outcome.

D2b is not a new mechanism node, not a posthoc child, and not a rerun or repair of D2-C1 or D2-C2.

## Parent scientific identity

The parent classifiable D2 study is D2-C2:

- scientific candidate `e8f719c3698b1f0180db07409c5eefd93facefbf`;
- authorization commit `88ab2e26efaff6434606b16e9a4dd162784e6279`;
- workflow `33312336871`;
- evaluator-emitted class `D2-S3`;
- result SHA-256 `f6010b83120c3767c518ffa75fd897b6321da17d190c42f783f1ee39a78ceec5`;
- attempted/analyzable/failed `360 / 359 / 1`;
- integrity PASS;
- independent Acceptance decision `ACCEPT discovery_supported` on issue #183.

D2-C1 remains an apparatus failure with no evaluator-emitted classification and contributes no scientific replication evidence.

## Frozen scientific mechanism

D2b retains the D2-C2 scientific treatment unchanged:

- provider: Z.AI;
- model: `glm-5-turbo`;
- temperature: `0.8`;
- thinking: disabled;
- structured JSON output;
- four arms: `fresh`, `description_only`, `reproduced`, `source_developed`;
- hidden-policy synthetic decision substrate unchanged;
- Capability Artifact v0.2 semantics/export boundary unchanged;
- 40 source-local development cases;
- 40 destination-local development cases;
- five development batches of eight;
- 32 held-out evaluation cases in four chunks of eight;
- no evaluation feedback;
- source/development private strategy remains non-exportable.

No D2-C2 outcome magnitude is used to modify any treatment component.

## Frozen inferential contract

D2b retains the D2-C2 inferential constitution exactly:

- experimental unit: paired fresh Source/Destination Field pair;
- attempted N: 360;
- minimum analyzable N: 330;
- no replacement or imputation;
- P0: `source_developed - fresh`, conventional threshold `+0.10`;
- P1: `reproduced - description_only`, conventional threshold `+0.10`;
- P2: `reproduced - 0.90 * source_developed`, threshold `0`;
- one-sided alpha `0.05`;
- fixed serial gatekeeping `P0 → P1 → P2`;
- paired normal primary tests / one-sided lower bounds;
- deterministic paired percentile-bootstrap sensitivity, 50,000 reps, seed `2026081516`, sensitivity only;
- no interim efficacy/futility analysis;
- no outcome-adaptive N increase;
- no threshold retuning;
- no same-request-stream rerun;
- frozen evaluator is the sole inferential classifier.

The parent D2-C2 observed effects are not planning alternatives. D2b intentionally retains the already-frozen 360/330 design rather than recomputing N from the favorable D2-C2 outcome.

## Fresh cohort

D2b reserves a new deterministic confirmatory namespace:

- seed base `3,200,000`;
- seed step `100`;
- source offset `+1`;
- destination offset `+2`;
- evaluation offset `+3`;
- pair indices `0..359`.

Case prefixes are frozen as:

```text
d2b-source-p{pair_index:03d}
d2b-destination-p{pair_index:03d}
d2b-eval-p{pair_index:03d}
```

The materialized cohort must be identity/seed/case disjoint from D2-C1, D2-C2, and all D2 calibration records. Source/destination development overlap and development/evaluation overlap must each be exactly zero. The exact 360-pair lock and aggregate hash must be generated and committed before the scientific candidate freeze.

## Execution durability

D2b retains the D2-C2 execution topology unchanged:

- 18 deterministic shards × 20 pair indices;
- shard local concurrency = 1;
- matrix max-parallel = 4;
- per-shard timeout = 240 minutes;
- max transport attempts per logical call = 8;
- minimum request-start interval = 0.35 seconds;
- successful shard output remains unclassified;
- no shard/job rerun after provider execution starts;
- missing shard becomes 20 registered failed attempted pairs with no synthetic arm/action data;
- credential-free aggregator canonicalizes exactly 360 attempted records;
- duplicate, foreign, preclassified, cohort/model/temperature/request drift is integrity failure;
- evaluator alone applies inferential classification.

One fully missing shard permits at most N=340; two fully missing shards imply at most N=320 and therefore an S4-class apparatus/min-N outcome.

## Replication classification

The ordinary D2 evaluator semantics are mapped one-to-one in the immutable D2b closeout:

```text
D2b-S0  source model-mediated capability development not established
D2b-S1  source developed; reproduction beyond description not established
D2b-S2  reproduction established; fidelity criterion not established
D2b-S3  fresh stochastic capability-reproduction replication supported
D2b-S4  apparatus/treatment-integrity failure or insufficient analyzable N
```

No manual scientific reclassification is permitted.

## Promotion rule

D2b-S3 is necessary but not sufficient for `internally_replicated`. A favorable preserved replication makes D2-C2 + D2b eligible for a separate independent Acceptance-plane review of exactly:

`discovery_supported → internally_replicated`

No automatic registry mutation is permitted.

## Claim ceiling

Even D2b-S3 remains the registered single-model synthetic individual-agent stochastic capability-reproduction mechanism only. It does not establish weight learning, cross-model/provider generalization, naturalistic validity, team/swarm/relationship/institution reproduction, capability composition, market viability, environment spawning, or production Historical Substrate authorization.

Production/default Historical Substrate remains OFF.
