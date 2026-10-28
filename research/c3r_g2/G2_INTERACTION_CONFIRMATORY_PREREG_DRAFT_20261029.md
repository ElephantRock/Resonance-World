# G2 interaction — confirmatory preregistration DRAFT v1 (UNFROZEN, for owner review)

Status: **DRAFT FOR REVIEW ONLY.** Not frozen; not dispatched; zero
sends to date beyond the 386 already registered (probe 2 +
calibration 384). Prepared under the owner's GO of 2026-10-29
(preparation only). Power simulation:
`evidence_g2_qualification_20261028/joint-gate-power-simulation.json`
(deterministic, frozen seed).

## 1. Research question and estimands

> Can an organization choose a knowledge-representation level that
> improves fresh members' performance above bounded raw-evidence
> interpretation — after accounting for knowledge-formation and
> operating costs?

Estimands (organization-level, paired within environment, ITT):

- **G = Y(D_VAR) − Y(D_CTX)** — the value of task-granularity
  representation over context-granularity compilation.
- **Net value condition (SEPARATE): Y(D_VAR) − Y(C) ≥ SESOI_NV** — any
  claim that compiled knowledge beats raw-evidence use rests on THIS
  contrast, not on G. G > 0 with D_VAR still below C is a
  representation-precision finding, not organizational net value.
- Descriptive: Y(D_CTX) − Y(C) per stratum.

**SESOI decision fields (owner decides at freeze; NOT transferred
automatically):**
- SESOI_G: proposed +5pp CONVENTIONAL (both compared arms share the
  D-class cost structure, so the threshold's meaning differs from the
  D−C case; a +10pp scenario is simulated as sensitivity). The owner
  may substitute a decision-theoretic derivation.
- SESOI_NV (D_VAR − C): +5pp, the same estimand family as the original
  D−C contract.

Gate structure: fixed-order hierarchical gatekeeping at one-sided
α=.05 — (1) net value D_VAR−C, (2) G, (3) D_CTX−C descriptively
reported only if (1) passes. (Net value is the architectural claim;
G refines HOW.)

## 2. Joint-gate power simulation (owner-mandated; results)

Gate = positive AND one-sided-significant AND estimate ≥ SESOI.
Org-level paired G ~ N(true_G, SD); between-organization variance
only; repeated tasks never independent units; 4,000 replicates/cell.

Worst declared band SD (0.576), SESOI_G = +5pp:

| true G | N (exact joint gate, 80%) | sends (48/org) | owner's conservative claim-N† |
|---:|---:|---:|---:|
| +30pp | 24 | 1,152 | ~34 |
| +20pp | 52 | 2,496 | ~92 |
| +15pp | 96 | 4,608 | ~205 |
| +10pp | 208 | 9,984 | — (unattainable) |

† the stronger claim "prove the TRUE effect exceeds SESOI"
(N ≈ ((1.645+0.842)·SD/(Δ−SESOI))²) — the owner's table. **Both
interpretations are displayed; the freeze chooses which claim is being
made.** At SD=0.45 (mid-band): N = 16/36/60/128 for
+30/+20/+15/+10pp. SESOI_G = +10pp scenario: identical N for
true_G ≥ 15pp; unattainable at true_G = 10pp (pass ≤ ~50%).

**Sensitivity to C-class output failures (9% observed):** affects the
NET-VALUE condition only (both D arms share the D-class 100%
validity): shifts measured D_VAR−C down ≈ 7.7pp and requires ~+25pp
true net effect at N=60/SD=0.45 for 80% (vs +15pp without failures).
C failures are ITT (no retry) and are already inside these numbers.

**Declared lever (owner-approved, simulation-quantified before any
freeze):** increasing tasks-per-environment shrinks per-org G SD; the
simulation must quantify the reduction and the added cost per
environment — no assumption that it "should" reduce N.

## 3. Stratified draw design (independent organizations)

- Primary stratum (declared): the informative band
  β ∈ {0.15, 0.30} × γ ∈ {0.0, 0.2} (the analysis band of the passed
  check), α ~ uniform over {0.55…1.0} by frozen seed.
- Allocation: balanced across the 4 (β, γ) band cells; org count per
  cell set by the freeze-time N (total N split evenly); environments
  drawn by frozen seed (`g2-interaction-v1`), disjoint from all
  developmental fixtures.
- Variance: between-org SD estimated per band cell from the idealized
  model (cross-seed) + a live-yield reserve; the primary analysis
  pools band cells with stratified weights (SE per the corrected
  formula); class/stratum breakdowns are secondary.
- No task-level unit is ever counted as independent.

## 4. Comprehensive cost model (48 sends/org: 16 C + 16 D_CTX + 16 D_VAR)

- Provider sends = task-execution requests ONLY. Compilation is
  deterministic Python: D_CTX reads the corpus once (20 records),
  D_VAR aggregates per variant (40 record-reads equivalent) —
  reported as compute-side accounting, zero provider sends.
- Token/time at observed averages (C ≈ 1,070 completion tokens,
  ~26.5 s, 91.1% parseable; D-class ≈ 103 tokens, ~3.4 s, 100%):
  per organization ≈ 17.1K C-tokens + 3.3K D-tokens; ~5 min wall.
  At N=52: ≈ 1.06M completion tokens, ~43 provider-hours; at N=96:
  ≈ 1.96M, ~80 h. Financial exposure: the existing Coding-Plan
  subscription (no incremental per-token cash); a hard money cap, if
  declared, must be registered before dispatch or nothing is sent.
- **Economical option (offered, hypothesis and distribution
  UNCHANGED):** concentrate N in the two highest-signal band cells
  (β=0.30, γ∈{0,0.2}) → same N-driven sends but narrower claim scope
  (G in that sub-band only); or accept the owner's conservative
  claim-N with a smaller N as an explicitly EXPLORATORY run
  (no confirmatory labeling). Both choices are the owner's.

## 5. Design facts carried from the passed check (owner-required display)

- Seed-change decomposition of the 10/20 band cells: **8
  positive↔tie, 1 negative↔tie, 1 positive+negative+tie, 10
  stable-positive.** Classification non-determinism is proven;
  full sign-flips are NOT widespread in the band — the strength of
  the no-forced-sign claim is exactly this.
- **Precision-without-net-value region (8+ grid cells, e.g. α=0.85,
  β=0.3, γ=0.2: G=+0.40 while D_VAR−C=−0.15):** D_VAR can beat D_CTX
  decisively and still lose to C — the reason the net-value condition
  is separate and primary.
- V1/V2 semantic caveat (documented, no re-run): oracle-swap and
  corruption are GRADER-PATH sensitivity probes — they prove the
  harness registers real changes, not that the compiler derives
  correct knowledge. (Exploratory live support for compiler
  correctness exists: developmental D_CTX was 64/64 in the noisy
  class; it is exploratory and excluded from confirmation.)

## 6. Pre-declared termination (owner's rule, adopted verbatim)

If no design with adequate power at acceptable cost exists under
these controls: **close this live line; pivot to the institutional
continuity study of the raw-history channel (H1–H4-supported)** —
with no SESOI, mixture or hypothesis change to rescue funding.

## 7. Decision fields for the owner at freeze

1. SESOI_G (+5pp conventional / +10pp / decision-theoretic value).
2. Claim interpretation: exact joint gate vs the stronger
   exceeds-SESOI claim (§2 table, both shown).
3. N and allocation (band-wide vs economical sub-band; exploratory
   small-N option).
4. Tasks-per-environment lever: approve simulation of its variance
   effect before freezing N.
5. Hard money cap registration (or subscription-as-envelope).

No live dispatch occurs before all five are decided and the prereg is
frozen by the owner. G3, Pattern Register promotion, and reuse of
developmental data remain NO-GO.
