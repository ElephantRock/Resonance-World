# G1 REAL agent experience-store transfer across process restart (2026-10-23)

**Actual GLM-5.3 (thinking enabled, reasoning_effort=low) provider experiment:** [GitHub Actions #39982949180](https://github.com/ElephantRock/Resonance-World/actions/runs/39982949180). Three real model cohorts, each in two separate Python processes (16 source actions, process termination, new Python interpreter rehydrating a private one-bit policy capsule, then 24 heldout actions). Distinct newly sampled context IDs and development/holdout operands were generated per run before the first source send. The user requested all work remain internal without an outside auditor or blocking approvals.

**Prospective frozen protocol:** G1_PERSISTENT_AGENT_REAL_PROSPECTIVE_20261023.md, committed and CI validated BEFORE dispatch. Executable: scripts/run_c3r_g1_persistent_experience_live.py; unit/negative tests: tests/test_c3r_g1_persistent_experience_live.py.

## Observed results (denominators fixed prior to outcomes)

| Cohort | Valid source | Learned correct/valid | Fresh correct/valid | Neutral correct/valid | Invalid holdout |
|---|---:|---:|---:|---:|---:|
| g1-agent-memory-20261023-1 | 16/16 | 8/8 | 3/7 | 3/8 | 1 |
| g1-agent-memory-20261023-2 | 16/16 | 7/7 | 3/7 | 3/8 | 2 |
| g1-agent-memory-20261023-3 | 16/16 | 8/8 | 4/8 | 1/8 | 0 |
| **Total** | **48/48** | **23/23** | **10/22** | **7/24** | **3** |

Holdout *intention-to-treat prescribed denominators* are **24 per arm**, including invalid responses. Thus Learned **23/24 = 95.8%**; Fresh **10/24 = 41.7%**; Neutral **7/24 = 29.2%**. Differences are **+54.2 percentage points** Learned–Fresh and **+66.7 points** Learned–Neutral. These are **descriptive**, not powered significance estimates.

There were **120 durably reserved provider request slots**, 48/48 successful source model responses and 69/72 accepted qualification responses. Three holdout responses were invalid-format (Fresh twice, Learned once), not silently removed or retried. All 24 newly generated context-level units had two valid development outcomes and were holdout-eligible. All three workflow jobs completed successfully.

Provider-reported holdout **completion** token totals: Learned **977**, Fresh **13,643**, Neutral **1,000**. The much larger Fresh value includes long/invalid generations and is **not** evidence of token-matched or equal-compute arms, nor an authenticated vendor invoice. The report holds cohort-level median latencies in the original JSON; pooled median latency cannot be reconstructed exactly from aggregated summary records.

## What G1 was actually tested

The model saw new public holdout operands but **did not receive source grades or its source transcript in any qualification prompt**. A small explicit agent-side reducer instead inferred a context's A/B bit from its two graded development actions, saved that bit to an owner-private persisted file, and a *separate new process* loaded it. This tests functioning **external agent experience memory across sessions**, not autonomous learned parameters or changes inside GLM.

The arms deliberately differ in capsule evidence: Learned receives the grade-inferred bit, Fresh receives unknown policy with predefined A fallback, Neutral receives an independently hashed pseudo-policy bit unrelated to private target assignment. The repeated public task **families** remain simple arithmetic/text transformation selectors. The result is consistent with effective re-use of stored relevant experience; it does not establish sophisticated general-purpose skill learning or unassisted institutional capability.

No exact matched per-context paired hypothesis test can be computed from the public *aggregate-only* artifacts, and no confirmatory p-value should be asserted. The placebo allocation is independent only by code/seed construction and may vary around 50%; the tiny and highly structured task family and the known-weak A fallback are confounds. The source grader and policy capsules occupy the same internal GitHub host; no external witness, timestamp or independent billing verification is claimed. The private manifest (hidden labels and task inputs) is deliberately absent from uploaded public artifacts. **scientific_acceptance=false**.

## Immutable artifact references (GitHub, 2026-10-23)

- Cohort 1 artifact ID **12514990430**, original ZIP SHA256 **2032430d5e0045dc70b38351339a575df628a6cee05d365dcbf181a8684a6dbd**.
- Cohort 2 artifact ID **12514381789**, original ZIP SHA256 **9f423f0ded827882097d6eb782da7c8969a893066f600fc935ab243f0e467d27**.
- Cohort 3 artifact ID **12514571847**, original ZIP SHA256 **1bf23938e31060ea7ae16100870998b791c6b9d7da67988a4f963d9dbdf6ce0d**.

All original redacted source/holdout reports were retained unchanged. The local combined public analysis JSON SHA256 **3ad952a8cfdd19a72f6ee7e62b47eae9c8af088a2336e051b5522a3387ed8f89**; evidence ZIP SHA256 **3cb17ab6196cc3ab11e07e7df01c46c49e0981cff47d3d3072ba3fea5985b129**. PR #310 remains Draft and no Pattern Register entry is promoted.

## Next scientific falsification, no external bottlenecks

Test retention over several chronological intervals and task changes, stronger matched-capacity random/shuffled-policy capsules, tasks requiring *multi-step* learned procedures rather than a deterministic one-bit reduction, matched token/compute exposure, and preregistered per-context paired outcomes. Run multiple fresh contexts/seeds and publish the failure/denominator ledger as well as successes. Keep scientific acceptance false until a causal design actually distinguishes acquisition from deterministic storage/retrieval.
