# PIANO Phase 5C v1 feasibility result

Status: **pre-treatment feasibility failure; no model calls; no confirmatory outcomes evaluated**.

Phase 5C v1 preregistered a roster-conditional constructor with 12 confirmatory organizations balanced 6 `role_specific` / 6 `cross_coverage`. The exact fresh source population was frozen before construction.

## Frozen source

- Source workflow run: `31652358960`
- Source workflow head: `88baf131c78bf37fe49fab858890cce7f4740729`
- Source artifact: `9163101495` (`piano-society-phase5c-frozen-source`)
- Artifact digest: `sha256:2caf65e6f2839f243ad0c6e59f7d12ad196f48ddf79aab7c3cca42b0904f22f6`
- Capsule SHA-256: `b44926d70fe91ae3ad546351bd42096ad54a10d7d50eb954060e1bc56dcd1ea8`
- Candidate SHA-256: `a750b8b110a26a60e74a4561493c3359b29524cca2ebec1061bccff6cb3ad0b7`
- 24 fields / 288 agents.

The original source-generation workflow was retired after this artifact was frozen. All later Phase 5C work must consume these exact bytes.

## v1 failure classification

The source/export/hash/lint steps all passed. The constructor exited `1` before producing `result.json`. A frozen-source diagnostic rerun reproduced the same failure and uploaded diagnostic artifact `9163204863`, digest `sha256:2392f9b1d2e70101d62fff6aeec4784826385a5a7fa915a7ddbdc9c0f3071e29`.

The exact exception was:

`ValueError: Phase-5C roster geometry cannot satisfy the registered target-balanced field selection`

This is not a scientific outcome and not a model/provider failure. It is a pre-treatment feasibility failure of the 6/6 selection requirement.

## Model-free geometry audit

A separate audit read only frozen pre-treatment competence state. It performed no institutional-memory training, sampled no mission outcomes, and made no model calls.

- Audit workflow run: `31652891403`
- Audit head: `f01f85369013ff8a74e0c9600e5e7eefc7036a78`
- Audit artifact: `9163248092`
- Audit digest: `sha256:c30535d8d14e93e35605db5690a7abda08e42f0ffcff1a49354dfc1b4a42ed2c`

Findings on the 18-field confirmatory pool:

- fields with at least one eligible `role_specific` target: **5**
- fields with at least one eligible `cross_coverage` target: **13**
- fields with eligible targets of both kinds: **5**
- 12-unit target balances feasible under the original thresholds: `0/12`, `1/11`, `2/10`, `3/9`, `4/8`, and **`5/7`** (`role_specific/cross_coverage`)
- `6/6` is impossible.

The original calibration pool remains capable of a 2/2 target-balanced four-unit selection.

## v2 rule

Phase 5C v2 changes **only** the infeasible confirmatory composition from `6/6` to the most balanced feasible `5/7`. It preserves:

- the exact frozen source artifact;
- calibration/confirmatory pool split;
- one unit per field;
- all roster-geometry eligibility thresholds;
- structural hypothesis family;
- target rule (correct policy must oppose the neutral-prior preference);
- constructor scoring rule;
- formation depth 96;
- 512 calibration trials per policy;
- four calibration units balanced 2/2;
- the original calibration acceptance gate (+3 pp mean lift, 4/4 nonnegative, 4/4 forecast-preference changes, 4/4 target-posterior matches).

No Phase 5C model-backed confirmatory call may occur unless v2 passes that unchanged calibration gate.
