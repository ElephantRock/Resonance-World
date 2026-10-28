# G2 calibration exploratory interaction analysis — REGISTERED EXPLORATORY (2026-10-29)

Status: **exploratory, non-inferential, registered on the developmental
calibration data (run 40740553836).** No confirmatory claim. Generated
by `scripts/analyze_g2_calibration_interaction.py`; canonical output:
`evidence_g2_qualification_20261028/devcal-exploratory-interaction.json`.

## 1) Class deltas, SDs and the interaction (exploratory)

| class | Δ = D−C | SD (4 orgs) |
|---|---:|---:|
| unambiguous | 0.000 | 0.000 |
| noisy_majority | +0.3906 | 0.0938 |
| task_conditional | −0.3906 | 0.0938 |

**θ = Δ_noisy − Δ_conditional = +0.7812 (+78.1pp)** — exploratory, and
NOT independently confirmable as designed: the current compiler is
contractually context-granular while C can read variant tags, so the
sign in the task-conditional class is pre-programmed by the
procedure's representational limits. An expensive confirmatory run
must not merely re-demonstrate this.

## 2) ITT decomposition (decision errors vs token exhaustion)

| class | C correct | D correct | C `length` failures | ITT Δ | Δ if all C-`length` were correct | decision-only Δ (C-parseable cells) |
|---|---:|---:|---:|---:|---:|---:|
| unambiguous | 64/64 | 64/64 | 0 | 0.00pp | 0.00pp | 0.00pp |
| noisy_majority | 39/64 | 64/64 | 13 | **+39.06pp** | **+18.75pp** | **+18.75pp** |
| task_conditional | 56/64 | 31/64 | 4 | **−39.06pp** | −45.31pp | **−39.06pp** |
| total | 159/192 | 159/192 | 17 | — | — | — |

All 17 C failures are `finish_reason=length` (token exhaustion), zero
transport errors. Reading:
- **Noisy-consistent class:** D's ITT advantage (+39pp) is roughly half
  decision quality (+18.75pp persists under the most C-favorable
  counterfactual) and half reliability/cost (13 exhausted C cells).
  The compiled win is REAL but not purely epistemic — it is accuracy +
  yield + cost in the registered regime, exactly as the treatment
  characterization states.
- **Task-conditional class:** D's loss is a pure DECISION error
  (−39.06pp decision-only): the context-granular procedure is wrong on
  special-variant tasks; validity is irrelevant (removing C's 4
  exhausted cells would WIDEN C's win to −45.3pp).
- **Unambiguous class:** perfect tie at ceiling with zero failures.

## 3) Statistical corrections (owner review, adopted)

1. **The pooled SD (0.34) does not describe stratified-design
   precision.** The stratified estimand is
   Δ̂ = Σ w_k Δ̂_k with w_k = 1/3 and
   SE(Δ̂) = sqrt(Σ w_k² s_k² / n_k). On these data:
   naive SE (12 orgs, strata ignored) = **9.82pp**; stratified SE
   (4 orgs/class) = **2.21pp**. The N = 287–690 figures are therefore
   **BANNED as a final sample-size justification**; they describe only
   the unstratified pooled design, which is now closed anyway.
2. **A structurally-zero pooled mean is not treated by adding N.** And
   the joint gate (positive + significant + estimate ≥ +5pp) can NOT
   be powered at 80% by assuming the true effect EQUALS +5pp —
   P(estimate ≥ threshold | true = threshold) ≈ 50%. Power calibration
   must assume a true effect ABOVE the decision threshold and simulate
   the full gate. Illustrative (stratified mean, s = 0.094): powering
   the gate at true +10/15/20pp needs ~1 org/class — but the pooled
   mean is not the confirmatory target anymore; the interaction design
   below re-derives its own N from its own parameter distributions.

## 4) Status handed to the design phase

The calibration supports (exploratorily) the architectural reading:
**organizational compilation trades representational detail for reuse,
reliability and cost.** When experience is consistent at the level the
procedure represents, the trade can pay; when decisions depend on
detail the compilation discards, it can harm. The independent protocol
draft (`G2_INTERACTION_PROTOCOL_DRAFT_20261028.md`) turns this into a
test whose sign is NOT pre-programmed. No live send is requested.
