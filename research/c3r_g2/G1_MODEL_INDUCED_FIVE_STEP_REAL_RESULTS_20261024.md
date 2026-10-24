# Real G1 GLM-authored FIVE-step policy induction and two independent execution sessions

**Date:** 2026-10-24. **Real provider trial:** https://github.com/ElephantRock/Resonance-World/actions/runs/40049076812 (all three independent cohort jobs succeeded). **Frozen protocol:** G1_MODEL_INDUCED_FIVE_STEP_PROSPECTIVE_20261024.md, committed and CI-tested before the unique dispatch marker. **Code:** scripts/run_c3r_g1_model_induced_five_step_live.py and tests/test_c3r_g1_model_induced_five_step_live.py. Model GLM-5.3 Coding, thinking.type=enabled and reasoning_effort=low (not disabled), max completion tokens 4096, bounded 3 calls/cohort, max two cohorts running in parallel, timeout 120 seconds, no retries.

## Central scientific distinction

In previous G1 pilots the agent's hand-coded reducer reconstructed a 3-bit program from labelled per-step grades or exhaustive elimination. This experiment required the **actual GLM model** to produce its own **5-bit procedural hypothesis (32 possibilities)** from TWO fully corrected terminal input/output examples. The agent persisted the model's five-character policy, **including valid but WRONG proposals, without repair**, and terminated its source Python process. Later Python interpreters applied that same saved policy on fresh operands in retention1 and retention2. Private evaluator alone compared proposal to hidden target; grades were not fed back to source or holdout. Independently uniform, equal-capacity Fresh and Neutral capsules had an a priori probability of 1/32 of matching each context's target program. Every attempted response and prescribed but not-sent slot remains in the intended denominator.

## Actual provider evidence (three independent cohorts)

| Cohort | Valid GLM 5-bit source proposals /8 | Correct proposals /8 | Learned holdout1 correct/8 | Learned holdout2 correct/8 |
| --- | ---: | ---: | ---: | ---: |
| 01 | 3/8 | 2/8 | 1/8 | 2/8 |
| 02 | 6/8 | 4/8 | 3/8 | 3/8 |
| 03 | 5/8 | 5/8 | 4/8 | 4/8 |
| **Total** | **14/24** | **11/24** | **8/24** | **9/24** |

### Full ITT holdout comparison

| Arm | Retention1 correct /24 | Retention2 correct /24 | Retention1 VALID /24 | Retention2 VALID /24 |
| --- | ---: | ---: | ---: | ---: |
| **Learned, verbatim GLM-authored 5-bit capsule** | **8/24 (33.3%)** | **9/24 (37.5%)** | 14/24 | 14/24 |
| Fresh, independent uniform random 5-bit capsule | 0/24 | 0/24 | 13/24 | 13/24 |
| Neutral, second independent uniform random 5-bit capsule | 1/24 (4.2%) | 1/24 (4.2%) | 13/24 | 14/24 |

**Source:** 24/24 requests physically reserved; **14 accepted five-letter policies** and **10 invalid_format**, not re-sent. Of 14 syntactically valid policies, **11 matched the private true 5-bit procedure** and **3 were wrong**. This is the first experiment in this line to explicitly keep model-authored but incorrect memory without automatic controller repair.

**Holdout:** 144 prescribed logical slots (72 per wave), 84 physical reservations (42 per wave), 60 prescribed not_sent because ten source contexts had no valid capsule. Retention1: 40 valid / 42 dispatched (two invalid); retention2: 41 valid / 42 dispatched (one invalid). Overall **168 prescribed logical slots**, **108 physical model request reservations**, **95 valid provider response outputs** (14 source + 81 holdout), **13 invalid_format responses** across phases, **60 not_sent holdout slots**. No ambiguous attempts were automatically retried. Reservations and model-reported usage do not independently attest vendor billing.

**Within-context Learned correctness changes across repeated waves:** correct in both = 8; lost by wave2 = 0; gained in wave2 = 1; incorrect/missing in both = 15. Same 24 contexts across two waves, NOT independent replications. Three model-authored valid but incorrect procedures remained wrong and were not secretly repaired, as prescribed. At least two execution misses occurred in wave2 despite source policies judged correct; source correctness does NOT mechanically force holdout correctness.

## Interpretation and what failed

The strong G1 result from earlier controller-inferred 3-step procedures did NOT generalize to near-perfect model-authored 5-step hypothesis induction. The main bottleneck is source **response validity (14/24)** and next source **semantic exactness (11/24)**. A downstream capsule cannot succeed if the model did not provide a valid and correct five-step program. Returned public summary records do not expose raw invalid text or finish reasons; therefore there is **no basis yet** to conclude that every invalid source attempt was a token-cap truncation versus an output-format problem. Future registered trials should record sanitized finish-reason and token metadata by source stage to diagnose this without releasing raw provider content.

The two task grammars are transparent and corrected final-output examples might make the five-step code easy to identify from a single example. Learned's advantage over equal-capacity uninformed capsules is descriptively real under this small sample, yet it does not prove harder general-purpose abstraction, durable model-internal learning, parameter updates, ability on unseen grammars, multi-day retention, fully matched compute or emergent autonomous institutions. There is no powered pre-registered hypothesis test; avoid confirmatory p-values. **scientific_acceptance=false** and PR #310 stays Draft. No Pattern Register promotion.

## Immutable evidence references

- Original sanitized cohort 01 GitHub artifact ID **12542117911** (g1-model-induced-five-01-20261024).
- Original sanitized cohort 02 GitHub artifact ID **12542527639** (g1-model-induced-five-02-20261024).
- Original sanitized cohort 03 GitHub artifact ID **12542876017** (g1-model-induced-five-03-20261024).
- All original artifacts were downloaded into a private local analysis runtime without changing their contents.
- An offline read-only auditor checks that all 8+24+24 logical slots, arm-level row grades, physical reservation counts, and paired contexts across retention waves reconcile. It never opens a provider connection and does not impose an external approval or operational bottleneck.

**Next internal experiment:** Use a newly sampled task set, higher generation budget and an appropriately tested GLM-5.3 reasoning effort (low vs high in distinct prospective arms, not as ad hoc repairs). Collect SANITIZED source finish_reason and token usage to isolate format/truncation from genuine inference errors, without retrying any prior physical send. A more demanding future experiment should hold the procedure grammar out entirely. Keep scientific acceptance false until stronger, independently seeded and causally credible evidence is obtained.
