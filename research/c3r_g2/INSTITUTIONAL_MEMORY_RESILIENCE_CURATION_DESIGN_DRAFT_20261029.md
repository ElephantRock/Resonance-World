# Institutional Memory Resilience & Curation — scientific design draft (UNFROZEN; offline design only)

Status: **DESIGN DRAFT for owner review.** Pivot approved
(2026-10-29) as **OFFLINE DESIGN ONLY**. Zero new live sends; G2
remains closed; Pattern Register and G3 unchanged. Supersedes
`G2_PIVOT_RAW_HISTORY_CONTINUITY_DECISION_DRAFT_20261029.md` (whose
headline undervalued what H2–H4 already established).

## 1. What is already established — and therefore NOT the new question

| experiment | established (within its registered scope) |
|---|---|
| H1 | structured history beats informationally-equivalent flat log for a fixed controller (deterministic) |
| H2 | the structured-history channel survives COMPLETE member replacement (deterministic) |
| H3 | value ACCUMULATES across five generations of complete replacement (deterministic) |
| H4 | fresh stochastic successors with a LIVE model use accumulated structured history better than flat/no history (35/36 vs 19/36, Holm-corrected) |

**Continuity-through-replacement is therefore measured, not
hypothesized.** Re-running CONTINUITY vs RESET as a headline would
reproduce H3/H4. RESET and FROZEN-SNAPSHOT enter the new design as
CONTROLS ONLY (separating history effect from renewal and
accumulation), not as the primary claim.

## 2. The genuinely new claim

> An institution's memory channel is useful in H1–H4 conditions
> (fresh, consistent, small evidence). The untested question is
> **resilience**: does accumulated structured history RETAIN its
> value when evidence quality degrades — and can registered
> CURATION rules prevent capability decay at acceptable cost?

**Primary candidate contrast (owner-defined):**

Δ_Curation = Y(Curated Continuity) − Y(Uncurated Continuity)

Both continuity arms share the SAME evidence source, the SAME
admission opportunities, the SAME model and retrieval budget; they
differ ONLY in registered curation/retrieval rules. Curation cost
(record-keeping, admission computation, retrieval ranking) is
measured and accounted.

## 3. The three stressors (the scientific core)

1. **Staleness / obsolescence:** the environment drifts across
   generations (task distribution and/or the underlying truth law
   shifts by a registered schedule). Accumulated evidence from old
   regimes becomes misleading unless the channel adapts.
2. **Contradiction:** a registered fraction of admitted records is
   wrong, adversarial, or mutually conflicting (bounded, seeded).
   H5's documented hallucinated-evidence-identifier problem is the
   live-model precedent for why this stressor is realistic.
3. **Retrieval saturation:** the history grows across generations
   while the per-decision retrieval budget stays FIXED (the H-series
   used a 6-record budget). Uncurated growth dilutes retrieval;
   curation must earn its keep by keeping the useful records
   reachable.

Each stressor has a registered intensity schedule; the design
measures capability decay curves per arm, not a single endpoint.

## 4. Arm skeleton (v2 — causal-fairness correction, owner-mandated 2026-10-29)

**Fairness rule (binding before any check): CURATED and UNCURATED
share the SAME structured store schema, the SAME base retrieval
engine (registered: 6 most-recent eligible records of the task's
context), the SAME retrieval budget (6 records) and the SAME evidence
admission opportunities. The ONLY primary difference is the
registered CURATION POLICY — which records are superseded or retired
from the ELIGIBLE pool (stale-regime retirement and contradiction
supersession), with its processing cost accounted.** If a wider
bundle (curation + ranking changes) is ever tested, its effect is
named a BUNDLE effect and never attributed to curation alone. (This
also respects H6/H7: retrieval selectivity is NOT assumed helpful —
it is held identical across arms.)

| arm | eligible pool | role |
|---|---|---|
| CURATED | append-only store + registered curation policy (below) | treatment |
| UNCURATED | append-only store, no curation | primary comparator |
| RESET | current generation's records only (no cross-generation carry) | control anchor (H3/H4) |
| FROZEN-SNAPSHOT | store frozen after generation 1 | control (retention w/o accumulation) |

**Registered curation policy (ONE family; deterministic; cost = retired
records + policy passes, reported):**
- **C1 regime retirement (staleness):** per context, when a
  generation's admitted majority plan differs from the cumulative
  majority of all older records, a regime change is declared and all
  older-regime records for that context are retired from the eligible
  pool.
- **C2 supersession (contradiction):** within the current regime, per
  context, when the success-count ratio between the top two plans is
  ≥ 3:1, records of the dominated plan are retired.

Contradiction arises ONLY from real noisy or stale observations
(wrong-plan successes; obsolete-regime records) — the independent
evaluator never emits forged records; adversarial-input testing is a
separate TRUST study, out of scope.

## 5. Frozen qualification grid (owner-fixed, 2026-10-29)

| stressor | low | mid | high |
|---|---|---|---|
| truth staleness (change prob per context per generation transition) | 0 | 0.15 | 0.35 |
| evidence contradiction (wrong-plan-success fraction of admissions) | 0% | 10% | 25% |
| history saturation (eligible records ÷ 6-record budget) | 1× | 4× | 12× |

27 combinations × 5 independent seeds = **135 deterministic
organization chains**; 5 operational generations each; complete member
replacement between generations; fixed 6-record retrieval budget.
Seeds from a NEW domain disjoint from all H and G2 fixtures. Values
qualify the APPARATUS — they are not confirmatory thresholds. Results
reported generation-by-generation. The grid is frozen; no re-tuning
after seeing results (one attempt, no-rescue).

**Pass conditions (no-forced-sign + evaluator validity):** the
deterministic check must exhibit curation WINNING, HARMING, and TYING
across the grid without the truth generator forcing any; evaluator
validity via oracle/corruption swaps must hold. Failure closes the
design with zero sends.

## 6. Early-closure conditions (pre-declared)

1. No-forced-sign fails (some arm's win is structural) → CLOSE, zero
   sends.
2. Joint hierarchical-gate power simulation (corrected semantics:
   differences on [−1,+1], measured joint distributions, C-failure
   sign per the corrected model) infeasible under the owner-declared
   cap → refer investment back; no rescue by narrowing or threshold
   change.
3. Curation cost exceeds value at every stress level in the
   idealized model → the mechanism family is closed, recorded as a
   design-level negative.

## 7. Claims boundary (explicit)

Even a gated Δ_Curation > 0 supports only: "registered curation
rules preserve the accumulated-history channel's value under
registered degradation at accounted cost." It does NOT establish a
self-regenerating institution — regeneration (repairing rules,
preserving functions through condition change) is a separate, wider
claim requiring different manipulations.

## 8. Next gates (all before any live send; none automatic)

1. Owner reviews this draft and fixes the claim + stressor schedule.
2. Offline qualification harness + no-forced-sign + evaluator
   validity (this document's §5).
3. Corrected joint power simulation under a declared cap.
4. Frozen prereg for owner review.
5. Only then: request-class check if needed, dispatch authorization.
