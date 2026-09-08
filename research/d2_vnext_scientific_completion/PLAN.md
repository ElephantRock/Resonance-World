# D2-vNext scientific-call / trajectory completion qualification

Issue: #223

This is a fresh **engineering-only** qualification after D2-vNext-S1. It does not
rerun S1, does not generate source-acquisition evidence, and does not score any
provider action against hidden scientific truth.

## Fixed substrate

- Z.AI GLM Coding Plan
- Coding endpoint `https://api.z.ai/api/coding/paas/v4`
- Hermes `0.8.0` at `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- pinned `run_agent.py` blob `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- OpenAI SDK `2.21.0`
- httpx `0.28.1`
- provider `zai`, API mode `chat_completions`
- requested model `glm-5.3`
- temperature `0.8`
- `thinking.type=disabled`
- no tools, memory/context files, persistent session, fallback provider/model, or General API fallback

Effective upstream model identity is not inferred if the supported Hermes boundary
does not expose it.

## Stage 1 — fixed completion ladder

All profiles execute, each with the four frozen D2-shaped non-scientific call
shapes:

1. `fresh_evaluation`
2. `developed_development`
3. `developed_evaluation`
4. `oracle_evaluation`

Profiles, in fixed order:

1. `iterations2_tokens768`
2. `iterations2_tokens1024`
3. `iterations3_tokens1024`

The selected envelope is the first profile in that order for which all four calls
complete with valid eight-action JSON under the profile's API-call bound. Later
profiles still execute for bounded diagnostics.

## Stage 2 — fixed trajectory topology

If a profile is selected, run four independent schema-like engineering trajectories.
Each has exactly the D2-vNext-S1 logical-call topology:

- fresh: 4
- developed-40: 5 development + 4 evaluation = 9
- developed-80: 10 development + 4 evaluation = 14
- developed-160: 20 development + 4 evaluation = 24
- oracle-shaped: 4
- total: 55 calls

Four trajectories therefore register 220 logical calls. They execute concurrently with a
fixed maximum concurrency of 4, matching the predecessor campaign's registered campaign-scale
parallelism while retaining one process-wide physical-send guard. Together with the 12
Stage-1 calls, the maximum registered topology is 232 logical calls.

Prompts use deterministic synthetic cases and synthetic feedback only. Returned
strategy text may be carried forward to reproduce prompt-state evolution. No hidden
scientific policy is used, no correctness comparison is made, and no efficacy score
or estimand is computed.

## Physical-send guard

- maximum theoretical per-logical-call bound: 54 physical sends
- hard campaign-wide bound: 400 physical sends
- the 401st provider send is blocked before transmission
- any non-Coding-Plan outbound HTTP request is blocked before transmission
- no replacement call/trajectory after failure
- workflow reruns are prohibited

The 400-send global ceiling intentionally prevents the full retry envelope from
multiplying across the trajectory assay.

## Persisted diagnostics

Persist bounded metadata only: completion flags, API-call counts, prompt/response
lengths and SHA-256 values, strategy length/hash, HTTP status, transport error type,
bounded provider status/code metadata, supported-boundary finish/stop reason when
directly exposed, and physical-send accounting.

Raw credentials, raw provider response bodies, raw provider error bodies, and raw
provider error messages are not persisted.

## Pass condition and claim ceiling

Qualification passes only if a Stage-1 profile is selected and all four Stage-2
trajectories complete 55/55 calls with no outbound/budget integrity defect and no
more than 400 physical sends.

A pass establishes only an engineering completion envelope suitable for constructing
a later **fresh** D2-vNext source-acquisition campaign. It does not establish source
development, capability acquisition, schema generalization, D2e readiness,
Mechanism Registry evidence, Acceptance authority, or Historical Substrate validity.

## Governance

Construction, deterministic materialization, tests, credential-free preexecution,
and review are autonomous. Provider/model execution requires a separate explicit
authorization naming the exact frozen candidate and covering at most 400 physical
provider sends in one workflow attempt. No rerun is authorized.

Evidence merge, scientific campaign execution, registry/Acceptance action, D2e,
Historical Substrate activation, deployment, publication, credential changes, and
material spend are separate authorities.
