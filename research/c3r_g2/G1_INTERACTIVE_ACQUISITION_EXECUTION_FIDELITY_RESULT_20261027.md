# G1 interactive acquisition & execution fidelity — RESULT (2026-10-27) — REV1 (send accounting corrected per owner review)

**Run:** GitHub Actions `40391144622` — 10/10 jobs succeeded.
**Campaign:** **52 model sends total** (C1: 8; C2: 12 across 4 group jobs ×
2 units, bounded 3 rounds — under its 24-send budget because early-pass
units exited after round 1 and the vacuous-break defect ended two malformed
rounds after one send each; C3: 16; C4: 16). Reconciled 2026-10-26 against
the nine published session summaries in
`evidence_interactive_fidelity/SEND_RECONCILIATION.md`; an earlier draft of
this document claimed 72 — withdrawn as a drafting error.
**Preregistration:** `G1_INTERACTIVE_ACQUISITION_EXECUTION_FIDELITY_PROSPECTIVE_
20261026.md` (frozen before dispatch; amendment A1: bracket step4 redefined
pre-dispatch after local unambiguity verification caught a no-op collision).
**Classification:** exploratory pilot; `scientific_acceptance=false`.

## 1) Headline: the meta-task is the bottleneck, not the task

| comparison | result | reading |
|---|---|---|
| C1 static induction | 5/8 source-correct (62.5%; 1 invalid) | moderate degradation vs known families (~90-100%) |
| C2 interactive (≤3 rounds) | 2/8 final capsules correct (**25%**) — WORSE than C1, partly an apparatus defect (§4) | interactive correction did not demonstrate improvement |
| C3 execution of an EVALUATOR-SUPPLIED CORRECT capsule | **3/16 (18.75%)** | **the dominant failure surface**: GLM-5.3 does not faithfully execute explicit A/B-step procedures |
| C4 raw re-induction at execution | 10/11 evaluated correct (**90.9%**; 5 invalid unscored) | the model performs the underlying task excellently when NOT forced through the procedure representation |

**The inversion:** the model excels at the object-level task (C4 ≈ 91%) and
fails the meta-task of encoding/executing explicit procedures (C3 ≈ 19%).
The bottleneck is NOT capability on the task; it is the procedure
representation itself.

## 2) Why the controls validate the design

- The balanced rule switch was real: execution against post-switch rules with
  PRE-switch procedures (or random capsules) yields chance-level values —
  visible in C3's failures and C4-invalid structure.
- No leakage: leak-discipline identical to the pilot; grammar disclosed, the
  5-bit secret never entered any prompt.
- fresh/neutral chance capsules in the previous pilot: 0/15 and 2/13 —
  consistent with 1/32 collision expectations.

## 3) Failure-surface decomposition (the owner's question answered)

The owner asked: does the failure sit in LEARNING, in RETAINING, or in
EXECUTING?

1. **Learning-to-capsule (C1/C2):** partially impaired on novel grammars
   (62.5% static; interactive rounds showed no demonstrated gain, with an
   apparatus defect corrupting 2 of 8 interactive units — §4).
2. **Retention across sessions:** mechanically sound — capsules persisted
   verbatim across separate processes (the custody chain is text-exact).
3. **Execution fidelity (C3):** **catastrophic — 3/16.** Even with the
   correct capsule explicitly supplied, GLM-5.3 improvises a plausible
   transformation instead of step-wise executing it. Failure examples show
   right data, wrong procedure: correct inputs/outputs vocabulary, wrong
   wrapper/separator/duplication choices.

## 4) Apparatus defect disclosure (C2)

`run_c2_group`'s round loop breaks when `all(outcomes)` is true — but an
INVALID round-1 answer produces an empty outcome list, and `all([])` is
vacuously true, aborting the interaction after one malformed round instead of
requesting revision. Two units (bracket-00, bracket-01) were affected; their
C2 finals are None and the interactive arm's 25% UNDERSTATES what a healthy
loop would show. The defect is fixed in
`scripts/run_c3r_g1_interactive_fidelity_live.py` (empty-outcomes no longer
terminate the loop) and is registered as an apparatus correction — it does
not rescue the C3 result, which is defect-free (no loop involved).

## 5) Verdict per the predeclared gates

| gate | threshold | observed | verdict |
|---|---|---|---|
| C2 acquisition (≥6/8) | 6 | 2 | **FAIL** (defect-adjusted upper bound still <6) |
| C3 execution fidelity (≥15/16) | 15 | 3 | **FAIL** |

Per the C3R-G2 worksheet rule ("if a source agent fails to acquire the
prerequisite ability under the new schema, stop at G1"): **the line stops
here.** No organizational test is justified on this mechanism; documenting
the limit IS the scientific output of this cycle.

## 6) The scientific reading for the roadmap

GLM-5.3 on novel procedural grammars is task-competent but
procedure-representation-blind: 91% correct when freed to answer directly,
19% correct when asked to execute an explicit step-procedure it is HANDED.
Any future acquisition design must either (a) use a representation the model
executes faithfully (e.g., natural-language rules rather than A/B codes —
untested), or (b) accept that explicit procedural memory is not this model's
mechanism and route organizational questions through task-level performance
instead.

## 7) Evidence

Run `40391144622` (90-day artifact retention): `fidelity-manifest-c1`
(owner-only: hidden programs), `fidelity-c2-group-{0..3}`
(round histories incl. the defect), `fidelity-c3-{wave1,wave2}`,
`fidelity-c4-{wave1,wave2}`. Aggregate summaries committed with this
document; hidden programs are not in the Git tree.
