# First live GLM-5.3 G1 exploratory comparison — 2026-10-22

**Evidence status:** REAL provider-attempted model-run diagnostic, complete and **exploratory only**. This is the first complete learned-vs-fresh paired comparison from the C3R G1 thread; **not** powered G1 acceptance or persistent autonomous agent learning.

## Provenance

- GitHub Actions: https://github.com/ElephantRock/Resonance-World/actions/runs/39780461001
- Re-run job (one manual re-run, attempt 2): `119830461561`.
- Research commit checked out in experiment: `d9a369a48b344676d89ddf7099f7ea37eaa0adcd`.
- Sanitized, immutable-for-this-run GitHub Actions artifact name: `c3r-g1-first-real-glm53-once`; artifact ID `12426073768`, ZIP SHA256 `7d3af17ae1cd8e2a819cab9b5598e81df05043cba90cdd992b87d9b5d38a8998`. GitHub retention currently 14 days; **not independent WORM custody**.
- Public task cohort SHA256: `81ca66b83f44332c3a16e41cd7157cdfe5ea210c0b28b0cdf85b955695311ad1`.
- Provider route: Z.AI **coding** endpoint as configured by the existing `ZaiStandardModelPort`, model ID `glm-5.3`. Output ceiling 16,384 tokens per request, fixed `reasoning_effort=low`, 180-second per-request timeout, maximum **8** physical reservations, no automatic retries.
- GitHub Actions job successfully completed with a sanitized output JSON artifact; the earlier GitHub run attempt 1 deliberately failed before ever reading the secret or attempting network calls.
- The temporary one-shot workflow file was **deleted from the branch** after the run to avoid further live re-execution. PR #310 remains Draft.

## Measured results

| Stage | Number planned | Accepted A/B | Correct | Observed choices |
| --- | ---: | ---: | ---: | --- |
| Development with grader feedback | 4 | 4 | 3 | A, B, B, B |
| Qualification **learned** (development history in new prompts) | 2 | 2 | **2** | B, B |
| Qualification **fresh** (no development history) | 2 | 2 | **0** | A, A |
| **Total** | **8** | **8** | **5** | |

**2/2** matched learned/fresh qualifications were analyzable. Observed accuracy difference: **+100 percentage points** (2/2 vs 0/2). This sample is FAR too small to support statistical generalization or an acceptance criterion.

All eight local transport entries recorded `http_status=200`, `failure_class=null`; each observation recorded model ID `glm-5.3`, exact accepted A/B output and `finish_reason=stop`. Request digests and HTTP classifications are produced **locally**, not cross-checked with Z.AI backend request IDs or provider invoice.

The fixed local target ordering was **B = multiply, then add** for this one context. For the two new qualification tasks:

| Qualification task | Public operands (value, offset, factor) | A=(value+offset)*factor | B=value*factor+offset | Learned | Fresh |
| --- | --- | ---: | ---: | --- | --- |
| holdout-0 | (17, 7, 5) | 120 | **92** | B (correct) | A (wrong) |
| holdout-1 | (5, 3, 3) | 24 | **18** | B (correct) | A (wrong) |

Output choices were independently reconstructed from the locally saved SHA256 hashes of `A` and `B`, rather than guessed from aggregate success counts.

## Generation usage reveals earlier experiment bottleneck

| Stage | Completion tokens reported | Reasoning tokens reported |
| --- | ---: | ---: |
| Development | 49 | 36 |
| Qualification learned | 6 | 0 |
| Qualification fresh | 536 | 528 |
| **Total** | **591** | **564** |

One fresh qualification consumed **519 completion tokens**, including **516 reasoning tokens**, and still returned A with `finish_reason=stop`. The old **512-token maximum would have been insufficient for that request**. This directly validates removing the arbitrary 512-token apparatus cap for GLM-5.3; it does not prove 16,384 is optimal. Tokens are **API-reported**, not independently billed.

## Interpretation / nonclaims

This run supports a limited observation: **including four prior graded attempts in an otherwise similar qualification prompt was associated with a different A/B behavior and better accuracy for two held-out operand sets in one fixed context**. The learned arm switched to the correct B after source feedback; fresh consistently returned A.

This **does not yet prove persistent acquired capability by an autonomous agent**, because development feedback was transmitted in prompt context across model calls, not stored in a separate enduring model or validated independent agent state. There is only **one context and one arithmetic task family**, the correct choice is always B (not counterbalanced), only two evaluation pairs, one local evaluator, no placebo or sham arm in the run, no independent replication and no masked external outcome owner. Any generalization to G1's Models → Agents transition remains unproven.

The actual provider account, endpoint entitlement, exact vendor-side billed count and monetary cost were not independently attested. This was a deliberately bounded exploratory pilot, **not** scientific acceptance and not a reason to merge PR #310, alter frozen D2/W/H/C3R nulls, or promote the Architecture Pattern Register.

## Next empirical action

Do not build additional witness/storage/CI frameworks first. Next experiment, only after a separate authorized physical-send/cost envelope, should **counterbalance A/B truth across contexts** and repeat with independent learner instances, new arithmetic/text task families and at least learned/fresh/placebo arms. Preserve this pilot and its negative controls before changing hypotheses. No additional Z.AI requests are authorized by the completed eight-request run.
