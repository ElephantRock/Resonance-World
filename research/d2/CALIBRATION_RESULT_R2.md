# D2-0 R2 calibration result — learnability-focused stochastic substrate

Status: **complete development-only calibration; conventional source-learnability handoff gates passed**.

D2-0 R2 is not confirmatory evidence, has no D2 S-classification, and cannot promote the Mechanism Registry.

Authoritative completed workflow: `31891269604`  
Scientific/development branch: `experiment/d2-0-learnability-r2`  
Frozen pre-provider candidate: `a9dc3bb0ae407ec877126d1a0d04a8fdc6c2c092`  
Authorization-marker execution head: `db9c3c7f1a85c1b2674f312083b56ee1cef4e398`  
Prospective issue #167 lock comment: `5302778520`  
Artifact: `9248780667` (`sha256:99c106d19c6343ba5a0a2678e1bfea722f8aa498c52eeb44f246a427b614f72c`)  
Frozen calibration output SHA-256: `c55e4e5e0c41a81173ff4da33eeef011ec7c566a940d0280e157f6d9312be643`  
Calibration report SHA-256: `bccb960a39c6ab06aad322874626185719a42968acbcf0067dfaf97131dcf197`  
Manifest SHA-256: `ff41bf0f86ccb528f17ab58295e772fbe220b70a162da2bbc801a6d2260ef82d`

## Prospective revision

R2 was motivated only by the R1 failure to produce a clearly learned source capability. Before R2 provider execution, the substrate was prospectively simplified to one hidden local-policy family: two undisclosed controlling coordinates among four integer features, each thresholded at 4, with an undisclosed one-to-one relabeling of the resulting two-bit state to four opaque actions.

The revision used eight fresh Field pairs, 40 source-local development cases, 40 destination-local development cases, 32 held-out development-calibration cases, five labeled development batches for source/reproduced, equal-call unlabeled practice for description-only, and no development for fresh. The four source-development readiness gates were frozen prospectively as **conventional workflow gates**, not SESOIs or inferential thresholds.

## Integrity and accounting

All registered structural gates passed:

- 8/8 Field pairs completed;
- source/destination development-feature overlap = 0;
- development/evaluation overlap = 0;
- all Capability Artifact export audits passed;
- reproduced and description-only logical-call counts were equal;
- every developed arm had exactly 9 logical calls per pair;
- every fresh arm had exactly 4 logical calls per pair;
- no evaluation feedback was returned;
- no confirmatory cohort or holdout was created or used;
- production/default Historical Substrate remained OFF.

Call accounting: **266 logical calls / 289 physical attempts**.

## Source-development readiness result

The prospectively fixed conventional gates all passed:

| readiness gate | observed | required | result |
|---|---:|---:|---|
| mean source held-out score | **58.594%** | >= 50% | PASS |
| mean source minus fresh | **+31.250pp** | >= +15pp | PASS |
| source > fresh | **7/8 pairs** | >= 6/8 | PASS |
| mean source final minus mean first development batch | **+41.406pp** | >= +10pp | PASS |

Mean source development-batch scores were approximately:

```text
17.188% -> 31.250% -> 48.438% -> 57.812% -> 50.000% -> 58.594% held-out
```

The trajectory is not monotonic in the fifth batch, but the prospectively registered final-vs-first and cross-arm readiness gates all pass. R2 therefore establishes only that this substrate is sufficiently learnable for the next **confirmatory-design freeze** step.

## Descriptive arm scores

| arm | mean held-out development-calibration score | SD |
|---|---:|---:|
| `fresh` | 27.344% | 10.398pp |
| `description_only` | 26.172% | 5.266pp |
| `source_developed` | 58.594% | 19.605pp |
| `reproduced` | 63.672% | 29.502pp |

Descriptive paired contrasts only:

- source - fresh: **+31.250pp**, paired SD 26.199pp;
- reproduced - description-only: **+37.500pp**, paired SD 28.787pp;
- reproduced - source: **+5.078pp**, paired SD 31.691pp.

These reproduction contrasts are calibration quantities only. They were not used to decide the R2 source-learnability handoff, and no p-value, confidence-based causal claim, superiority claim, fidelity/non-inferiority claim, or registry promotion is authorized from them.

Pair-level heterogeneity remains substantial: reproduced minus source ranges from -53.125pp to +46.875pp. This variance must inform the prospectively powered D2 design rather than being hidden by the positive aggregate calibration mean.

## Sampling characterization

All sampling-characterization calls eventually satisfied the structured-output contract. The calibration panel observed valid-contract rate 100% at temperatures 0.4, 0.8, and 1.0. This does not by itself select a confirmatory temperature; the confirmatory design must prospectively freeze the sampling setting and justify it from the development-calibration record.

## Handoff decision

The exact registered R2 handoff is:

> **`eligible_for_confirmatory_design_freeze`**

This is not authorization to execute D2 proper. Before any confirmatory provider call, D2 still requires a separately frozen confirmatory cohort, estimands, paired analysis, power/minimum analyzable N, threshold classifications and provenance, P2 materiality/non-inferiority margin, test/CI family, multiplicity plan, missingness/stopping rules, evaluator, request plan, and candidate commit posted prospectively to issue #167.

Production/default Historical Substrate remains OFF.
