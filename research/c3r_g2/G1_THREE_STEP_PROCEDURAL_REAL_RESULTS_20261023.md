# Real G1 three-step procedural agent memory — three completed cohorts (2026-10-23)

**Actual GLM-5.3 Coding provider study:** [GitHub Actions run #39997025654](https://github.com/ElephantRock/Resonance-World/actions/runs/39997025654) completed **success** in all three independent jobs, after prospective design and passing CI. Every send requested **thinking.enabled, reasoning_effort=low**. The project remained internal-only without external auditing or approval queues.

**Prospective protocol:** G1_THREE_STEP_PROCEDURAL_MEMORY_PROSPECTIVE_20261023.md.
**Code:** scripts/run_c3r_g1_three_step_procedure_live.py.
**Offline tests:** tests/test_c3r_g1_three_step_procedure_live.py (six new tests).
**Dispatch marker:** G1_THREE_STEP_PROCEDURE_REAL_DISPATCH_20261023.md.

## What was physically executed

Three separately seeded 8-context cohorts, four arithmetic and four text each, with three blinded A/B source probes per context. An **explicit deterministic agent-side reducer** translated the three subsequent correct/incorrect bits into an owner-private persisted three-character procedure. After source interpreter termination, a **new interpreter** loaded the capsule and asked GLM-5.3 to **execute the three ordered operations** on a newly sampled public holdout input, as opposed to merely echoing A/B.

Each context had three capacity-matched **three-character** capsule arms:
- Learned: source-grade-inferred policy for this context.
- Fresh: random untrained procedure sampled before source.
- Neutral: remembered policy from a different context in the same family, rotated in a fixed preplanned order. If the unrelated donor was incomplete, fall back to a precommitted random code.

No raw source transcripts, source grades, true private hidden programs or actual capsule contents entered the published qualification artifact or the holdout model prompt. Private targets and manifest stayed on the same internal ephemeral GitHub host. No external provenance or independently verified billing is claimed.

## Prescribed denominators and observed model responses

**Source:** 72/72 real A/B responses valid, 24/24 contexts source-eligible. **Holdout:** 70/72 final-result completions valid, **2 invalid_format** (one Learned arithmetic and one Neutral text, both in cohort 02). No retries, no not_sent rows, **144/144 real provider request reservations**, all with one provider dispatch attempt per logical slot.

| Cohort | Source valid | Learned correct / valid | Fresh correct / valid | Neutral correct / valid | Invalid holdout |
|---|---:|---:|---:|---:|---:|
| 01 | 24/24 | **8/8** | 1/8 | 0/8 | 0 |
| 02 | 24/24 | **7/7** (7/8 prescribed) | 0/8 | 0/7 | 2 |
| 03 | 24/24 | **8/8** | 0/8 | 0/8 | 0 |
| **Total** | **72/72** | **23/23** (23/24 prescribed) | **1/24** | **0/23** (0/24 prescribed) | **2** |

Prescribed qualification denominators: **24 per arm**, including invalid outputs. Correct rates: Learned **23/24 = 95.8%**, Fresh **1/24 = 4.2%**, Neutral **0/24 = 0%**. Within family: Learned 11/12 arithmetic and 12/12 text; Fresh 0/12 arithmetic and 1/12 text; Neutral 0/12 in both families. Across 24 context-level paired comparisons, Learned beat Fresh in 22, tied twice and lost zero; Learned beat Neutral in 23, tied once and lost zero. These are DESCRIPTIVE paired counts only, not a confirmatory causal significance test.

Across the three cohorts, holdout provider-reported completion token sums were **3,077 Learned**, **2,773 Fresh**, **2,649 Neutral**. Median local per-request latency was approximately **4.06 seconds Learned**, **3.86 Fresh**, **3.54 Neutral**. Provider-reported usage and monotonic local transport timing are not independently reconciled vendor invoices or matched compute budgets.

## Critical interpretation and asymmetries

**What is operationally established:** a stored **three-step** procedure derived from source feedback by a simple explicitly programmed agent controller was persistently retrieved in a separate Python model session and used to execute NEW tasks correctly in 23 of 24 planned Learned attempts.

**What is NOT established:** latent LLM acquired skill, model parameter updates, autonomous strategy invention, rich real-world procedures, or statistically balanced causal superiority over equally informative control memories. Each hidden bit was recoverable almost mechanically from ONE blind A/B probe and its correctness bit; this is not a hard learning problem.

**Placebo bias requiring correction in the next experiment:** Although the Neutral capsule matches Learned's **three-character representation**, its **statistical success probability is not equal to Fresh**. The hidden target steps were each balanced 2A/2B within the same four-context family, while Neutral received a code rotated from another family-matched context. Such rotation induces negative dependence per bit between the donor and recipient targets; Neutral is systematically disadvantaged compared with an independently random three-bit program. For a single target bit under 2A/2B balance, a different randomly assigned donor has 1/3 probability of bit agreement; independently random Fresh has 1/2. Therefore **do not call Neutral a balanced information-strength placebo** or treat its zero successes as a precise causal estimate.

The tasks remain just three simple deterministic transformations on arithmetic/text strings, and the two arms are given different *information* (the correct externally reconstructed procedure versus uninformed alternatives). Task results are strongly favorable to stored relevant experience by construction, but a powered G1 theory test requires hard/ambiguous multi-step learning, matched-prior controls, delayed retention at more than one distinct timepoint, and independently sampled task laws/contexts (the latter internally controlled rather than audited externally). Only three runs with reused task **families** were used; context units within the design are counterbalanced, not all independent Bernoulli observations.

**scientific_acceptance=false**. PR #310 remains Draft, no Pattern Register promotion or claim of Autonomous Institutions is justified.

## Immutable evidence artifacts and provenance

GitHub workflow archive IDs and original SHA-256:
- Cohort 01, ID **12519928545**: 383b6b4f61b423746d9d48e9df44c31fe691146cffde5e415e4a21ce8976590d
- Cohort 02, ID **12520291550**: 0db78894f976b894c10606ad86c0e8bf676ae3acaaa1c0c9d06d9ca93bdb3c24
- Cohort 03, ID **12519957914**: 78d9ad72b7c16750f4ff144dd50dab2e830921c4026a4248062f7235a1047db6

Locally reproduced and validated aggregate JSON SHA-256: **8e7d82f34a4fc78fab381f5b5a28674ed68bb81ddb9460d084b048d9762e855c**. Public evidence bundle with unmodified source archives + extracted redacted results + analysis report SHA-256 **1bb051f42449f90edf025caafa6fec6dc8548f51a361380cb33b99727e4ac6ff**. Private manifest/targets, source feedback rows, API credentials, and raw outputs were never uploaded.
