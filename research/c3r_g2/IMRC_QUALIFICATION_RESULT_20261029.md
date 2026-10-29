# Institutional Memory Resilience & Curation — offline qualification RESULT (2026-10-29)

Status: **ONE frozen deterministic attempt. Zero sends.** Owner GO
2026-10-29 (offline design only). Grid frozen BEFORE running; no
re-tuning after results. Report:
`evidence_g2_qualification_20261028/imrc-qualification-report.json`;
tests: `tests/test_institutional_resilience_qualification.py` (7/7).

## Verdict (pre-declared binary)

> **QUALIFICATION PASSED** — evaluator valid AND curation
> wins/harms/ties all occur without forced signs.
> **Proceed to owner review of the resilience map. No freeze. No
> sends. No protocol dispatch.**

## 1) Evaluator validity (separated, as mandated)

- Oracle swap: all members, all generations → **100% correct**.
- Corruption swap: all members → **0% correct**.
- The apparatus registers real performance changes.

## 2) The resilience map (27 combos × 5 seeds = 135 chains; Δ = CURATED − UNCURATED over stressed generations 2–5; classification margin τ=0.05)

| staleness | contradiction | 1× | 4× | 12× |
|---|---|---|---|---|
| 0 | 0% | tie | tie | tie |
| 0 | 10% | **−0.100 harms** | tie | tie |
| 0 | 25% | **−0.125 harms** | tie (−0.025) | tie (+0.025) |
| 15% | 0% | **+0.175 wins** | tie | tie |
| 15% | 10% | **+0.200 wins** | tie | tie |
| 15% | 25% | **+0.100 wins** | tie (+0.050) | tie (+0.025) |
| 35% | 0% | **+0.225 wins** | tie | tie |
| 35% | 10% | **+0.225 wins** | tie | tie |
| 35% | 25% | **+0.150 wins** | tie (+0.025) | tie (+0.050) |

**Class counts: 6 wins, 2 harms, 19 ties.** All three outcome
families exist; no arm is structurally guaranteed.

## 3) The scientific structure the map reveals (non-inferential)

1. **Curation's value concentrates at LOW saturation + ANY staleness**
   (+0.100 to +0.225). At 1× saturation the retrieval budget spans
   the whole pool — stale-regime records dominate retrieved evidence
   after a truth change; the C1 regime-retirement policy clears them
   and the channel recovers.
2. **Curation HARMs at staleness=0 + contradiction>0 + low saturation**
   (−0.100, −0.125). With no true regime change, noise-induced
   generation majorities trigger C1's false-positive retirement of
   CORRECT older records; the curated pool loses the right evidence
   and the channel degrades. **The curation policy is genuinely
   double-edged — exactly the finding that makes the live design
   worth running.**
3. **At saturation ≥ 4× the recency-first retrieval engine is itself
   an implicit curator** (the 6-record window fills with current-
   regime records); curation adds ≈ 0 above it. This is NOT a
   generator-forced result — it is the interaction of policy with
   retrieval structure, visible only because the grid spans the
   space. (It also cleanly respects the owner's H6/H7 caution:
   selectivity is not assumed — it is measured as near-zero where the
   budget already selects.)

## 4) What is NOT claimed

This is an idealized deterministic model (majority deciders, the
registered C1/C2 policy, the frozen grid). It qualifies the DESIGN —
it says nothing about the live model's behavior. No confirmatory
freeze, no live send, no promotion, no G2 reopening, no Pattern
Register change. The 386-send historical G2 ledger is untouched; the
reserved Probe sends are untouched.

## 5) Handed to the owner for review

The full per-generation curves for all 135 chains and all 27 combo
summaries are in the committed report. The owner reviews the
resilience map, the harm/win structure, and the between-combo
variance, and decides whether:
(a) to proceed to confirmatory power simulation under a declared
    investment cap (with the corrected joint-distribution semantics
    and sign-preservation tests);
(b) to refine the curation policy (e.g., noise-robust regime
    detection) before any confirmatory design;
(c) to close this direction.
