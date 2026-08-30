# D2-C2 Confirmatory Closeout

D2-C2 is closed as a completed confirmatory campaign.

## Identity

- Scientific candidate: `e8f719c3698b1f0180db07409c5eefd93facefbf`
- Authorization commit: `88ab2e26efaff6434606b16e9a4dd162784e6279`
- GitHub Actions run: `33312336871`
- Cohort hash: `8341d573da2d626858d25abfb381c499cc4d3c640749045b0141c985828fc676`
- Run conclusion: **success**

## Confirmatory disposition

- Classification: **D2-S3**
- Label: `stochastic_model_mediated_capability_reproduction_supported`
- Attempted pairs: 360
- Complete/analyzable pairs: 359
- Failed pairs: 1
- Minimum analyzable N: 330
- Integrity: **PASS**
- Global integrity defects: 0
- Pair integrity defects: 0

All preregistered serial gates passed:

| Gate | Estimate | One-sided 95% lower bound | Frozen threshold | Result |
| --- | ---: | ---: | ---: | --- |
| P0: source-developed − fresh | 0.243471 | 0.220815 | > 0.10 | PASS |
| P1: reproduced − description-only | 0.302141 | 0.278273 | > 0.10 | PASS |
| P2: 90%-fidelity margin | 0.111612 | 0.083951 | > 0.00 | PASS |

P2 aggregate reproduction fidelity was `1.127260` of source-developed accuracy.

## Durable evidence preservation

The repository preserves:

- the exact frozen evaluator result;
- the exact evaluation manifest;
- the exact aggregation manifest;
- a compact 360-index inferential ledger containing frozen-evaluator-verified arm-score arrays, the failed-pair summary, and ordered pair-record/pair-lock cryptographic commitments;
- SHA-256 commitments and GitHub artifact IDs/digests for the full canonical provider artifact and all 18 provider-shard artifacts.

Canonical provider JSON SHA-256:

`83de0f7d79b6356d590f55e048629829ccbd2eec67d8cc86d1605b2521d6b3aa`

Canonical GitHub Actions archive SHA-256:

`5f27258f1a27f7ed0c6bd4ac096a6d85f53fd003ee651dbf148a85ed560dc9cc`

Compact durable ledger SHA-256:

`11effc4f5584ef2ec03150e5e9e81877a62b9480fccf338c8b33a38d44fde17e`

The full canonical provider archive is not duplicated into the lightweight Git repository; its exact content is committed cryptographically by the hashes above. The compact ledger retains every pair-indexed inferential arm score (with `null` at the single failed pair) after the frozen evaluator verified complete-pair runner scores against the evaluation actions.

## Scientific claim ceiling

registered single-model synthetic individual-agent stochastic capability-reproduction mechanism only; no weight learning, cross-model/provider, naturalistic, team/swarm/institution, composition, market, environment-spawning, or production Historical Substrate claim

D2-C2 does not establish cross-model/provider transport, naturalistic transfer, team/swarm/institutional capability, composition, markets, environment spawning, or production Historical Substrate readiness.

## Governance

- The frozen evaluator does **not** authorize Mechanism Registry promotion.
- Acceptance-plane review remains separate and required.
- No automatic registry mutation occurred.
- Production/default Historical Substrate remains **OFF**.
- D2-C2 is not eligible for same-request-stream rerun.
- D2-C1 remains separately recorded as an apparatus failure with no evaluator-emitted classification.
- D2-C2 is a fresh successor study, not a rerun of D2-C1.
