# C3R G1 — Fourth pilot: crossed A/B × arithmetic/text (offline design)

**Status:** construction-only, nonconfirmatory; zero new provider/model sends. The existing Draft PR #310 is not scientific acceptance, experiment authorization, or permission to modify prior W/H/D/G1 evidence.

## Why this follows the third live run

GitHub Actions [run 39800889211](https://github.com/ElephantRock/Resonance-World/actions/runs/39800889211) completed eight locally reserved real GLM-5.3 calls and two full three-arm holdout triplets. Arithmetic was B-true (learned 1/1, fresh 0/1, neutral 0/1); text was A-true (each arm 1/1). This evidence is exploratory and confounds correct target with task family. Its grade-free neutral control matched characters, **not provider tokens**. See `G1_THIRD_REAL_MULTISCHEMA_NEUTRAL_20261022.md`.

The next question is whether actual graded in-context feedback improves new-item accuracy **within each family when both A and B can be correct**, rather than simply reflecting the model's default-A tendency.

## Small crossed technical qualification — no execution authorized

| Family | A-target contexts | B-target contexts | Total |
| --- | ---: | ---: | ---: |
| Arithmetic operation order | 2 | 2 | 4 |
| Text transformation order | 2 | 2 | 4 |
| **Total** | **4** | **4** | **8** |

Each context is a proposed independently reset learner unit, with **2 distinct development tasks** carrying authentic evaluator-returned grades, then **1 new holdout task** administered to (i) learned, (ii) fresh, and (iii) grade-free neutral-metadata arms.

**Budget:** 8 contexts × (2 development + 3 qualification) = **40 prescribed logical attempts**: 16 development, 24 qualification, 8 complete-triplet opportunities. Authorized physical sends: **0**. This is not a 40-send authorization or a power calculation.

The public tasks must have noncommuting A/B operations, disjoint task IDs and operands across development and holdout, and opaque context identities. A separately controlled evaluator should create a keyed, prospectively sealed and **within-family balanced** target assignment. No per-context answer mapping or secret is admissible in public tasks, model prompts, output summaries or shared session context. A self-generated local commitment is not independent attestation.

Development grades may be returned **only after** submitting an accepted source A/B choice; no holdout grade, correctness, score, intermediate success metric, or target is disclosed until every qualification attempt is closed. The fresh arm sees no development history. A neutral arm may see public task IDs plus label-free fixed placeholders, **never** actual source actions or grades. It must be validated for comparable provider-token and compute exposure to the learned arm; character parity alone is insufficient. Deliberately misleading sham histories remain a separate intervention, not a neutral control.

Session identities must be distinct between learner contexts, between development and qualification, and across qualification arms. Merely assigning different IDs does not attest session separation. Order must be preregistered and balanced/randomized independently from truth assignment, with all source development completed before any holdout disclosure.

## Descriptive outcome reporting

Report ITT heldout correctness `learned - fresh` and `learned - neutral` separately for each (family, A/B truth) cell; the diagnostic within-family interaction is `(learned-fresh | B) - (learned-fresh | A)`. All attempts, malformed outputs and missing responses remain in the prescribed denominator. Disclose A/B choice frequencies by arm, accepted-action yield, complete-triplet yield, source feedback exposure, token usage, provider failures and cost envelope. Treat the **learner context** as the proposed inferential unit; the triplet's three responses are not independent units.

With **only two contexts per family × target cell and one qualification item per context**, the crossed exercise is descriptive **even if all 40 logical attempts complete**. It cannot be retrospectively promoted to a powered G1 result.

## Runtime and scientific gates — all remain closed

Before any independently authorized live run: (1) independent evaluator ownership, signed target and grade receipts and private custody; (2) actual model-session isolation and no cross-context leakage; (3) token-matched neutral history and fair compute; (4) separate source/calibration/holdout locks and preflight yield; (5) frozen provider route, physical-send reservations and cost controls; (6) preregistered inferential unit, paired/cluster design, power, minimum analyzable N, alpha/multiplicity, CI, SESOI classification, missingness and replication contract; (7) explicit operator-approved one-shot dispatch.

No live workflow, credential access, model call, registry promotion, main merge or G2/G3/G4 claim is part of this documentation update. This proposal complements the existing offline v2 multi-schema construction but does **not** claim that its current runner implements this full crossed neutral-control protocol.

## Offline construction files and verification

- `src/resonance_world/c3r_g1_crossed_plan.py`: credential-free public task/schedule lock and structural audit, plus **local-test-only** HMAC-keyed private target-balancing utility (2 A + 2 B within each family).
- `tests/test_c3r_g1_crossed_plan.py`: five construction and negative tests checking count/split integrity, strict exact A/B actions, private balance without public target disclosure, unauthorized schedule mutations, and no credential/provider dependence.

Local standalone run on 2026-10-22: **5 tests passed**. This is a local construction result, not repository CI attestation; CI must be checked separately.

To inspect with no credentials or network:

```bash
python -m resonance_world.c3r_g1_crossed_plan
pytest -q tests/test_c3r_g1_crossed_plan.py
```

The CLI emits a public structural digest and `physical_sends=0` with `scientific_acceptance=false`. The current planner **does not implement a live model runner, session isolation, neutral prompt token parity, an independently operated evaluator, result estimator or provider dispatch**. The public digest is self-generated, not a signed evidence receipt. This document and code belong only to Draft PR #310, without acceptance or authorization for live work.


## Qualification-view preflight (2026-10-22, offline only)

The follow-on module **src/resonance_world/c3r_g1_crossed_preflight.py**
constructs candidate holdout-arm views without provider access; it does not
authenticate evaluator data or authorize a run.

- **Frozen plan:** requires the exact public digest generated by the existing
  crossed plan (00661fe7dd37086f08f8458b13a57cc1e8b2123fd00e31918dedf8d26a3cdf6e).
  Structurally valid but modified input plans are rejected. This is a local
  freeze check, not an independent signed preregistration.
- **Development:** requires exactly 16 distinct source observations, each
  carrying an exact A/B choice and binary correct/incorrect feedback.
  Source authenticity and grade provenance remain unattested.
- **Session references:** requires 32 unique local identifiers, one for each
  development/learned/fresh/neutral context phase. String distinctness is
  **not** actual physical or provider-session isolation.
- **Holdouts:** renders 24 views in locked schedule order. The learned
  arm receives public source tasks plus choices and grades; the neutral
  arm receives public source tasks plus grade-free attempt-presence metadata;
  the fresh arm receives no source history. The function takes no private
  target-assignment map or holdout labels.
- **Parity:** an optional caller-supplied local token counter diagnoses
  eight learned-neutral view pairs but never certifies provider-token or
  compute parity. No automatic padding or synthetic fairness claim is made.

The audit always marks physical sends zero, physical-send authorization
false, live readiness false, independent evaluator receipt attestation false,
provider session isolation false, and scientific acceptance false.

Companion tests: **tests/test_c3r_g1_crossed_preflight.py** exercises source
errors, missing or reused sessions, neutrality under source-feedback changes,
misleading local tokenizers and modified-plan rejection. **11 tests** passed
locally on October 22 across the two crossed-plan test files, not yet a claim
about CI status for the subsequent GitHub branch head.

**Remaining blockers:** signed independently controlled evaluator receipts and
target custody; genuine provider session separation; neutral provider-token
and compute parity; audited qualification ordering independent of target;
one-shot operator approval and capped provider send/cost contract. The
currently frozen schedule is deterministic rather than randomized. This
offline view construction does not resolve those blockers.


## Descriptive outcome audit with missingness bounds (2026-10-22)

The additional **src/resonance_world/c3r_g1_crossed_outcomes.py** is
credential-free and accepts only a frozen public plan and an explicitly
completed table of **40 prescribed logical attempt records**. Each record
must identify a scheduled unit/task/stage/arm, status, and—if and only if
accepted—an exact A/B action and a boolean *reported* correctness. Missing,
duplicate, alien, contradictory or malformed rows fail closed. Non-accepted
attempts are recorded as invalid_format, provider_error or not_sent
with neither accepted action nor claimed score.

The returned audit accounts separately for **16 development and 24
qualification attempts**, the eight potential triplets, complete
development histories, accepted responses by arm, and family-specific
descriptive scores. With unresolved holdouts, each arm's accuracy is
reported as two **missing-data extreme-case bounds**: a lower score if all
unresolved tasks are incorrect and an upper score if all are correct.
Learned-minus-fresh and learned-minus-neutral bounds preserve the
context-level denominator. These are **not confidence intervals**, a
randomization-based causal estimate, missing-at-random assertions,
a power calculation, or evidence of G1 acquisition.

The public summary exports no target assignment and no per-context
scored actions. It explicitly declares target_cell_stratification_available=false:
the A/B × family interactions requested for a future evaluator-controlled
analysis are **not estimable by this public-only layer**. An authorized
independently operated evaluator must compute its own blinded,
preregistered target-stratified analyses without sending the target map to
a model or worker.

**All input correctness flags and accepted actions remain unattested.**
No signature, independently verified provider send, authentic score
receipt, actual session separation, token parity or provider billing
reconciliation is provided. Output flags for those criteria are always
false, as is scientific_acceptance. Even a fabricated file of 40 perfect
attempts produces only unattested descriptive arithmetic. The audit is
not connected to live dispatch.

Companion **tests/test_c3r_g1_crossed_outcomes.py** adds five negative
and denominator-preservation tests. The three crossed-plan test modules
passed **16/16 local tests** on October 22; GitHub CI is reported
separately and only when its current result is confirmed.

No extra provider sends, live workflows, new registry patterns,
claim promotion or default-branch changes were requested or performed.
