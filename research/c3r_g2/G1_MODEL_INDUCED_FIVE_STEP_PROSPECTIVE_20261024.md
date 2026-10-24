# Prospective G1 GLM-authored 5-step memory experiment — 2026-10-24

**Registered BEFORE actual provider dispatch.** Internal-first real experimentation authorized by owner, without a spending ceiling, external auditors or approval bottlenecks. PR #310 Draft, scientific_acceptance=false.

## Research question and important distinction

Earlier G1 experiments relied on a programmed agent-side solver that reconstructed each A/B step from per-step binary grades, or eliminated a complete program from eight candidates. This study tests whether the actual GLM-5.3 MODEL, not the controller, can infer a hidden **five-step procedure (32 possibilities)** from TWO corrected whole-program input/output examples. The model returns a five-character A/B policy. The controller freezes that proposal *verbatim*, even if wrong; source correctness is evaluated but never fed back. A separate interpreter reloads the GLM-authored capsule to execute a NEW task; a third interpreter reloads it again to execute another NEW task. No hidden step labels or raw training examples appear in holdout prompts.

Unlike the previous terminal-only binary grades, this experiment uses corrected final outputs as training supervision. A transparent five-step grammar may make the code readily identifiable from one example. Successful source inference is model-authored but not necessarily advanced algorithm invention or novel autonomous expertise.

## Frozen task, groups and baseline

- Three independently randomized cohorts, each with 8 new opaque contexts (4 arithmetic and 4 text). The FIVE target A/B bits are individually balanced 2A/2B within each 4-context family.
- Arithmetic operations, in order: add/subtract a; multiply by 2/3; add/subtract b; multiply by 5/7; add/subtract c. Text operations: prefix q/r; suffix 3/7; uppercase/lowercase; reverse/no reverse; prefix !/?. Hidden targets are randomly sampled. Source input/output examples and both new holdout tasks are freshly sampled. The arithmetic task generator requires all 32 program outputs to be distinct.
- Each source induction request sees the five public A/B operation pairs plus two previously unseen inputs with their CORRECT final outputs. The model must return exactly five A/B letters. No controller-side enumeration, repair, target recovery or per-step correctness feedback is admitted to the model training phase. An invalid/ambiguous model proposal stays invalid, and its 6 holdout attempts are not_sent.
- At holdout all arms receive the same prompt renderer and exact FIVE-character policy. Learned uses the **unchanged, model-authored proposal**. Fresh and Neutral use TWO separately presampled uniform random five-bit codes, each independently distributed over 32 possibilities, unrelated to target or training outcomes, exact-match probability 1/32 ex ante. They are equal-capacity RANDOM baselines, not experienced other agents. All arms must execute the 5 steps and return the final numeric/text result.
- Model is GLM-5.3, Z.AI Coding route, thinking.type=enabled and reasoning_effort=low, output cap 4096 including reasoning, timeout 120 seconds, max 3 concurrent calls/cohort and 2 concurrent cohort jobs. No retries or billing attestations.
- Exactly 8 prescribed induction and 24 prescribed holdout slots for EACH of retention1 and retention2, or **56 slots per cohort and 168 logical campaign slots**. The same 24 context units are re-tested across both waves; 48 observations are not 48 independent subjects. Do not discard invalid/failed/not_sent rows.
- Each run has an exclusive private 0700 workspace, immutable 0600 local files and full fsync, exclusive persisted send reservations before every provider attempt, and phase-level exclusive no-replay start markers. Each wave runs in a separate Python interpreter with no shared in-process source state. The two waves occur in chronological order but no hours/days delay is required or claimed.
- Raw source examples, task operands, hidden targets, model-authored capsule contents, raw provider bodies and credentials stay in private workspace. Upload only redacted source correctness and per-context holdout statuses, grades, local latencies and provider-reported usage.

## Interpretation and endpoints

Primary descriptive estimands: model source proposal target-match correct/8 per cohort, and Learned versus random Fresh/Neutral full five-step correct result /8 per arm per wave, intention-to-treat. Report independent cohort outcomes and within-context first-to-second-wave change, nonvalid/unsent responses, and provider-reported tokens and latency. An incorrect but valid learned proposal is **not** corrected by the experiment controller, allowing direct falsification of the model-induction claim.

A deterministic inference algorithm remains possible for the transparent task grammars, but no such solver is invoked on source model output by the agent runtime. There is no powered confirmatory test, model-weight update, long-duration retention or institution-level regeneration evidence. Scientific acceptance stays false until stronger evidence and internal scientific review. No Pattern Register promotion and no PR merge.

Implementation:
- scripts/run_c3r_g1_model_induced_five_step_live.py
- tests/test_c3r_g1_model_induced_five_step_live.py

The one-time real-model workflow will be introduced and launched only after Ruff, pytest and the architecture audit pass.
