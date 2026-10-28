# G1 natural stepwise execution fidelity — RESULT (2026-10-28)

**Run:** GitHub Actions `40652718082` — all 20 jobs succeeded.
**Campaign:** 96/96 sends (Arm A: 2 sessions × 8 single-shot; Arm B: 16
sessions × 5 stepwise; cross-process O_EXCL slot ledger 0..95; over-budget
and double-dispatch fail visibly — tested).
**Design (frozen before first send):**
`G1_NATURAL_STEPWISE_EXECUTION_FIDELITY_PROSPECTIVE_20261027.md` — 16 tasks
(8 public programs × 2 waves), same correct NL procedure and same fresh
unambiguous inputs in both arms; the ONLY variable is execution
granularity. glm-5.3, coding endpoint, High/4096, temperature 0.
**Classification:** exploratory pilot; `scientific_acceptance=false`.

## 0) Apparatus correction (pre-dispatch, zero live sends affected)

Offline pre-dispatch testing caught a frozen-text defect: the rotate
step-5 B branch was rendered as "prepend '5'" while the frozen evaluator
prepends **'9'**. This campaign renders the branch as '9' (correct w.r.t.
the evaluator); the manifest pins the corrected step lines. The published
representation-comparison baseline (75% natural ITT, 20261027) inherited
the defect — its 8 rotate-B natural tasks were instruction-impossible.
The single-shot baseline re-measured here is therefore the cleaner
reference.

## 1) Primary result — final-task ITT success

| arm | sends/task | tasks | ITT successes | **ITT success** | invalid/unparseable |
|---|---:|---:|---:|---:|---:|
| **A single-shot** | 1 | 16 | 13 | **81.25%** | 0 |
| **B stepwise (5 visible states)** | 5 | 16 | 14 | **87.5%** | 0 |

**Zero invalid or unparseable outputs in all 96 sends.** Every failure in
both arms is a wrong final value — not a format/execution breakdown.

## 2) Paired discordance (same task, both arms)

16 paired comparisons: **12 both-correct, 2 B-only, 1 A-only, 1
both-failed; 0 with any unparseable step.** Paired B−A = **+1** (B-only:
rotate-01/wave2, rotate-03/wave2; A-only: rotate-00/wave1; both-failed:
rotate-03/wave1). *[Correction 2026-10-28, owner decision: the pair
table originally read "13 both-correct" — re-derivation from the session
evidence gives 12 both-correct + 1 both-failed. The report JSON's
discordant counts (2/1) and the verdict were already correct.]*

- digits family: **8/8 in both arms** — perfect under both granularities.
- rotate family: A 5/8, B 6/8.

## 3) Predeclared verdict (frozen criterion)

**B ITT ≥ 14/16 AND paired B−A ≥ +3 → stepwise closes the gap.**

Result: B = 14/16 ✓ but paired = +1 ✗ → **criterion NOT MET.** Per the
frozen prospective this is terminal for the mechanism's line: the stepwise
limit is documented; no threshold adjustment, no rescue redesign. The
cost asymmetry (B = 5× A per task) is registered and stands.

## 4) Failure localization (the actual residual mechanism)

Both B failures (and all three A failures) are rotate tasks diverging at
**step 2 — "insert '_' after every third character"**:

- The evaluator implements join semantics: no trailing separator when
  the state length divides by 3 (`"ewgisp"` → `"ewg_isp"`, 7 chars).
- The model reads the instruction literally: insert after EVERY third
  character, including the final one (`"ewg_isp_"`, 8 chars) — or drops
  the separator/character at the boundary (`"eboook"` → `"ebo_ok"`).
- The divergence propagates deterministically through steps 3–5
  (window-6 selection and pair swaps act on different strings).

So the residual ~15–19% is concentrated in **one boundary-interpretation
ambiguity of a single step's wording**, not in sequencing ability,
state-tracking, or answer formatting. Under this apparatus, granularity
(single-shot vs stepwise-with-visible-states) changes little: the model
executes the same ambiguous step the same way in both arms. Removing the
ambiguity (e.g., "insert '_' between consecutive 3-character groups,
with no trailing separator") is an apparatus-text amendment — the
owner's decision, explicitly out of scope for this frozen run.

Sanity confirmation of the §0 correction: the previously impossible
rotate step-5-B tasks now pass whenever the chain is otherwise clean
(rotate-01 both waves B; rotate-03/wave2 B).

## 5) Answers to the registered question

> Can step-by-step execution with explicit intermediate states raise the
> final-task success of a CORRECT natural-language procedure from 75%
> (ITT) to a reliable level, WITHOUT adding information about the truth?

**No — not to the predeclared bar.** With a corrected procedure text the
single-shot baseline itself rises to 81.25% (the published 75% was
deflated by the step-5 defect), and stepwise execution adds only +1
paired task (87.5%). Stepwise execution does not add information; the
residual failures are wording-ambiguity errors the model commits
identically with or without visible intermediate states.

## 6) Implications for procedural memory on this model class

- Execution granularity is NOT the remaining lever on this apparatus:
  five visible states did not repair a boundary-interpretation error.
- The remaining lever is **unambiguous procedure semantics** (separator
  boundaries), then multi-round execution with feedback (per the
  interactive-fidelity result) for genuine error correction.
- Findings are specific to glm-5.3 on the coding endpoint, High/4096,
  the two novel grammar families, and this frozen task set. No claim
  about retention, transfer, or organizational use.

## 7) Evidence

Run `40652718082` (90-day artifact retention): `stepwise-manifest.json`
(frozen programs, corrected step lines, inputs, truths, 96-slot plan) +
18 session summaries + `stepwise-report.json`. Committed under
`research/c3r_g2/evidence_stepwise_20261028/`. All 96 slots consumed
exactly once; send accounting reconciles 96/96.
