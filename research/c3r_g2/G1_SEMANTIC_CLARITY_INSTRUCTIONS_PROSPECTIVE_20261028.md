# G1 semantic clarity of procedural instructions — PROSPECTIVE (frozen before first send)

Status: **PROSPECTIVE / FROZEN before any provider dispatch.**
Authorization: project owner limited GO (2026-10-28), following the
stepwise execution fidelity result (criterion NOT MET; all 5 arm-failures
were rotate tasks diverging at the separator-insertion step 2).
**Classification: diagnostic study driven by a prior result. It is NOT
independent confirmation of any earlier hypothesis.**

## Research question (owner-registered)

Does explicitly specifying separator placement and forbidding the
trailing separator improve procedure-execution success, with the true
program, model, resources and inputs held fixed?

## Design

- The 4 frozen public rotate programs ONLY (the family carrying the
  ambiguity; digits has no separator step). 2 waves x 2 fresh
  unambiguous inputs per (program, wave) = **16 tasks**, identical
  across arms.
- **Arm A (ambiguous):** the original frozen step-2 wording —
  "insert '-' after every second character." /
  "insert '_' after every third character."
- **Arm B (precise):** the exact-placement wording —
  "insert '-' between consecutive pairs of two characters, with no
  separator at the end of the string." /
  "insert '_' between consecutive groups of three characters, with no
  separator at the end of the string."
- The step-2 line is the ONLY difference between arms. Steps 1, 3, 4, 5
  are identical, including the corrected rotate step-5 B ('prepend 9').
- **Single-shot execution only** (1 send per task per arm) — isolates
  the wording effect from granularity/round effects. glm-5.3, coding
  endpoint, High/4096, temperature 0.
- Correctness: final answer == deterministic truth (frozen evaluator,
  unchanged — its join semantics ARE the precise reading).
- **ITT:** a task fails if the response is unparseable or wrong. All
  failures preserved in the denominator.
- **Hard send cap: 32** (16 A + 16 B), enforced by a shared cross-process
  O_EXCL slot ledger (files 0..31; over-budget and double-dispatch fail
  visibly). Cost-symmetric: 16 sends per arm.

## Predeclared success criterion

Rationale (from committed evidence): in the stepwise campaign, rotate
steps 1/3/4/5 never failed independently — all five rotate failures were
step-2 boundary divergences, and digits reached 16/16. If specification
ambiguity is the dominant residual cause, the precise arm should
approach that ceiling.

**B ITT ≥ 15/16 (93.75%) AND paired B−A ≥ +4** → ambiguity of the
specification is the dominant residual cause; proceed to feedback-based
procedure acquisition (acquire with feedback → store → execute across
fresh sessions).

**Otherwise** → the wording-fix path is CLOSED: model execution limits
persist under an unambiguous specification. No serial redesign, no
threshold adjustment, no rescue rounds.

## Explicitly out of scope

No feedback rounds, no stepwise execution, no digits family, no G2
transition, no platform work, no retrospective re-scoring of earlier
campaigns, and no use of the two reserved Probe sends.
