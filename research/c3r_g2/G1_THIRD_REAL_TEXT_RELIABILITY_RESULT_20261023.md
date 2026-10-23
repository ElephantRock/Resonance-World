# G1 — Third REAL GLM-5.3 Text Reliability Trial (2026-10-23)

**Empirical evidence, not offline simulation.** GitHub Actions run [39937406266](https://github.com/ElephantRock/Resonance-World/actions/runs/39937406266) completed successfully. Artifact: `g1-text-reliability-real-20261023` (ID **12495645624**), downloaded ZIP SHA256 **8f4fd3fedcaffd6d9b48b48319c7676f9a71bc8b1b998cdf10a6a6795c18110d**, internal JSON SHA256 **59f75278bce1884723430a62b4ac971a0a485c289e814470cd14eec0d6538aab**. Execution run ID: `g1-text-reliability-20261023-03`.

## Fixed 40-attempt logical denominator

Only the text family was enabled, so all 20 arithmetic rows remain prescribed but **not sent by design**.

| Family/stage | Accepted | TimeoutError | Not sent | Logical denominator |
|---|---:|---:|---:|---:|
| Text development | 8 | 0 | 0 | 8 |
| Text qualification | 4 | 8 | 0 | 12 |
| Arithmetic development + qualification | 0 | 0 | 20 | 20 |
| **Total** | **12** | **8** | **20** | **40** |

Exactly **20 physical send reservations**; this is not vendor-authenticated billing. All four text context-level units had two accepted development grades, so all four qualified for holdout. All four **Learned** arms returned a valid, internally graded correct answer (**4/4**); all four **Fresh** and all four **Neutral** requests ended in **TimeoutError** without an A/B answer (**0/4 valid for both**). Failure codes were recorded from the local transport ledger, with no provider HTTP status or raw error body available for any timeout. This means control *accuracy cannot be estimated*, and 4/4 vs 0/4 is **not** an identified causal treatment contrast.

Provider usage reported on the twelve completed responses (missing errors excluded):
- Source: 1,354 prompt tokens, 11,394 completion tokens, 11,366 reasoning tokens within completion.
- Holdout: 775 prompt tokens, 682 completion tokens, 665 reasoning tokens within completion.
- **Observed total:** 2,129 prompt tokens, 12,076 completion tokens, including 12,031 reported reasoning tokens. This is a lower bound on observed requests with token metadata, **not a billing total**.

The most important new signal is **arm-confounded availability of valid model answers**. The observed difference is answer validity/latency, not proven correct-answer learning: the controls repeatedly run until their 180-second timeout because no graded evidence identifies the randomly assigned hidden A/B target. The Learneds generally have enough source evidence to terminate quickly. This explanation is a plausible mechanism, **not independently demonstrated from provider internals**.

## Next genuine empirical test

For a new run ID, test all three arms using **GLM-5.2** with `thinking.type=disabled` applied **uniformly** to each source and holdout request. GLM-5.3 explicitly does not support disabling reasoning ([official Z.AI API changes](https://z.ai/blog/glm-5.3)). A different model is a **separate technical/research condition**, not a repair or automatic continuation of GLM-5.3 observations. Keep the 40-slot frozen plan, no retries, one-shot reservation journal, internal source checkpoint, and the same arms; compare valid-answer completeness before any correctness contrasts. No scientific acceptance or independent persistent memory claim.

This trial is a run-specific operational probe on the repeated frozen public tasks; task independence/novelty is not claimed. No independent/outside auditor is requested.
