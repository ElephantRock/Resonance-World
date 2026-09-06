# D2 General API Transport Qualification Preflight

## Status and purpose

This is an engineering-only preflight for a future fresh D2 source-capability-acquisition study. It follows the completed D2d `D2d-A0` apparatus failure and the bounded provider/runtime diagnosis that observed Coding-route model remapping and structured-output incompatibility.

It is not a D2d rerun, repair, replacement, scientific continuation, or source-acquisition study. It produces no Field trajectories, capability scores, reproduction evidence, registry evidence, or Acceptance-plane evidence.

Production/default Historical Substrate remains **OFF**.

## Provider contract under qualification

- provider: Z.AI
- endpoint: `https://api.z.ai/api/paas/v4/chat/completions`
- requested model: `glm-5-turbo`
- temperature: `0.8`
- thinking: disabled
- stream: false
- max tokens: 256
- exactly one physical attempt per request
- no retries

The endpoint intentionally differs from the completed D2d Coding route `https://api.z.ai/api/coding/paas/v4/chat/completions`.

## Fixed probe matrix

Exactly three requests are materialized:

1. `general_minimal_text` — minimal text completion and exact-model check.
2. `general_minimal_json` — minimal JSON-object completion and exact-model/JSON check.
3. `general_d2_shape_json` — realistic D2-shaped 8-action JSON completion and exact-model/JSON/action-shape check.

The D2-shaped request is an engineering transport-shape probe only. It supplies no hidden policy, no outcome-bearing history, no evaluation labels, and no scientific scoring.

## Qualification rule

Each request must reach HTTP 200 and return exact model identity `glm-5-turbo`.

- text probe: non-empty content.
- minimal JSON probe: non-empty valid JSON object.
- D2-shaped JSON probe: non-empty valid JSON object containing exactly 8 actions from `KAPPA`, `MICA`, `ORBIT`, `VELA`.

The engineering preflight qualifies only if all three fixed probes pass their contract. A successful preflight still does not authorize or scientifically validate any later campaign.

## Durable diagnostics

The execution result may preserve only bounded metadata:

- HTTP status;
- returned model and exact-model-match boolean;
- body/content length and SHA-256;
- JSON/action-shape validation booleans;
- latency;
- sanitized provider code and provider-message length/SHA-256 when structurally available.

Raw credentials are never persisted. Raw provider error messages are never persisted. Response content is validated in memory but not stored in the result artifact.

## Authorization boundary

Issue #202 authorizes construction, deterministic materialization, tests, zero-provider CI, and an exact-candidate freeze only.

**Provider execution is not authorized by the scientific candidate.** After a candidate is frozen, a separate explicit authorization naming that exact candidate is required. The only authorized post-freeze mutation would then be a sole-child `research/d2_general_api_preflight/RUN_D2_GENERAL_API_PREFLIGHT` marker commit.

A successful provider preflight would only permit construction of a separate fresh scientific source-acquisition candidate. That future study must receive its own prospective freeze and its own provider-execution authorization.

## Prohibitions

- no rerun of D2d workflow `33701860334`;
- no D2d shard/job rerun or failed-pair replacement;
- no scientific Field trajectory or capability scoring;
- no adaptive N or outcome-based redesign;
- no registry mutation;
- no Acceptance-plane promotion;
- no Historical Substrate activation;
- no provider call before separate exact-candidate authorization.
