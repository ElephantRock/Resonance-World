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

## 4. Arm skeleton

| arm | history policy | role |
|---|---|---|
| CURATED | growing structured history + registered curation rules (admission support floors, supersession/provenance on contradiction, relevance-and-recency retrieval ranking under the fixed budget) | treatment |
| UNCURATED | growing structured history, same admission机会, no curation — append-only, budget-spent-on-most-recent or fixed-order retrieval (registered) | primary comparator |
| RESET | no carry-over between generations, same member quality/budgets | control (H3/H4 replication anchor) |
| FROZEN-SNAPSHOT | history frozen at generation 0 | control (retention without accumulation) |

Curation is ONE mechanism family in this design (admission +
supersession + ranking under a fixed budget); rule-repair and
self-modification are explicitly OUT (that is institutional
regeneration, a later, wider claim).

## 5. No-forced-sign preconditions (preparation only; must pass before any freeze)

A deterministic idealized model over (staleness rate, contradiction
fraction, history-size/retrieval-budget ratio) must show all three:
curation HELPS (high staleness/contradiction), curation HARMs
(over-pruning discards rare-but-crucial records at low stress), and
TIES (benign regimes). Sign-preservation unit tests on every
transformed quantity (ERRATUM discipline). Evaluator validity:
oracle/corruption swaps must move measured outcomes exactly.

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
