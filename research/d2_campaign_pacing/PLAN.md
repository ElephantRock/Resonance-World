# D2 campaign-scale transport pacing qualification

Status: prospective engineering construction; provider execution unauthorized.

Issue: #210

## Scope

This stream diagnoses the operational dependency exposed by D2d-S2: the hardened Z.AI General API transport passed bounded requalification, but the one-shot D2d-S2 scientific campaign produced terminal HTTP 429 failures for all 384 attempted pairs. This stream is engineering-only. It does not rerun D2d-S2, does not generate source-acquisition evidence, does not mutate the Mechanism Registry, and does not activate Historical Substrate.

The provider-side policy cause of HTTP 429 is not assumed. The historical launch used up to four parallel shard jobs, each with its own client-local 0.35 s minimum interval. That historical burst schedule is not equivalent to, and is not reproduced by, the globally gated profiles below.

## Fixed transport contract

- endpoint: `https://api.z.ai/api/paas/v4/chat/completions`
- exact model: `glm-5-turbo`
- `thinking.type=disabled`
- `temperature=0.8`
- `max_tokens=768`
- JSON-object response requesting exactly 8 actions from `KAPPA`, `MICA`, `ORBIT`, `VELA`
- redirects rejected
- explicit HTTP 200 required
- strict JSON validation
- one initiated physical HTTPS attempt per logical probe
- no retry
- 90 s connect/open timeout and 90 s bounded body-read deadline
- raw credentials and raw provider response/error bodies are never persisted

The engineering request uses deterministic synthetic cases, synthetic bounded feedback, and a synthetic strategy string. It is intentionally not a registered scientific task instance and is never scientifically scored.

## Frozen pacing profiles

Profiles execute in this order and all are bounded diagnostics. **Each profile uses one global request-start gate**, even when more than one request may be in flight.

| profile | calls | max concurrency | global minimum request-start interval |
| --- | ---: | ---: | ---: |
| `baseline_serial_5s` | 3 | 1 | 5.00 s |
| `serial_2s` | 6 | 1 | 2.00 s |
| `serial_1s` | 6 | 1 | 1.00 s |
| `concurrency2_1s` | 8 | 2 | 1.00 s |
| `concurrency4_035s` | 8 | 4 | 0.35 s |

Maximum provider calls: **31**. No profile retries failed calls.

`concurrency4_035s` is a bounded high-intensity globally gated diagnostic for a candidate future scheduler. It does **not** recreate D2d-S2's failed four-independent-client burst schedule and therefore cannot establish that the historical schedule itself has become safe.

A profile passes only when every call returns HTTP 200, exact model identity, valid D2-shaped JSON, exactly one initiated physical attempt, and no redirect. HTTP 429 is always a profile failure.

The recommended campaign profile is the most intense contiguous passing profile before the first failed profile. If the baseline fails, the recommendation is `null`. Later profiles still execute as bounded diagnostics, but a later isolated pass cannot leapfrog an earlier failure for qualification.

## Result authority

The result may establish only a bounded engineering statement about the tested globally gated pacing profiles under the exact candidate and provider/account context at execution time. It does not establish provider policy, future unlimited quota, the safety of the historical failed burst schedule, scientific efficacy, source capability acquisition, schema generalization, production readiness, or any registry/Acceptance claim.

## Authorization

The frozen construction candidate must not contain `research/d2_campaign_pacing/RUN_D2_CAMPAIGN_PACING_QUALIFICATION`.

Provider execution requires a later explicit authorization naming the exact frozen candidate. The marker must then be introduced as the sole child of that candidate with exactly:

```text
candidate_sha=<40-lowercase-hex-frozen-candidate>
issue=210
authorization=D2_campaign_pacing_execution_explicitly_authorized
```

The execution workflow is one-shot: GitHub Actions reruns are prohibited. A failed qualification is preserved as evidence; it is not retried under the same frozen request stream.

## Governance

- engineering only
- external discretionary spend remains unauthorized until explicit exact-candidate execution authorization
- no D2d-S2 rerun or failed-unit replacement
- no scientific campaign authorization
- no registry promotion or Acceptance-plane action
- no Historical Substrate activation
- production/default Historical Substrate remains OFF
