# D2-0 learnability revision 2 — prospective development-only calibration

Status: **prospective development-only revision; never confirmatory evidence**.

Parent development calibration: `research/d2/CALIBRATION_RESULT.md` / workflow `31890035170`.

The parent D2-0 calibration failed its source-development handoff because source performance remained near the four-action 25% uniform-action reference. This revision is therefore motivated only by **source learnability**. It is not selected to increase the previously observed reproduced-minus-description contrast, and that contrast remains scientifically uninterpretable until a learnable source capability exists.

No D2 confirmatory cohort, holdout, p-value, SESOI, non-inferiority margin, S-classification, or registry promotion is created or authorized here. Production/default Historical Substrate remains OFF.

## Revision intervention

The prior six-family parity/threshold ecology is replaced for this development calibration by one simpler registered family:

- each Field has four visible integer features `f0..f3`, values 0..7;
- exactly two undisclosed controlling coordinates are selected locally;
- each controlling coordinate yields bit 0 below 4 and bit 1 at or above 4;
- the two-bit state is mapped one-to-one to `KAPPA`, `MICA`, `ORBIT`, `VELA` by an undisclosed local permutation;
- the controlling coordinates and action relabeling remain environment-private and are not exported.

This preserves a genuine hidden local policy while sharply reducing compositional complexity. The developmental operation remains model-mediated hypothesis formation from local outcome-bearing feedback.

## Curriculum and budget

Eight fresh source/destination Field pairs are used. Pair seeds begin in a new `840000` series and are disjoint from the completed R1 calibration cohort.

Per pair:

- source-local development: 40 cases;
- destination-local development: 40 cases;
- source and destination development feature tuples: exact overlap 0;
- held-out development-calibration evaluation: 32 cases;
- development/evaluation feature overlap: exact 0;
- 5 development batches of 8 cases;
- each development set and evaluation set is balanced over the four hidden action states;
- source and reproduced receive local correctness + correct-action feedback after each development batch;
- description-only receives equal-call unlabeled practice and no outcome labels;
- fresh receives no development;
- evaluation is split into four deterministic 8-case chunks for every arm and returns no feedback.

The source development instruction is fixed: compare candidate controlling feature pairs across labeled examples, infer the four-state action relabeling, maintain a concise private hypothesis, prefer rules explaining all evidence, and avoid case-ID memorization.

## Capability Artifact boundary

Capability Artifact v0.2 remains the public reproduction carrier. It may describe the registered family, development curriculum, feedback contract, memory/update interface, provider contract, resource budget, stopping rule, evaluation contract, dependencies, and known failure conditions.

It must not contain source identity, source/private strategy or memory, source development examples, source/pair seeds, local controlling coordinates, local action permutation, hidden truth token, evaluation answers, or confirmatory material. The existing `d2_artifact_core` machine audit remains authoritative.

## Provider / transport freeze

Development provider candidate: Z.AI `glm-5-turbo`, temperature `0.8`, thinking disabled, JSON-object structured output.

Transport contract:

- `actions` mandatory, exact expected length, exact registered vocabulary;
- optional private `strategy`, max 6000 characters;
- harmless extra keys ignored;
- up to 8 transport/format attempts per logical call;
- no scientific outcome-adaptive retrying;
- request IDs, prompt/response hashes, attempts, token accounting, and latencies retained.

Sampling characterization repeats a fixed 8-case suite six times each at temperatures 0.4, 0.8, and 1.0. These are development-calibration diagnostics only.

Expected logical calls before retries:

- developed arm: 5 development + 4 evaluation = 9 calls;
- fresh arm: 4 evaluation calls;
- per pair: `9 + 9 + 9 + 4 = 31`;
- paired panel: `8 * 31 = 248`;
- sampling characterization: 18;
- total: **266 logical calls**.

## Conventional development-readiness gate

The following thresholds are explicitly classified as **conventional development-readiness workflow gates, not inferential SESOIs and not confirmatory evidence**. They are frozen before R2 provider execution solely to decide whether the stochastic substrate is sufficiently learnable to justify designing D2 proper:

1. mean source held-out calibration score >= 50%;
2. mean source minus fresh >= +15 percentage points;
3. source > fresh in at least 6 of 8 pairs;
4. mean source held-out score minus mean first-development-batch score >= +10 percentage points.

All four must pass for the handoff `eligible_for_confirmatory_design_freeze`. Failure of any gate returns D2-0 to development-substrate revision; it is not a D2-S0 confirmatory classification.

These conventional gates deliberately concern **source development only**. No reproduced-minus-description or reproduced-minus-source threshold is used to select this revision or decide substrate learnability.

## Integrity gates

R2 is valid development calibration only if all of the following hold:

- exactly 8 fresh Field pairs complete;
- source/destination development overlap = 0;
- development/evaluation overlap = 0;
- all Capability Artifact export audits pass;
- description-only and reproduced have equal logical-call counts;
- every developed arm has exactly 9 logical calls per pair;
- fresh has exactly 4 logical calls per pair;
- no evaluation feedback is returned;
- no confirmatory cohort/holdout is created or used;
- production/default Historical Substrate remains OFF.

A transport failure may be prospectively repaired only if it does not change the hidden-policy family, pair cohort, development/evaluation cases, feedback labels, development curriculum, Artifact semantics, readiness gates, or scientific comparisons. Such a failure is not a scientific result.

## Handoff rule

If the four conventional source-development readiness gates and all integrity gates pass, D2-0 R2 may hand off only to **prospective D2 confirmatory design freeze**. It does not itself authorize provider execution of D2 proper.

D2 proper still requires a separately frozen confirmatory cohort, power analysis, estimands, statistical tests/CIs, multiplicity plan, non-inferiority/materiality margin with provenance, evaluator, request plan, and candidate commit posted prospectively to issue #167 before any confirmatory provider call.
