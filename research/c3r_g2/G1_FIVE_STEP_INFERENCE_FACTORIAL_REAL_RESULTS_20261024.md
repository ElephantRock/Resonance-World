# G1 five-step GLM source induction: REAL effort x generation-cap factorial — 2026-10-24

Actual completed experiment: https://github.com/ElephantRock/Resonance-World/actions/runs/40053408070. The 3 GitHub matrix jobs succeeded. This is **source policy induction only**, not cross-session agent memory or general G1 scientific acceptance. Model requested GLM-5.3 Coding, thinking.type=enabled. The four configurations were low/high reasoning effort crossed with 4096/8192 generation token limits.

**Frozen before experiment:** research/c3r_g2/G1_FIVE_STEP_INFERENCE_FACTORIAL_PROSPECTIVE_20261024.md. Every one of 24 unique context units (three groups of 8, balanced arithmetic/text) saw exactly the SAME two corrected input/output training examples and identical prompt in all four arms. The 96 logical model sends were all physically reserved and completed; none was retried. There were **24 paired contexts**, not 96 independent contexts.

## All observed outcomes (each condition 24 prescribed source attempts)

| Requested condition | Valid exact 5-letter source outputs | Correct hidden 5-bit program | Length exhausted | Finished stop but invalid format | Valid but wrong | Provider reported completion tokens | Median latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Low/4096 | 7/24 | 6/24 | 13 | 4 | 1 | 60,717 | 36.23s |
| Low/8192 | 9/24 | 5/24 | 8 | 7 | 4 | 76,873 | 14.66s |
| **High/4096** | **24/24** | **21/24** | **0** | **0** | 3 | **16,595** | **10.55s** |
| High/8192 | 23/24 | 20/24 | 0 | 1 | 3 | 13,460 | 9.98s |

Provider-reported prompt token sum: **5,289 for every condition**, consistent with the paired identical input prompts. Arithmetic/text exact correctness separately: Low/4096 4/12 and 2/12; Low/8192 3/12 and 2/12; High/4096 9/12 and 12/12; High/8192 10/12 and 10/12.

Cohort-level correct policy counts High/4096 were 5/8, 8/8, 8/8; Low/4096 were 0/8, 4/8, 2/8. This heterogeneity is preserved.

**Matched within-context High/4096 vs Low/4096:** 15 contexts improved from incorrect to correct, 0 worsened, 6 were correct under both, and 3 incorrect under both. Descriptive correctness difference: **+62.5 percentage points**. High/4096 used around **72.7% fewer reported completion tokens** than Low/4096, with a substantially lower observed median request latency. This is not a vendor billing report or a proof about server compute.

**More tokens did not reliably help:** Raising Low's max_tokens to 8192 reduced finish_reason=length from 13 to 8, but increased stop-terminated invalid-format outputs (4 to 7) and valid-wrong programs (1 to 4). The number of correct source hypotheses was 5 rather than 6. Under high effort, 8192 produced 20 correct compared with 21 at 4096. The evidence for these task families favors **High/4096 as the next source-induction operating setting**, conditional on replication with novel task grammars; not a global GLM default.

## Research interpretation and security boundary

The previous real GLM-authored five-step experiment recorded 14/24 valid and 11/24 correct source policies, but not a sanitized source finish reason. This new factorial isolated **length_exhausted**, **invalid_format after stop**, **valid_wrong**, **valid_correct**, and **provider_error**. Within the Low configuration, long outputs exhausting the generation cap were a key operational failure mode. The target hidden program and raw model output were not exposed publicly.

There are important limitations: within-context send order was not block-randomized, three cohorts are small, the 2 public arithmetic/text procedure grammars are deliberately transparent, and Z.AI's low/high values are requested settings rather than independently measured compute. Never treat repeated measurements on the same context as independent draws. Descriptive differences do not constitute preregistered confirmatory causal proof, independent model weight learning, real agent-memory transfer, or organizational/institutional regeneration.

All work and methodological validation remained internal. There was no external auditor, outside custodian or serial science approval bottleneck. Provider tokens are reported metadata, not reconciled billing. **scientific_acceptance=false**. PR #310 remains Draft/unmerged, and Pattern Register is unchanged.

## Evidence & reproducibility

- Exact source: scripts/run_c3r_g1_five_step_factorial_diagnostic.py
- Tests: tests/test_c3r_g1_five_step_factorial_diagnostic.py (CI #40053299215: 930 passed, 4 skipped, Ruff and compatibility green, Architecture Audit #40053299212 green).
- Real GitHub artifacts: cohort 01 ID **12544785915**, SHA256 **f634c1dd10913823079d1d41165bb6d33d536dd860306659070d86155ec26b83**; cohort 02 ID **12544019832**, SHA256 **a94ca8351aacf6bc0d4f59fb80d1e8006aa10fedba7c31971624e14dfa9d43be**; cohort 03 ID **12543978539**, SHA256 **00d3bc512b1f6897bbbb277adb74385f7bccccee709fdd8cee8728771d2258fa**.
- Derived exact-matched-24-context redacted JSON SHA256 **5fd0f5e19f49de0a1fd9a0ad43344bdfd678ea7dc5693b5f6eabdc53faf981b5**.
- Internal original-archives + read-only analyzer + JSON + narrative evidence ZIP SHA256 **0828754554de15099a114365ed1f682fb2b0b99ec11ccaa3096ff8a4c86ec6df**. Private prompts, hidden targets, raw completions, credentials and provider error bodies were not uploaded.

## Next predeclared discriminating G1 test

For NEW procedural grammars and context samples, evaluate High/4096 source hypotheses against no-memory and independent equal-capacity randomized controls on NEW holdout inputs after separate process sessions. Distinguish whether GLM's original five-bit source proposal was right from whether holdout execution succeeded. Do not promote a Pattern Register entry until persistent agent acquisition/generalization earns scientific support.
