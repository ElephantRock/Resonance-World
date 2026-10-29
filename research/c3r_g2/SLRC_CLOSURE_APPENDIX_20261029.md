# SLRC DESIGN CLOSED — closure appendix (2026-10-29; final; zero execution)

Status: **CLOSURE APPENDIX.** One document; no code run; no grid
execution; no policy improvement; no parameter change. All prior
records preserved unchanged. C3R-G2 remains closed at 386 live
sends; IMRC results frozen; H-series results untouched; reserved
Probe sends untouched; Pattern Register and G3 unchanged.

## 1. The closure reason (owner's proof, adopted verbatim)

At any admission rate a ≥ 2 records/context/gen with a 6-record
recency-first budget and the two-consecutive-generation detection
rule, the following is a **structural property of the apparatus**
under clean-evidence conditions:

- **Generation h = 1 after a truth change:** the window holds
  `a` new-correct + `(6 − a)` old-obsolete records. The consecutive
  counter is at r = 1 (first generation of new evidence) — **no
  declaration**. If a = 3 the window is 3+3 (tied) and tie-breaking
  favors the old incumbent reference → UNCURATED may err here.
- **Generation h = 2 after the change:** the window holds `2a` new
  records (≥ 6 at a ≥ 3) and 0–0 old. SLRC's detection fires (r = 2)
  — **but UNCURATED's majority is already correct**: the retrieval
  engine has flushed the obsolete evidence by itself.

Therefore in `change_early` / `change_late` (clean noise = 0%):

> **Δ_Shed = Y(SLRC) − Y(UNCURATED) = 0** regardless of detection
> correctness — the detector arrives after the problem has solved
> itself.

This holds at a = 4 (v2.1), at a = 3 (the v2.2 proposal), and at
a = 2 (where the majority is already correct by h = 2: 4 new + 2
old → 4 > 3). Only a ≤ 1 record/gen delays majority-correction past
the 2-generation detection window — and a = 1 is not a defensible
institutional-memory regime (it depletes the evidence stream itself).

**The correct boundary condition is temporal, not the ratio R alone:**

```
decision-level curation value exists only when:
    detection_time (≥ 2 generations by construction)
  < evidence-flush time (⌈K/2⌉ / a generations)
```

This requires ⌈3/a⌉ > 2, i.e., a < 1.5 — at which point the
apparatus no longer tests institutional memory curation but
near-empty evidence streams. The design space that supports the
primary compound contrast does not exist within the current
apparatus class.

## 2. What is adopted from the v2.2 review (independent documentation fixes)

The owner adopted these specification corrections (preserved for any
future design that operates in a different apparatus class):

1. **C3_stability scope:** all truth-stable conditions (clean +
   burst + chronic), not stable_clean alone.
2. **Silent vs zero-sum generations:** distinguished; window ages
   over active generations only.
3. **Reference initialization:** gen-1 majority with hash fallback;
   no evaluator truth access.
4. **Right-censored recovery:** reported separately as "censored".
5. **Noisy-record model:** declared as probabilistic-evaluator
   false positives on outputs (not evaluator forgery).

These are apparatus-engineering principles, not SLRC claims.

## 3. The scientific principle retained (hypothesis-level, not confirmed)

> **The value of memory curation depends on the timing of detection
> relative to the timing of evidence-flush by the retrieval engine.**

If the retrieval engine bypasses old evidence before the detector
can intervene, there is no observable decision-level value for that
intervention — no matter how accurate the detection is. This
principle emerged from three rounds of design review (v2 → v2.1 →
v2.2) without a single live send, and defines the correct future
question:

> *When does an institution benefit from retaining historical
> knowledge, and when is current-evidence retrieval alone sufficient?*

This is a genuine architectural insight, but it does not
automatically justify a new experiment.

## 4. Status of the closure

- **SLRC is CLOSED as a candidate for the current apparatus class**
  (structured-history + recency-first bounded retrieval +
  majority-of-retrieved deciders + two-generation detection).
- The closure is **NOT evidence that SLRC fails against a live
  model** — it is a failure to prove causal identifiability of the
  primary compound contrast within the proposed apparatus. No live
  model was involved.
- No parameter change (4→3 or otherwise) was executed. No grid was
  run. No threshold was tuned. No prior result was used to set any
  parameter.

## 5. Ledger

| item | value |
|---|---|
| live sends in the entire G2/IMRC/SLRC program | 386 (probe 2 + calibration 384) |
| new sends for this closure | 0 |
| grids executed | IMRC 135 (frozen); SLRC 0 |
| reserved Probe sends | untouched |
| Pattern Register / G3 | unchanged |
| historical records modified | none |
