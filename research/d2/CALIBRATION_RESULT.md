# D2-0 calibration result — stochastic model-mediated capability substrate

Status: **complete development-only calibration; confirmatory handoff criterion not met**.

D2-0 is not confirmatory evidence, has no D2 S-classification, and cannot promote the Mechanism Registry.

Authoritative completed calibration workflow: `31890035170`  
Scientific/development branch: `experiment/d2-0-stochastic-calibration`  
Execution head: `2a418668d587940ef4775e9f8ef71ff71537fb4a`  
Artifact: `9248350146` (`sha256:e7e95a5e6ab14fd77cff9647f573c8fac23ebbabb6c49a509dd825fb1eb6df3c`)  
Frozen calibration output SHA-256: `2d3fd4a023c2333b9dee8fdf115591d984eacc5d9a54ca6c2ea7a75ecdc0304b`  
Calibration report SHA-256: `c5fdc838910c1e60f699fdec67f978e278dd2103e9dec6ace0ee487e2be6fd4d`

## Transport history

The first v0.1 provider workflow `31889041385` was incomplete because one 24-action evaluation request exhausted the strict JSON/action-count retry budget. It emitted no campaign report or scientific calibration artifact. That failure is preserved as a development transport record, not interpreted as a scientific result.

Transport repair 1 was frozen prospectively before the successful run. It changed only evaluation batching/parser robustness: 24 held-out calibration cases became three deterministic 8-case chunks for every arm; `actions` remained mandatory/exact-length/vocabulary-checked; private `strategy` became optional/carry-forward; harmless extra keys were ignored; no evaluation outcomes were returned. Task families, pair cohort, development examples, feedback labels, Artifact boundary, model line, temperature, and comparisons were unchanged.

A subsequent workflow `31889900677` failed in documentary preflight before any provider call; its literal assertions were fixed without scientific or transport-treatment changes. The completed run is therefore `31890035170`.

## Completed calibration panel

- model: Z.AI `glm-5-turbo`
- paired-development temperature: `0.8`
- 8 frozen Field pairs
- 16 source-local development cases per pair
- 16 destination-local development cases per pair
- 24 held-out calibration evaluation cases per pair
- source/destination development overlap: exactly 0
- development/evaluation overlap: exactly 0
- reproduced and description-only logical-call accounting: equal
- developed arms: 5 logical calls per pair
- fresh: 3 logical calls per pair
- sampling panel: 18 logical calls
- total: 162 logical calls, 167 physical attempts
- retry frequency: 2.994%; 3 timeout retries and 2 format/value retries
- all Capability Artifact export audits passed
- no confirmatory cohort or holdout was created or used
- production/default Historical Substrate remained OFF.

## Descriptive arm scores

| arm | mean held-out calibration score | SD | min | max |
|---|---:|---:|---:|---:|
| `fresh` | 24.479% | 12.879pp | 12.500% | 50.000% |
| `description_only` | 21.875% | 5.786pp | 12.500% | 29.167% |
| `source_developed` | 26.562% | 7.695pp | 16.667% | 37.500% |
| `reproduced` | 28.125% | 11.302pp | 20.833% | 54.167% |

Descriptive paired contrasts only:

- P0-like source − fresh: **+2.083pp**, paired SD **15.749pp**;
- P1-like reproduced − description-only: **+6.250pp**, paired SD **10.681pp**;
- P2-like reproduced − source: **+1.562pp**, paired SD **14.423pp**.

These are calibration quantities, not confirmatory estimates. No p-values, confidence-based claims, SESOI decisions, or non-inferiority conclusions are authorized from D2-0.

## Learning-curve diagnostic

Mean source scores across the two development batches and held-out calibration evaluation were approximately:

```text
28.125% → 25.000% → 26.562%
```

Mean reproduced scores were:

```text
29.688% → 23.438% → 28.125%
```

Mean description-only scores were:

```text
26.562% → 29.688% → 21.875%
```

With four registered action tokens, 25% is the uniform-action reference. The source arm therefore remained near that reference and did not show the nontrivial developmental trajectory required by the prospective D2-0 handoff criterion.

## Sampling characterization

All 18 sampling-characterization calls eventually satisfied the structured-output contract without retry.

| temperature | valid-contract rate | unique-response rate | repeat-response rate | action entropy | score variance |
|---|---:|---:|---:|---:|---:|
| 0.4 | 100% | 33.3% | 66.7% | 2.000 bits | 0.01042 |
| 0.8 | 100% | 66.7% | 33.3% | 1.932 bits | 0.00260 |
| 1.0 | 100% | 50.0% | 50.0% | 1.959 bits | 0.00000 |

The provider/output contract is sufficiently measurable for further development calibration, but D2-0 does not select a confirmatory sampling setting.

## Prospective handoff decision

`CALIBRATION_PLAN.md` requires all of the following descriptively before D2 proper may proceed: nontrivial source capability development, no ceiling saturation, a potentially powerable reproduced-vs-description contrast, estimable pair variation, reliable structured outputs, and exact export-boundary enforcement.

D2-0 satisfies the structural/integrity conditions and does not show ceiling saturation. Pair variation is estimable, and a positive reproduced-minus-description calibration contrast exists. **However, the required source capability-development condition is not met:** source performance remains near the 25% uniform-action reference with no coherent upward learning curve.

Therefore:

> **D2 proper is not authorized from this calibration. Revise the development substrate while D2 remains pre-confirmatory, document the revision prospectively, and rerun D2-0 on development-only data.**

The revision should target capability learnability rather than the desired reproduction contrast. Appropriate development-only levers include reducing hidden-policy compositional complexity, adding a staged curriculum, and/or increasing local outcome-bearing development budget. No confirmatory cohort exists, so such revision remains within the prospectively permitted D2-0 development phase.

Production/default Historical Substrate remains OFF.
