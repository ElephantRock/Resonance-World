# SLRC Design v2.1 — executable specification (2026-10-29; UNFROZEN; design only; zero execution)

Status: **v2.1 — all owner-identified gaps closed.** This document
supersedes v2 for review purposes; v2 and all prior documents remain
immutable. ZERO execution: no grid run, no power simulation, no live
send, no freeze. C3R-G2 remains closed (386 sends); IMRC grid frozen;
C1/C2 preserved; Pattern Register and G3 untouched.

## 1. Consecutive-evidence counter (the decisive fix)

The v2 rule (`cumulative_LLR > 2.0 AND gen_evidence[g] > 0`) allows a
single generation's evidence to trigger a declaration when the window
sum is already above threshold from earlier evidence. The v2.1 rule:

```python
# consecutive-generation positive-evidence counter
r_g = r_{g-1} + 1  if gen_evidence[g] > 0
r_g = 0            if gen_evidence[g] <= 0

# windowed cumulative LLR (W = 3 generations)
L_g = sum(gen_evidence[i] for i in the last 3 generations)

# declaration (both required)
Declare_g  <=>  L_g > +2.0  AND  r_g >= 2
```

**After declaration:** r is reset to 0, the window is cleared, and
the reference plan is re-inferred (§4). **Single-generation
positive evidence can never cause retirement regardless of LLR
magnitude.** (Static test: `e_{g-1}=0, e_g=+2.50` → no declaration.)

## 2. Causal compound gate (corrected: superiority vs non-inferiority separated)

| contrast | condition | requirement | test type |
|---|---|---|---|
| **C1_retain** | truth stable + noise burst ≥2 gens | **SLRC > RESET** (strict superiority) | one-sided |
| **C2_shed** | truth changed (early or late) | **SLRC > UNCURATED** (strict superiority) | one-sided |
| **C3_stability** | truth stable throughout | **SLRC ≥ UNCURATED − δ**, δ = 0.05 (non-inferiority, conventional) | CI-based |

**C1 uses superiority, not non-inferiority** (the owner's correction:
proving memory value above fresh start requires exceeding it).
C3 uses non-inferiority at the pre-declared margin. In the
deterministic qualification these are DESCRIPTIVE measures only; the
confirmatory version will use joint-gate simulation with appropriate
confidence bounds (not just a point estimate above −δ).

**Design unit correction:** C1, C2, C3 are NOT computed from "the
same chain" literally — they use **one design, independent paired
chains per condition, with the declared contrasts aggregated ACROSS
conditions** (C1 from stable+noise chains, C2 from change chains, C3
from stable-clean chains).

## 3. Grid v2.1 (9 conditions × 5 seeds = 45 chains; new seed domain `slrc-v2`)

| # | condition | truth schedule | noise schedule | purpose |
|---|---|---|---|---|
| 1 | stable_clean | no change | 0% | baseline |
| 2 | stable_burst1 | no change | 25% in gen 3 only | single-burst retention |
| 3 | stable_burst2+ | no change | 25% in gens 3–4 | false-alarm boundary |
| 4 | stable_chronic | no change | 10% every gen | chronic noise |
| 5 | change_early | change at gen 2, sustained | 0% after | early detection speed |
| 6 | change_late | change at gen 4, sustained | 0% after | accumulated-evidence drag |
| 7 | change_revert | change at gen 2, revert at gen 4 | 0% | permanent-retirement cost |
| 8 | **change_noise** | **change at gen 3, sustained** | **15% in gens 2–4 (pre, during, post)** | **the hardest boundary: detector must fire through noise** |
| 9 | saturation_control | no change | 0% | current-gen fills budget |

**Condition 8 is the owner-mandated concurrent condition** — a true
regime change WITH noisy evidence before, during, and after the
change. The detector must distinguish sustained directional change
evidence from noise contamination in the same window.

**Condition 9 expectation corrected:** the natural result is
**SLRC ≈ RESET ≈ UNCURATED** (a tie) — not a RESET win. The
qualification must not force a winner the structure doesn't allow.

**Fully specified environment parameters (frozen BEFORE execution):**
- Admissions: **4 records per context per generation** (all
  conditions; saturation_control raises to 14 to fill the budget).
- Initial state: empty store, no prior records; the first
  generation's admissions build the initial reference.
- Tie-breaking: majority-of-successes among the 6 retrieved records;
  if tied, the incumbent reference plan is kept (not neutral).
- Noisy-record generation: a noisy record carries the WRONG plan
  with graded_success=True (real observation, not evaluator forgery).
- All seeds, task operands, and member identities derived from the
  condition+seed hash (deterministic, disjoint from all prior).

## 4. Detector state-transition table (owner-mandated)

| state | event | action | new state |
|---|---|---|---|
| ACCUMULATE | `gen_evidence[g] > 0` | r++; update window | ACCUMULATE |
| ACCUMULATE | `gen_evidence[g] <= 0` | r = 0; update window | ACCUMULATE |
| ACCUMULATE | `L_g > 2.0 ∧ r_g >= 2` | infer new ref; retire; reset r, window | ACCUMULATE (new ref) |
| ACCUMULATE | no new evidence | r unchanged; window unchanged | ACCUMULATE |
| **Post-declaration** | inferred ref == incumbent ref | **NO retirement**; log as "no-op declaration"; reset r, window | ACCUMULATE (same ref) |
| **Post-declaration** | window majority TIED | **NO inference, NO retirement**; log "ambiguous declaration"; reset r, window | ACCUMULATE (same ref) |
| **Reversion** | old regime returns | retired records NOT restored; the cost is MEASURED (recovery latency from new admissions only) | ACCUMULATE |

## 5. Recovery-latency and no-evidence rules

- **Recovery latency** = generations from correct declaration to
  SLRC achieving ≥ 90% of its own pre-change performance (measured on
  the SLRC arm's per-generation curve). Reported per chain. This is
  an **independent performance cost**, not collapsed into mean
  accuracy.
- **No new evidence in a generation:** neither r nor the window
  changes; no declaration can occur (absence of evidence is not
  confirmation).

## 6. Cost model v2.1 (audit-store cost separated from processing cost)

| component | metric | SLRC | UNCURATED | RESET |
|---|---|---|---|---|
| evidence processing | records scanned per generation | 8 (4×2 contexts) | 8 | 8 |
| detector updates | LLR + window + r operations | O(1) per record | 0 | 0 |
| eligible-pool storage | records in eligible pool | ≤ total (retired removed) | = total | current gen only |
| **audit-store storage** | records in immutable store | = total (never deleted) | = total | = total |
| retrievals | 6-record retrievals per gen per member | identical across arms | identical | identical |
| detection latency | gens from change to declaration | measured | n/a | n/a |
| recovery latency | gens to ≥90% pre-change | measured | n/a | n/a |

Audit-store cost is reported SEPARATELY from processing cost. The
economic trade-off curve (processing cost vs performance value at
assumed per-operation cost) is derivable from these components but is
NOT a net-value claim — it is a parameterized tool for the owner's
economic decision.

## 7. Static validity tests v2.1 (expanded; run BEFORE the grid)

1. Sign preservation on [−1, +1] (ERRATUM discipline).
2. No evaluator truth leakage (oracle used for grading only).
3. Single-counting: per-record contribution counter (each record's
   LLR contribution enters the window exactly once).
4. No silent confirmation: `e_g = 0` → r unchanged, window unchanged.
5. Determinism: byte-identical re-run.
6. Compound-contrast coherence: C1 from stable+noise chains only; C2
   from change chains only; C3 from stable-clean chains only — paired
   arms within each condition, aggregated across conditions.
7. **Consecutive-counter correctness:** `e_{g-1}=0, e_g=+2.50` → NO
   declaration (r = 1 < 2). `e_{g-1}=+2.50, e_g=+2.50` → declaration
   (r = 2, L = 5.0 > 2.0).
8. **No-op declaration:** when inferred ref == incumbent, no records
   are retired (the declaration is logged but has no side effect).
9. **Ambiguous declaration:** tied window majority → no inference, no
   retirement.
10. **Reversion irreversibility:** retired records never re-enter the
    eligible pool; the cost is measured through recovery latency.
11. **Saturation-control expectation:** the check must NOT require
    any arm to win in condition 9 (the natural result is a tie).

## 8. Conventional-choice declaration

The thresholds (+2.0 bits, W=3, 0.85/0.15 ratio, δ=0.05, 4
records/context/gen) are **declared conventional design choices**.
They are NOT tuned on any prior result, NOT guaranteed optimal, and
may fail. The qualification tests whether the DESIGN works at these
values — it does not prove the values are correct.

## 9. Next gates (unchanged from v2 §10)

1. Owner reviews this v2.1 specification.
2. On approval: ONE deterministic qualification attempt on the new
   45-chain grid (no re-tuning).
3. On pass: corrected joint-gate power simulation under a declared cap.
4. On pass: frozen prereg for owner review.
5. Only then: dispatch authorization (separately gated).
