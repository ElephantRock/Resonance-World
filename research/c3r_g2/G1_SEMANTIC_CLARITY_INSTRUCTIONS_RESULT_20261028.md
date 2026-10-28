# G1 semantic clarity of procedural instructions — RESULT (2026-10-28)

**Run:** GitHub Actions `40669477667` — all 6 jobs succeeded.
**Campaign:** 32/32 sends (Arm A ambiguous 16 + Arm B precise 16;
cross-process O_EXCL slot ledger 0..31 consumed once each; cost-
symmetric). glm-5.3, coding endpoint, High/4096, temperature 0.
**Design (frozen before first send):**
`G1_SEMANTIC_CLARITY_INSTRUCTIONS_PROSPECTIVE_20261028.md` — 4 frozen
rotate programs x 2 waves x 2 fresh unambiguous inputs = 16 tasks,
identical across arms; the step-2 line is the ONLY difference between
arms (original ambiguous wording vs exact-placement wording with no
trailing separator). Single-shot execution.
**Classification:** diagnostic study driven by the stepwise result; NOT
independent confirmation of any earlier hypothesis.
`scientific_acceptance=false`.

## 1) Primary result — final-task ITT success

| arm | step-2 wording | tasks | ITT successes | **ITT success** |
|---|---|---:|---:|---:|
| **A** | ambiguous (original) | 16 | 11 | **68.75%** |
| **B** | precise (exact placement, no trailing separator) | 16 | 15 | **93.75%** |

Paired table: **10 both-correct, 5 B-only, 1 A-only, 0 both-failed.**
Paired B−A = **+4**.

## 2) Predeclared verdict (frozen criterion)

**B ITT ≥ 15/16 AND paired B−A ≥ +4** → ambiguity of the specification
is the dominant residual cause.

Result: B = 15/16 ✓ and paired = +4 ✓ → **criterion MET, at both
thresholds exactly (no margin).**

Answer to the owner-registered question: yes — explicitly specifying
separator placement and forbidding the trailing separator improves
procedure-execution success with program, model, resources and inputs
held fixed. The residual rotate failure is caused by specification
ambiguity, not by model execution limits.

## 3) Failure breakdown (honest reading, no post-hoc rescue)

- **Arm A's 5 failures are all separator-boundary tasks:** the four
  rotate-03 tasks (`BBBAB`, the `'_'` branch) and rotate-01#1 (the
  `'-'` branch). Answers show the same literal trailing-separator /
  divergent-chain pattern as in the stepwise campaign
  (e.g. `9_jki_d` vs truth `9jvi_dk`).
- **Arm B's single ITT failure is NOT a comprehension failure:** task
  rotate-01#0/wave1 ended in `provider_error`
  (`ProviderTransportRejected` after 561 ms — a fast transport
  rejection; no retry, per protocol). Among **evaluated** responses the
  precise arm is **15/15 (100%)**.
- Decision-relevant nuance, corrected per owner review (2026-10-28): the
  frozen ITT rule already counts the transport failure in the
  denominator — B is 15/16 **with** it. Had that send been answered
  correctly, B would be 16/16; had it been answered wrong, B would
  remain 15/16. The zero margin is real but lies in the fifteen
  successes: losing any ONE of them to a wrong value drops B to 14/16
  and the criterion would not be met. The registered verdict stands as
  computed; this paragraph exists so the reader knows where the margin
  sits.

## 4) Implications

- The wording of a single ambiguous instruction line was worth **+4
  paired tasks** on identical programs and inputs — larger than the
  entire stepwise-granularity effect (+1) at one-fifth of its cost.
- Procedural instructions for this model class must specify boundary
  semantics explicitly (separator placement, windows, counts). The
  precise step-2 text is frozen in the committed manifest and is the
  baseline wording going forward.
- Per the owner's decision framework, the next test is now worth
  running: **feedback-based procedure acquisition → storage → execution
  across fresh sessions**, with unambiguous wording. C3R-G2 remains
  deferred until that chain is demonstrated.

## 5) Evidence

Run `40669477667` (90-day artifact retention): `clarity-manifest.json`
(frozen programs, both arms' step texts, inputs, truths, 32-slot plan) +
4 session summaries + `clarity-report.json`, committed under
`research/c3r_g2/evidence_semantic_clarity_20261028/`. Send accounting
reconciles 32/32; both prior campaigns' numbers remain un-re-scored
(owner decision 2026-10-28).
