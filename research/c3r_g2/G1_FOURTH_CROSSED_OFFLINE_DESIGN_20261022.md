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

## Offline implementation artifact

A standalone local construction patch accompanies this design in the working conversation, with a proposed deterministic public task/schedule builder, private HMAC-keyed **local test** balancing, explicit structural audit, and five passing offline tests. **That patch is not in GitHub unless separately committed and CI-verified.** Its local private assignment is not a substitute for a separately operated evaluator. This document is the research-branch record, not an attestable execution lock or license to run a provider.