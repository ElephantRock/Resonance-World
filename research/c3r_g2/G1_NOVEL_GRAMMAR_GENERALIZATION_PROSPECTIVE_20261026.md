# G1 novel grammar generalization — PROSPECTIVE (frozen before first send)

Status: **PROSPECTIVE / FROZEN 2026-10-26, before any provider dispatch.**
Authorization: project owner GO (2026-10-26) resuming the C3R-G1 track from
`G1_FIVE_STEP_INFERENCE_FACTORIAL_REAL_RESULTS_20261024.md`, whose predeclared
next discriminating test this document implements: NEW procedural grammars,
NEW context samples, four discriminating arms, separate process sessions,
High/4096 fixed, no retries, failures preserved.

## Hypothesis (exploratory pilot, not confirmatory acceptance)

An agent using GLM-5.3 (High/4096) can (a) induce a correct novel five-step
procedure from two corrected examples, (b) retain it across separate process
sessions as a capsule, and (c) apply it to NEW holdout inputs — and the
retained capsule yields higher holdout success than re-deriving from the same
raw examples at execution time, than no-experience capsules, and than chance.

## Novel procedural families (frozen verbatim)

Input domain and operation set are compositions never used in any prior
C3R-G1 experiment (prior families: arithmetic +a/×2/3/×5/7 and text
q/3/case/reverse/!?). Primitive operators may share generic forms; the
compositions, input domains and step semantics are new. Inputs are
rejection-sampled until all 32 candidate programs produce pairwise-distinct
outputs on that task (no ambiguous units).

### Family `digits` — input: a uniformly random 4-digit decimal string

- Step1 A: swap the two middle digits. B: leave unchanged.
- Step2 A: keep only the first two digits. B: keep only the last two digits.
- Step3 A: replace each digit d with (d+1) mod 10. B: replace each digit d
  with (d+9) mod 10.
- Step4 A: arrange digits descending. B: arrange digits ascending.
- Step5 A: prefix the digit count. B: append the digit count.

### Family `rotate` — input: a uniformly random 6-letter lowercase string

- Step1 A: rotate the string left by 2. B: rotate the string right by 2.
- Step2 A: insert "-" after every second character. B: insert "_" after every
  third character.
- Step3 A: keep the first 7 characters. B: keep the last 7 characters.
- Step4 A: swap every adjacent character pair. B: leave unchanged.
- Step5 A: append "9". B: prepend "5".

## Units and slots

8 independent context units (4 per family), each with a private uniformly
random 5-bit program, two source tasks, and TWO holdout tasks per retention
wave (fresh tasks per wave, never reused). Private programs live only in the
owner-only manifest written once before dispatch (O_EXCL, 0600).

| session | process | sends |
|---|---|---:|
| induction | 1 job | 8 (one source induction per unit) |
| wave 1 | 4 jobs (one per arm × 8 units) | 32 |
| wave 2 | 4 jobs (fresh holdout tasks) | 32 |
| **total** | 9 dispatches | **72** |

## Arms (all High/4096, temperature 0, glm-5.3, coding route)

1. **learned** — execution prompt: grammar + the unit's induced capsule
   (verbatim from the induction session) + new holdout task. No examples.
2. **raw** — execution prompt: grammar + the unit's TWO source training
   examples + new holdout task. No capsule. (Re-induce inline, then execute.)
3. **fresh** — grammar + a uniformly random capsule + new holdout task.
4. **neutral** — grammar + a second independent random capsule + new holdout.

Arm D (deterministic control): the true program's executed output, computed
offline by the evaluator — no provider call; it defines correctness.

## Outcome taxonomy

- Induction (learned arm only): `length_exhausted`, `invalid_format`,
  `valid_wrong`, `valid_correct`, `provider_error` — identical classes to the
  factorial.
- Holdouts (every arm): final value compared to the true program's executed
  output → `correct` / `wrong`; provider failures → `provider_error`.
- Discrimination note (predeclared): source-correctness of the induced
  capsule is REPORTED separately from holdout execution success; a correct
  capsule executed wrongly, or a wrong capsule executed "correctly" against
  its own policy, are distinct outcomes and never merged.

## Primary estimand

Paired per-(unit, wave) holdout success difference: **learned − raw**, on NEW
grammar families and NEW holdout tasks, in separate processes. Secondary:
learned − fresh, learned − neutral, fresh/neutral success rate, induction
valid/correct rates, per-family breakdown, per-arm failure classes.

## Failure preservation and stop rules

No retries, no repair, no regeneration. Every prescribed send lands in the
denominator with its failure class. Provider/refusal failures consume the
slot and mark the (unit, wave, arm) outcome `provider_error`; the world is
not re-run. If a wave process aborts early, completed units are reported and
incomplete units are labeled, never silently dropped.

## Explicit limitations

Exploratory pilot; one world; descriptive statistics; no confirmatory
causal claim; effort values are requested settings; repeated measurement on
the same unit across arms is paired, not independent; primitive operators
may resemble generic forms used elsewhere — novelty is at family
composition level; successful holdout execution demonstrates procedure USE,
not human-readable understanding.
