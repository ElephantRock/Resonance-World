# G1 interactive acquisition & execution fidelity — PROSPECTIVE (frozen before first send)

Status: **PROSPECTIVE / FROZEN 2026-10-26, before any provider dispatch.**
Authorization: project owner decision (2026-10-26): GO for the interactive
acquisition test WITH the execution-fidelity comparison merged in. Reasoning-
effort ablation deferred; no C3R-G2 transition before this experiment's
acquisition requirement is met on novel grammars.

## Research question (the failure-surface decomposition)

The novel-grammar pilot (RESULT REV1) isolated two distinct failures:
(a) acquisition — only 4/8 source proposals correct on novel families;
(b) execution — a source-CORRECT capsule was mis-executed on both retention
waves (rotate-03). This experiment measures the two surfaces SEPARATELY,
plus the value-of-retention comparison, under one preregistered protocol.

## Four comparisons (all on NEW grammar families, all High/4096, coding route)

| # | comparison | what it measures |
|---|---|---|
| C1 | static two-shot induction | baseline acquisition (replicates the pilot's blind condition) |
| C2 | interactive-feedback induction (bounded rounds) | does correction improve acquisition? |
| C3 | execution of an EVALUATOR-SUPPLIED correct capsule | execution fidelity alone (induction quality removed) |
| C4 | re-induction from raw examples at execution time | does the retained capsule add value over the same raw evidence? |

Primary (predeclared): (i) C2 final-capsule correctness vs C1 final-capsule
correctness (acquisition surface); (ii) C3 holdout execution success
(execution surface). Secondary: C4 vs C3 holdout success (value-of-retention);
failure-class distributions by session.

## Novel grammar families (frozen verbatim; compositions unused in any prior
C3R-G1 experiment)

### Family `bracket` — input: a uniformly random 5-character string over "<" and ">"

- Step1 A: flip every character (< ↔ >). B: leave unchanged.
- Step2 A: remove all "<". B: remove all ">".
- Step3 A: wrap the string as <<string>>. B: wrap the string as [[string]].
- Step4 A: reverse the string. B: leave unchanged.
- Step5 A: duplicate the string. B: append the string length as a decimal digit.

### Family `modpair` — input: two distinct integers in [10, 99], JSON {"a": A, "b": B}

- Step1 A: order the two numbers ascending. B: order them descending.
- Step2 A: join with "-". B: join with ":".
- Step3 A: duplicate the first number. B: duplicate the second number.
- Step4 A: replace every "9" with "Z". B: replace every "0" with "O".
- Step5 A: wrap in parentheses. B: wrap in angle brackets.

Inputs are rejection-sampled until all candidate programs give pairwise-
distinct outputs. Both families avoid the operation vocabularies of
arithmetic/text/digits/rotate.

## Units, sessions, budget (fixed before dispatch)

- 8 independent units (4 per family), private 5-bit programs, 2 source tasks
  per unit, 2 holdout tasks per unit per execution wave (fresh per wave).
- Session 1 (acquisition): per unit — C1: one blind two-shot induction send;
  C2: up to 3 bounded correction rounds (propose → per-example pass/fail
  bits → revise); the FINAL capsule of the bounded sequence is the arm's
  acquired procedure. Capsules persist owner-only; sessions separated.
- Session 2 (execution): per unit — C3: execute the evaluator-supplied TRUE
  program capsule on 2 holdout tasks; C4: re-induce from the same raw
  examples and execute on the same holdout tasks. One send per (arm, task).
- Hard send cap: **64** (8 C1 + ≤24 C2 rounds + 16 C3 + 16 C4), enforced by
  an independent durable ledger (campaign id
  sha256(anchor:zai:glm-5.3:interactive-fidelity-v1)). Budget exhaustion
  stops the run with a partial report; no slot is replenished.
- No retries. Every send in the denominator, classified:
  transport failure / malformed response / valid response. ITT: results
  reported by treatment intention; transport failures are reported
  separately from acquisition and execution errors and never silently
  dropped.

## G2-transition criterion (predeclared)

The acquisition requirement for considering C3R-G2 is BOTH:
(a) C2 final-capsule correctness ≥ 6/8 on novel families, AND
(b) C3 execution fidelity ≥ 15/16 on evaluator-supplied correct capsules.
Missing either records the capability limit and stops this mechanism's line.

## Failure preservation

All responses, including invalid and failed ones, are preserved with
(unit, comparison, round, failure class). Hidden programs never enter
prompts or public reports; prompts may disclose the grammar and the
CAPSULE BEING EXECUTED in C3 (that is the controlled treatment).
