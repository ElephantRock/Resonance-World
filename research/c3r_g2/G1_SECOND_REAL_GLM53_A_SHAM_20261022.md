# G1: Second real GLM-5.3 A-law with independent sham feedback — 2026-10-22

**Status: real exploratory provider run complete, NOT scientific G1 acceptance.** No continuing automation or further provider sends authorized by this run.

## Source and provenance

- Successful GitHub Actions job: https://github.com/ElephantRock/Resonance-World/actions/runs/39790290483
- Re-run attempt 2 job ID: `119864536761`. Initial attempt was blocked BEFORE reading the credential or dispatching; an earlier workflow rerun `39789416281` ended in `startup_failure` without a new job, so the trigger was adjusted and submitted exactly once more.
- Artifact `c3r-g1-second-real-A-sham-20261022`, ID `12430143335`; ZIP SHA256: `c63eadee19a25f60fcffca73bb0f49ac8c1d10cda46b5c086a94b612dc53060c`. Original sanitized JSON inside ZIP: `real-A-sham.json`. GitHub artifact expires after 14 days; it is not independent WORM retention.
- Experiment implementation: `scripts/run_c3r_g1_a_counterlaw_live.py` on research branch. Unique opaque context `c3r-k7-opaque-20261022`. Correct law **A = (value + offset) * factor**, intentionally opposite the previous first real pilot's fixed B target.
- Provider/model as configured: `glm-5.3`, Z.AI coding endpoint; completion-token cap 16,384 per call, `reasoning_effort=low`, up to 8 physical-send reservations, no SDK retries or redirects.
- First counterlaw live workflow was removed from the branch after successful completion. Draft PR #310 remains unmerged.

## Prespecified eight-call scope

| Phase | Number | Handling |
| --- | ---: | --- |
| Development | 2 | Each answer is graded locally against target A; real source choice and grade passed only to learned arm |
| Holdout: learned | 2 | Both real development records supplied; no holdout feedback during qualification |
| Holdout: fresh | 2 | No source records supplied |
| Holdout: sham | 2 | Two development-task records with **synthetic independent choice B / success=true** labels, regardless of what learned actually chose; no real grade |
| **Total** | **8** | Two matched three-arm qualification triplets |

**This sham is directional/misleading**, not a neutral matched-memory control. Prompt lengths and tokens are not exactly matched. A sham deficit alone cannot be construed as evidence for persistent learning.

## Verified results

| Phase | Accepted / prescribed | Correct | Choices |
| --- | ---: | ---: | --- |
| Development | 2/2 | 2/2 | A, A |
| Holdout learned | 2/2 | **2/2** | A, A |
| Holdout fresh | 2/2 | **2/2** | A, A |
| Holdout sham | 2/2 | **0/2** | B, B |

- **Two of two** qualification three-arm triplets were complete and analyzable. Observed learned-minus-fresh difference was **0 percentage points**, learned-minus-sham **+100 percentage points** on these two items. There is no powered inference from either comparison.
- All 8 self-produced transport reservations show **HTTP 200** and no failure class; all 8 model completions have `finish_reason=stop` and exact A/B output. Output hashes were independently mapped to SHA256(A) or SHA256(B) in the downloadable artifact; every grade was checked against the frozen target A and observed operands.
- Local reported completion-token total: **333**, of which **305** were reported as reasoning. Breakdown: development 20 (12 reasoning); learned qualification 121 (114); fresh 43 (36); sham 149 (143). These API-reported numbers are NOT vendor-invoice attestation.

### Public qualification operands and alternative outputs

| Held-out item | Value | Offset | Factor | A target | B alternative | Learned | Fresh | Sham |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| holdout 13 | 13 | 4 | 7 | **119** | 95 | A | A | B |
| holdout 14 | 1 | 7 | 5 | **40** | 12 | A | A | B |

## Comparison to first live pilot

| Pilot | Correct fixed law | Learned correct | Fresh correct | Sham correct |
| --- | --- | ---: | ---: | ---: |
| First real run, GitHub `39780461001` | B | 2/2 | 0/2 | not tested |
| Second real run, GitHub `39790290483` | A | 2/2 | 2/2 | 0/2 |

Across the four qualification items, **fresh chose A in all four cases**; learned chose the correct A/B in all four cases after source feedback. This is evidence that the *in-context feedback text* influences behavior in the two short runs, but a fresh A default alone explains the first pilot's apparent uplift when the correct answer is B, and the tie when it is A. The two contexts and task-item sets were not randomized, with different training counts and no common sham arm, so pooling is **descriptive only**.

## Scientific interpretation

1. The original B-only pilot's `2/2 vs 0/2` contrast **did not replicate as a learned-over-fresh advantage under target A**: here both learned and fresh were 2/2. Thus no robust, direction-invariant G1 uplift has been demonstrated.
2. The learner and sham followed the information content of their supplied feedback in a way consistent with context-sensitive instruction following. This does not demonstrate persistent autonomous memory across calls: history is repeated directly in each prompt.
3. The sham records deliberately recommend the wrong B rule; poor sham performance cannot substitute for a neutral placebo, a matched token budget, randomized target assignment, or evaluator-independent outcome auditing.
4. Only two holdout tasks per pilot, one context per run, one arithmetic task family, and no independent learner units. All grading is local; backend request IDs, invoice amount and spending eligibility are not independently confirmed. `scientific_acceptance=false` remains mandatory.

**Next scientific priority** is a single preregistered study with counterbalanced A/B truth, independent learner units, a neutral well-matched placebo (not overt misleading labels), at least one different task family (text), and randomized assignment. No further live calls or Pattern Register promotion are implied by this report.
