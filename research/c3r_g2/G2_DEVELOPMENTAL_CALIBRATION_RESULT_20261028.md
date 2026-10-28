# G2 developmental variance calibration — RESULT (2026-10-28 night)

**Run:** `40740553836` — 14/14 jobs succeeded. **384/384 sends**
consumed exactly (permanent O_EXCL ledger); reserved Probe sends
untouched. NON-INFERENTIAL by design: variance, validity and cost only.
No mechanism promotion; confirmatory N remains unfrozen; the full
campaign remains NO-GO.

## 1) Organization-level paired differences (D − C, per org, 16 cells each)

| class | orgs | per-org diffs | mean | SD |
|---|---|---|---:|---:|
| unambiguous | 0–3 | 0.00 × 4 | **0.000** | 0.000 |
| noisy_majority | 4–7 | +0.50, +0.44, +0.31, +0.31 | **+0.391** | 0.094 |
| task_conditional | 8–11 | −0.31, −0.50, −0.31, −0.44 | **−0.391** | 0.094 |
| **pooled (equal mixture)** | 12 | — | **0.000** | **0.340** (χ² upper bound 0.528) |

The mirror symmetry is the finding: **compile-once knowledge wins
+39pp where evidence is noisy but globally consistent; bounded
interpretation wins −39pp where truth is task-conditional and the
compiled granularity is too coarse; and the two cancel exactly under
the frozen equal mixture.** The offline fixture predicted BOTH signs
(S2-like +0.375, S3-like −0.46..−0.50); the live model reproduced the
directional structure at similar magnitudes — a strong harness-validity
signal (fixture ↔ live correspondence).

## 2) What this means for the frozen estimands

- **The pooled-over-mixture primary is structurally dead as designed.**
  Its true mean is ~0 BY CONSTRUCTION of the equal mixture, and its
  SD (0.34; upper 0.53) implies N ≈ 287–690 organizations for the
  joint gate at SESOI +5pp — impractical at 32 sends/org
  (~9,200–22,000 sends). Per the owner's rule this is NOT rescued by
  lowering SESOI or changing the mixture: the pooled estimand's
  viability is referred back for re-evaluation.
- **The pre-declared stratified view is where the signal lives.**
  Within-class SDs are small (0.094). A class-conditional question is
  powered at modest N (illustrative, joint-gate simulation at freeze):
  at SD = 0.094, detecting +5pp needs ~22 orgs/class; the observed
  within-class effects (±39pp) are far above SESOI. Stratification was
  frozen IN ADVANCE (protocol §"Declared analysis" + prereg §4.3) —
  this is the declared sensitivity analysis, not a post-hoc rescue.

## 3) Validity and cost (registered accounting)

| measure | C (interpretation) | D (execution) |
|---|---:|---:|
| parseable responses | 175/192 (**91.1%**; 17 ITT failures) | 192/192 (100%) |
| completion tokens | 205,377 | 19,697 (**10.4× cheaper**) |
| total latency | 5,085 s | 657 s (**7.7× faster**) |
| abstention-flag cells | — | 0 (all 12 orgs compiled) |

The C-class failure rate (~9%) must enter confirmatory yield planning
(already ITT-counted in these numbers).

## 4) Inputs handed to the owner's freeze decision (no decision taken here)

1. **Class-conditional confirmatory** (e.g., noisy-majority-stratified
   primary: "does compiled knowledge beat bounded interpretation where
   evidence is noisy but consistent?") — powered at ~22+ orgs/class;
   OR
2. **Interaction estimand** (mechanism × environment class: is the
   sign reversal real and large?) — treats class as the moderator
   rather than averaging over it; OR
3. **Re-evaluate the pooled investment** per the no-rescue rule.

Developmental organizations, corpora and records are seed-locked and
completely excluded from any confirmatory draw. No SESOI, mixture or
threshold change occurred; no rescue was attempted.

## 5) Evidence

`research/c3r_g2/evidence_g2_qualification_20261028/`:
`devcal-manifest.json` (frozen fixtures), `devcal-org-00..11.json`
(per-send rows: classification, latency, tokens, abstention flags),
`devcal-report.json` (this aggregation). Run `40740553836` (90-day
retention). Reserved Probe sends: untouched. Total live sends in the
G2 line to date: 2 (request-class probe) + 384 (this stage) = 386.
