# D2c schema-generalization closeout

D2c completed as a valid negative confirmatory study.

- Scientific candidate: `1db50eea77e71cda64b2f7dc0ec0bfb8ffb9e98c`
- Authorization commit: `0104de9d8b221eb49b555e88fabca91ad946a715`
- Authoritative workflow: `33470898083`, attempt 1, **SUCCESS**
- Provider shards: **27/27 successful**
- Attempted / complete / failed pairs: **540 / 540 / 0**
- Analyzable pairs: **180 per schema**
- Frozen evaluator: **D2c-S1 — schema_generalization_source_development_not_established_all_schemas**
- Evaluator result SHA-256: `066b846e7fe9b9dc6abd1210fa297788c27a3161d70090a38a1d155133521489`
- Canonical provider output SHA-256: `245276672dfe4615d53acc7e6d9e631ec43ff14b6b05d2a0ed14f312c4ad4d63`

## Decisive result

The program failed at the registered P0 source-development gate in every held-out schema family:

| Schema | Source - fresh mean | One-sided 95% lower bound | P0 threshold | Result |
| --- | ---: | ---: | ---: | --- |
| `interval_pair` | 0.12048611 | 0.09562993 | 0.10 | FAIL |
| `parity_pair` | 0.07222222 | 0.05219620 | 0.10 | FAIL |
| `pairwise_order` | 0.03906250 | 0.02003347 | 0.10 | FAIL |

Because the preregistered gatekeeping order is P0 → P1 → P2, P1 and P2 were not confirmatorily entered. Their descriptive values are preserved in the frozen evaluator result but cannot rescue the study.

## Scientific interpretation

D2c does **not** establish G2 schema generalization. The valid negative result localizes the immediate bottleneck upstream: robust source capability acquisition was not established under the frozen 40-case development protocol on any of the three new schemas.

This does not reverse or invalidate the earlier D2-C2/D2b evidence for same-schema stochastic capability reproduction. It constrains the next question: characterize the source capability-acquisition envelope prospectively, then test reproduction again on new held-out schemas using a separately frozen acquisition protocol.

No D2c rerun, adaptive-N rescue, threshold change, schema selection, or favorable-subset claim is authorized.

## Evidence commitments

- Evaluation artifact `9812491165`, digest `sha256:aa65fe16b54a25136dd5421d7cd7e2c367213e38b5f33cfdbcc966a3580a8dd3`
- Canonical provider artifact `9812464076`, digest `sha256:a086d1fcdae18dde10842be8fb1e37984d1a7ae0fe2c72c61d19fd2648fd1e19`
- Cohort-pairs SHA-256 `559a4420a1d592d85fa350d087a8d4b945f4bf882a683c660a77cf9fdb6b9c04`
- Cohort-lock SHA-256 `5701669d2594aaeb49ad0bc8c682b61c3cbfde6a1cb496bbf63b265a6ce26f00`
- Shard-map SHA-256 `2f23b0a940a6a2b4bd71aedf7d6d008939f5e89e6978284eac304e060e0009b5`

The frozen evaluator output and evaluation manifest are committed beside this closeout.

## Governance

No registry transition is eligible. `d2_stochastic_capability_reproduction` remains `internally_replicated`. No independent Acceptance-plane promotion review is entered for D2c-S1.

Production/default Historical Substrate remains **OFF**.
