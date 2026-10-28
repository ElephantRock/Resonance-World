# G2 no-forced-sign check — RESULT (2026-10-29; one frozen deterministic attempt; zero sends)

Status: **offline check executed ONCE under the frozen spec** (no grid
iteration). Report: `evidence_g2_qualification_20261028/no-forced-sign-report.json`;
tests: `tests/test_g2_no_forced_sign_check.py` (7/7). No model calls;
no live sends; developmental organizations untouched.

## Verdict (owner's pre-registered gate)

| gate question | result |
|---|---|
| apparatus causally valid? (MUST be positive) | **YES** |
| generator outcome-determinative? (MUST be non-definitive) | **NO — non-definitive** |
| overall | **CHECK PASSED → proceed to confirmatory prereg PREPARATION for review. No launch.** |

## 1) Apparatus causal validity (separated from generator expectations)

- **V1 — oracle-granularity swap:** replacing D_VAR's compiled
  procedures with the TRUE per-variant plans lifts D_VAR to exactly
  **100%** at both γ=0 and γ=0.4. The harness registers real
  granularity-driven performance change perfectly.
- **V2 — corruption swap:** flipping the D_CTX procedure collapses it
  to exactly **0%**. The harness responds to mechanism manipulation.

These probes measure the APPARATUS, not the environment: they hold
regardless of what the generator would predict.

## 2) The generator does not pre-determine the outcome

- In the **pre-declared analysis band** (β ∈ {0.15, 0.30} ×
  γ ∈ {0.0, 0.2}): **10 of 20 cells have seed-dependent G signs** —
  with identical rules and parameters, different evidence draws flip
  the winner. What decides there is the SAMPLED EVIDENCE, which is
  precisely what a live experiment would measure.
- Across the full 60-cell grid, every outcome family exists:
  G > 0 in 41 cells; G ≤ 0 (ties AND negatives) in 19 cells;
  D_CTX > C in 10 cells; D_CTX < C elsewhere. No arm is structurally
  guaranteed.

## 3) The owner's corrections were hypotheses — now MEASURED

- **β = 0 does NOT guarantee G = 0:** measured G at β=0,
  γ=0: **−0.40 at α=0.55**, −0.20 at α=0.65/0.75, → 0.0 only at
  α ≥ 0.85. Granularity-splitting genuinely HARMS at low consistency
  (per-variant support splitting + noise overfit) — the harm path the
  owner anticipated is real in the apparatus, not asserted.
- **γ = 0.4 ≠ information absence:** visible tags (~60%) still drive
  positive G cells at γ=0.4 in the band; masking degrades — not
  nullifies — variant exploitation.

## 4) Honest variance and cost inputs for the freeze decision

- Cross-seed SD of G within band cells reaches **0.576** (upper). A
  conservative org-level power calc for the live G estimand in the
  declared band (joint-gate rule, true effect above threshold):
  ~51 environments at true G=+20pp; ~91 at +15pp (≈ 2,400–4,400
  sends at 3 arms × 8 tasks × 2 members per environment, split
  1/3 C-class, 2/3 D-class). **This is large; whether it is fundable
  is an owner investment decision, not a design rescue.** A declared
  design lever at freeze time (NOT a post-hoc rescue): more tasks per
  environment shrinks per-environment G variance before N is fixed.
- Accounting corrected per owner: any live design splits sends
  1/3 C-class : 2/3 D-class (e.g., 960 sends = 320 C + 640 D; ≈ 328K
  C completion tokens vs ≈ 60K D at probe averages).

## 5) Constraints honored

Single frozen attempt (no grid iteration until success); all
parameters/seeds/classification rules/equivalence controls declared in
the script header BEFORE execution; zero live sends; the 12
developmental organizations were not used as confirmatory evidence; no
Pattern Register promotion; no G3; reserved Probe sends untouched.

**Handed to the owner:** the check passed its gate — the next step per
the owner's table is preparing a final confirmatory prereg FOR REVIEW
(power simulation of the joint gate on G in the declared band,
corrected send/token accounting, frozen grid-sampling method and
replication), explicitly without auto-launch.
