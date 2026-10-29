# BREA Design v2 — Sequential Likelihood-Ratio Curation (2026-10-29; UNFROZEN; architectural & statistical review only)

Status: **DESIGN DOCUMENT v2 for owner review.** The v1 design's
hypothesis is approved; this revision fixes the causal and
statistical gaps the owner identified. ZERO execution authorization:
no grid run, no power simulation, no live send, no freeze. C3R-G2
remains closed; IMRC grid frozen and not re-run; C1/C2 preserved.

## 1. Rename: SLRC (Sequential Likelihood-Ratio Curation)

The owner correctly notes that without transition probabilities and
hypothesis priors, the mechanism is not "Bayesian" in the full sense.
**Scientific name: Sequential Likelihood-Ratio Curation (SLRC).**

## 2. The executable LLR definition (owner table, item by item)

### 2.1 Direction
```
LLR_g = log2( P(data_g | CHANGED) / P(data_g | SAME) )
```
A record CONTRADICTING the incumbent reference plan contributes
positive evidence FOR a change; a record CONFIRMING it contributes
negative evidence (for a change).

### 2.2 New evidence only
Each admitted record is processed **exactly once** — at its admission
generation. Its contribution enters `gen_evidence[g]` and is never
recounted. The running LLR is:

```
cumulative_LLR[g] = sum(gen_evidence[i] for i in window[g])
```

### 2.3 Windowed memory (no unbounded accumulation)
The evidence window is a **sliding window of the last W = 3
generations** of generation-level evidence sums (not raw records).
This bounds the detector's memory and prevents ancient correct
evidence from drowning a late true change. The window size W = 3 is
a CONVENTIONAL DESIGN CHOICE, not a proven guarantee.

### 2.4 Two-consecutive-generation rule (refined)
A regime change is declared only when BOTH hold in the current
generation g:
1. `cumulative_LLR[g] > +2.0` bits (the threshold), AND
2. `gen_evidence[g]` provides NEW supporting evidence
   (`gen_evidence[g] > 0` — the current generation's fresh records
   contribute positively toward "changed").

Condition 2 prevents a stale high cumulative value alone from
triggering the next generation's declaration: without NEW evidence,
the accumulator cannot fire.

### 2.5 Per-record evidence contribution (declared)
For a record contradicting the incumbent plan:
`contribution = +log2(0.85/0.15) ≈ +2.50 bits`
For a record confirming the incumbent plan:
`contribution = -log2(0.85/0.15) ≈ -2.50 bits`

(The 0.85/0.15 ratio is a CONVENTIONAL design choice. A single
contradicting record DOES exceed the +2.0 threshold — this is
correct and deliberate: the mechanism's noise-robustness comes from
the two-consecutive-generation rule + the new-evidence requirement,
NOT from making a single record's contribution sub-threshold.)

### 2.6 After declaration (no evaluator truth access)
When a regime change is declared at generation g:
1. **Infer the new reference plan** from the current window's
   records: majority plan among successes in the last W = 3
   generations (excluding retired records).
2. **Permanently retire** all records that (a) were admitted BEFORE
   the declaration generation and (b) whose success-plan differs
   from the newly inferred reference plan. Retirement = removal
   from the ELIGIBLE pool ONLY; the immutable audit store is never
   modified.
3. **Reset the detector**: `cumulative_LLR` = 0, window cleared.
4. **Begin accumulating evidence for the NEW reference plan**
   (the incumbent is now the newly inferred plan).

### 2.7 Non-modifiable audit trail
All admitted records live in an append-only `store` (never deleted).
The `eligible` pool is the only mutable view. Every retirement event
is logged with: record ID, generation, reason (regime_change /
supersession), and the detector state at the time.

## 3. The three-linked-contrast structure (owner-mandated)

| contrast | condition | question |
|---|---|---|
| **C1_retain**: SLRC − RESET | truth STABLE + noise burst ≥2 gens | does accumulated memory have value above fresh start? |
| **C2_shed**: SLRC − UNCURATED | truth CHANGED early or late | does the policy avoid obsolete-evidence harm? |
| **C3_stability**: SLRC − UNCURATED | truth STABLE throughout | does the policy avoid harmful false alarms? |

**Compound success condition (pre-declared):** C1_retain > 0 (or ≥
declared non-inferiority margin), C2_shed > 0, and C3_stability ≥
−δ (non-inferiority margin δ = 0.05, pre-declared). All three must
hold in the SAME grid. The three are necessary and jointly
sufficient for the claim "selective institutional resilience."

**If only C1 holds** (SLRC = UNCURATED > RESET in noise, no
improvement at change): the value is **continuous history**, not the
SLRC mechanism. **If only C2 holds**: a shedding mechanism, not
retention value. Both are valid scientific findings, but neither
alone supports the compound claim.

## 4. The new frozen grid specification (numbers fixed BEFORE any run)

| condition | truth schedule | noise schedule | purpose |
|---|---|---|---|
| stable_clean | no change (5 gens) | 0% | baseline |
| stable_burst1 | no change | 25% in gen 3 only | single-burst retention |
| stable_burst2+ | no change | 25% in gens 3–4 | false-alarm boundary |
| stable_chronic | no change | 10% every gen | chronic noise |
| change_early | change at gen 2, sustained | 0% after | early detection speed |
| change_late | change at gen 4, sustained | 0% after | accumulated-evidence drag |
| change_revert | change at gen 2, revert at gen 4 | 0% | permanent-retirement cost |
| saturation_control | no change | 0% | current-gen fills budget |

**8 conditions × 5 seeds = 40 deterministic chains** (new seed
domain `slrc-v1`, disjoint from all prior). 5 generations, 2
contexts, 8 tasks/gen, 2 members/gen, 6-record retrieval budget.
Retrieval engine and admission opportunities IDENTICAL across all
arms. Grid values are apparatus-qualification parameters, not
confirmatory thresholds.

**Registered metrics (beyond mean accuracy):**
- **detection latency**: generations from truth change to SLRC
  declaration (or "not detected" = 5);
- **recovery latency**: generations from declaration to
  SLRC performance ≥ 90% of its pre-change level;
- **false-alarm count**: declarations in truth-stable conditions;
- **retirement count + audit trail size** (cost).

## 5. Honest conditions where RESET or UNCURATED can win

- **RESET wins** in `change_early` + `change_late` if SLRC's
  detection latency ≥ 2 generations: fresh members outperform an org
  carrying undetected obsolete history.
- **UNCURATED wins** in `stable_chronic` if SLRC fires false alarms
  and retires correct history: append-only is safer when nothing
  truly changes.
- **RESET wins** in `saturation_control` (current-gen evidence fills
  the budget; history adds nothing).

The no-forced-sign check must CONFIRM that these wins are reachable
in the idealized model — not just that SLRC wins somewhere.

## 6. Cost definition (owner item #4)

| cost component | metric | reporting |
|---|---|---|
| processing | records processed per generation | count |
| detector updates | LLR updates + window operations | count |
| storage | total records in audit store + eligible pool | count |
| retrievals | 6-record retrievals per generation per member | count (identical across arms) |
| detection latency | generations from change to declaration | count |
| recovery latency | generations to ≥90% pre-change performance | count |

All components are deterministic compute (zero provider sends).
Total cost is reported per chain and per arm.

## 7. Static validity tests (owner item #5; before any grid execution)

1. **Sign preservation:** every transformed difference stays on
   [−1, +1]; no clipping to probability ranges (ERRATUM discipline).
2. **No evaluator truth leakage:** SLRC, UNCURATED, RESET and
   FROZEN access only admitted graded records; the oracle is used
   ONLY for grading, never inside any policy.
3. **Single-counting:** each record contributes to the detector
   exactly once (verified by a per-record contribution counter).
4. **No silent confirmation:** absence of new evidence in a
   generation does NOT count as supporting evidence for another
   generation's declaration (the `gen_evidence[g] > 0` guard).
5. **Determinism:** byte-identical re-run of the same chain.
6. **Compound-contrast coherence:** C1, C2, C3 computed on the SAME
   chain data; no cherry-picking across runs.

## 8. Four-outcome classification (owner's table, adopted verbatim)

| outcome | scientific classification |
|---|---|
| retain + shed + stability all pass | candidate for selective institutional resilience |
| SLRC > RESET but SLRC = UNCURATED | value of continuous history, not of the SLRC mechanism |
| SLRC > UNCURATED at change but not > RESET at noise | shedding mechanism, no proven retention value |
| detection failure / false alarms / unjustified cost | mechanism-specific negative result |

Each outcome is a valid scientific finding; none is a failure of the
investigation.

## 9. Early-closure conditions (pre-declared)

1. Static validity tests fail → CLOSE before any grid run.
2. No-forced-sign check fails (RESET or UNCURATED cannot win
   anywhere) → CLOSE with zero sends.
3. SLRC's compound gate fails but the four-outcome table is
   informative → REPORT the outcome and hand the decision to the
   owner (this is a scientific result, not a rescue).

## 10. Next gates

1. Owner reviews this v2 design (equations, grid, contrasts, costs,
   closure rules).
2. On approval: ONE deterministic qualification attempt on the new
   40-chain grid (no re-tuning).
3. On pass: corrected joint-gate power simulation under a declared cap.
4. On pass: frozen prereg for owner review.
5. Only then: dispatch authorization (separately gated).
