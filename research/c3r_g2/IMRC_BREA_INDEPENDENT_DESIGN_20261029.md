# IMRC — BREA: Independent Prospective Curation Design (2026-10-29; UNFROZEN; offline design only)

Status: **DESIGN DOCUMENT for owner review — nothing runs.** The
frozen IMRC qualification grid is NOT re-run; C1/C2 and its results
are closed and preserved; no power simulation, no live send, no
freeze occurs from this document.

## 1. The new hypothesis (above H3/H4 and IMRC)

Three levels of evidence now exist:

| level | evidence status |
|---|---|
| structured history helps successors through turnover | confirmatory (H2–H4, incl. live model) |
| simple curation (C1/C2) recovers from harmful old evidence | deterministic, in tested IMRC cases (CURATED ≈ RESET in 129/135) |
| **a knowledge-maintenance policy that preserves institutional value ABOVE reset through both regime changes AND noise bursts** | **unmeasured — this design's target** |

> **Hypothesis (pre-declared):** a noise-robust regime-evidence
> accumulator can distinguish "old evidence became wrong" (true
> regime change) from "old evidence is still correct but temporarily
> contradicted by noisy recent evidence" (noise burst) — and by doing
> so, preserve accumulated knowledge value that EXCEEDS what fresh
> members reconstruct from current-generation evidence alone, at an
> accounted operating cost.

## 2. The mechanism: BREA (pre-declared; no post-hoc tuning)

**Bayesian Regime-Evidence Accumulator** — one deterministic policy,
fully specified before any qualification:

- **Per context, maintain a running log-likelihood ratio (LLR)
  between "same regime" and "regime changed" hypotheses over the
  stream of admitted graded records** (the record's plan and success
  under each hypothesis; pre-declared Bernoulli likelihoods:
  success-probability p_same = 0.85 under "same", p_changed = 0.15
  under "changed" for records contradicting the incumbent majority,
  and vice versa for confirming records).
- **Decision rule (pre-declared):** when the LLR crosses a
  pre-declared threshold (LLR > +2.0 bits for 2 consecutive
  generations), declare a regime change and retire the old-regime
  records permanently (one-way: BREA is a permanent-retirement
  policy — the eligibility-recomputation ambiguity is resolved by
  declaration). When LLR falls back below +1.0 bit, reset the
  accumulator and KEEP the incumbent records.
- **Noise-robustness by construction:** a single noisy generation
  cannot cross the 2-consecutive-generation + 2.0-bit threshold;
  only sustained directional evidence can. This is the mechanism
  that distinguishes C1's harm region (noise-triggered false
  retirement) from true regime detection.
- **No evaluator truth access:** BREA reads only admitted graded
  records — the same information available to every arm.

**Information boundary:** BREA, UNCURATED, RESET and FROZEN all see
the same store; the retrieval engine (6-record recency-first) is
identical across all arms; admission opportunities are identical.
The ONLY difference is BREA's retirement policy and its cost.

## 3. The discriminating test (owner requirement #4)

The primary NEW estimand separates "memory value above fresh start"
from "just shedding the past":

**Δ_Above_Reset = Y(BREA_CURATED) − Y(RESET)** — measured in the
**noise-burst condition** (contradiction present but truth stable):
an organization that correctly KEEPS its valid old knowledge should
outperform an organization limited to current-generation evidence.
Δ_Above_Reset > 0 is the first measurable claim of institutional
memory value beyond member replacement.

Secondary contrasts (same design, same session):
- Δ_Shed = Y(BREA) − Y(UNCURATED) in the regime-change condition
  (does BREA still shed genuinely obsolete evidence? — the IMRC
  result to preserve, not re-prove);
- Δ_Retain = Y(BREA) − Y(RESET) in the regime-change condition
  (should be ≈ 0: correct retirement ≈ correct fresh start);
- The **noise-burst x regime-change boundary**: a single frozen
  crossover design where bursts and changes co-occur at different
  intensities — BREA's SCIENCE is at the boundary, where no simple
  rule works.

RESET is the **primary interpretive control** (not a footnote): if
BREA only ever matches RESET, the policy is a cleaner shed mechanism,
not institutional memory.

## 4. Policy failure modes (pre-declared; any may close the design)

1. **Missed change (sticky incumbent):** LLR threshold too high →
   Breta retains obsolete evidence through true changes →
   Δ_Shed < 0 relative to C1's IMRC shedding result.
2. **False alarm under sustained noise:** ≥2 consecutive noisy
   generations cross the threshold → BREA falsely retires correct
   history → Δ_Above_Reset < 0.
3. **Accumulator drift:** LLR creeps upward under chronic low noise
   → delayed false alarms.
4. **Cost:** BREA's per-record per-generation LLR update is O(1)
   compute but O(generations × records) total; the cost is reported
   alongside retirement counts and compared with C1/C2's.

## 5. Early-closure conditions (pre-declared)

- Offline no-forced-sign check (NEW grid, disjoint seeds, declared
  before running): BREA must win (Δ_Above_Reset > 0 in noise-burst),
  harm (false alarm → Δ_Above_Reset < 0), and tie (benign regimes)
  across the new grid — otherwise CLOSE with zero sends.
- If BREA's Δ_Above_Reset is structurally forced positive by the
  generator (truth stable, noise high, RESET's current-gen window
  too noisy) → CLOSE: the apparatus answers the question by
  construction, not by measurement.
- If the corrected joint-gate power simulation (differences on
  [−1,+1], measured joint distributions, sign-preservation tests)
  shows the design infeasible under the owner's declared cap →
  refer back; no rescue.

## 6. What would be new knowledge (claims boundary)

A gated Δ_Above_Reset > 0 with Δ_Shed ≥ 0 and Δ_Retain ≈ 0 supports:
"a pre-declared noise-robust regime-evidence accumulator preserves
accumulated institutional knowledge value above member replacement
under registered stress, at accounted cost." It does NOT establish:
self-modification of curation rules, institutional regeneration,
cross-environment generalization, or any claim about the live model's
behavior (until measured live).

## 7. Next gates (all before any execution; none automatic)

1. Owner reviews this design (hypothesis, mechanism, boundaries,
   failure modes, closure criteria).
2. Offline no-forced-sign + evaluator-validity qualification on a
   NEW frozen grid (disjoint seeds; BREA fully specified in advance).
3. Corrected joint-gate power simulation under a declared cap.
4. Frozen prereg for owner review.
5. Only then: dispatch authorization (separately gated).
