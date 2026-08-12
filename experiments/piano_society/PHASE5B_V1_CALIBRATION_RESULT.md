# PIANO Phase 5B v1 calibration result

Status: **pre-inference calibration failed; no model calls; confirmatory fields untouched**.

This document records the terminal result of preregistration `piano-phase5b-transfer-search-v1`. The +3 percentage-point acceptance threshold is not changed after observing the result.

## Frozen source

- Source workflow run: `31649544130`
- Source workflow head: `55668e2f5aa74baa070d2c7fcfc2a2e77de26e8f`
- Frozen source artifact: `9162069554` (`piano-society-phase5b-frozen-source`)
- Artifact digest: `sha256:f91b0d23cf3a5b78c100ecacba0fc873bcfc3f5db18ee9a7ed17900d14c793b5`
- Capsule SHA-256: `3db71e9b498605853454abe64c0937f032e8d91bf0500c76fe20b17c9e436ebd`
- Candidate SHA-256: `ca6a9317358643fdf22464512447b800b4336470b3488b03764a9dd3cc862190`
- Calibration fields: `w4-source-seed-13007`, `w4-source-seed-13109`
- Confirmatory fields kept unopened by the search: seeds 13217, 13331, 13441, 13553, 13669, 13781.

The exact frozen source artifact must be reused by every Phase 5B revision. Source regeneration is prohibited because W5 roster construction depends on source agent UUIDs.

## v1 calibration lock

- Structural hypotheses: `role_specific`, `cross_coverage`
- Prior: 0.5 / 0.5
- Executable turnover policies: `specialist`, `balanced`
- Formation depth: 48 rounds per candidate
- Evaluation: 256 paired deterministic trials per policy
- Search space: 60 ordered skill-pair × regime candidates
- Selected contexts: 4 total, 2 per regime
- Acceptance gate:
  - 8 selected calibration units
  - mean transfer-policy lift over neutral-policy baseline >= **0.03**
  - >= 6/8 nonnegative selected units
- Model calls: 0

## Result

- `accepted`: **false**
- mean selected transfer-policy lift over neutral policy: **0.0283203125**
- nonnegative selected units: **8/8**
- posterior structural-direction matches: **7/8**

The best registered four-context set therefore missed the effect-size gate by `0.0016796875` (0.168 percentage points). The threshold is not relaxed.

The strongest observed pattern was that the structural posterior frequently corrected a roster-only neutral forecast, but finite formation evidence still left one structural misclassification and several units in which retained and neutral policies selected the same route, producing zero causal contrast.

## Pre-inference revision rule

A Phase 5B v2 may increase **formation evidence depth only**, because:

1. no Phase 5B model call has occurred;
2. no confirmatory organization was loaded by the v1 search;
3. the exact source artifact is already frozen;
4. the inference family, policy vocabulary, calibration fields, evaluation law, search algorithm, and +0.03 acceptance gate remain unchanged.

The registered v2 change is formation depth `48 -> 96`. v2 must run from artifact `9162069554` and may not regenerate source state.
