# D2 General API Hardened Transport Requalification

## Status and purpose

This is a fresh **engineering-only** requalification of the hardened General API transport integrated by PR #203. It exists because the historical issue #202 preflight was executed before redirect-following was disabled and therefore could establish only response-level properties, not one-physical-request-per-probe transport qualification.

The historical result, artifact, and closeout remain immutable. This stream does not rerun or replace them and does not raise their claim ceiling.

This is not a D2d rerun, not a D2c repair, not a source-capability-acquisition study, and not Mechanism Registry evidence. Production/default Historical Substrate remains **OFF**.

## Historical boundary being repaired prospectively

Historical preflight:

- issue: `#202`
- PR: `#203`
- authoritative workflow: `33992155068`, attempt 1
- artifact id: `9976954042`
- artifact digest: `sha256:4ce006afc0397847709f41100a291ae5ccf2a2637096afe15589e85e9e1ae665`
- result-file SHA-256: `607994b0e3679fa65ec89150cf58d09b1e560156dcf8009af499463004082a2f`
- durable status: `completed_response_level_pass_redirect_unverified`

The historical stream remains `redirect_history_verified=false`, `one_physical_request_per_probe_verified=false`, and `transport_qualified_for_future_prospective_design=false`.

## Provider contract under fresh qualification

- provider: Z.AI
- endpoint: `https://api.z.ai/api/paas/v4/chat/completions`
- requested model: `glm-5-turbo`
- temperature: `0.8`
- thinking: disabled
- stream: false
- max tokens: 256
- exactly three fixed probes
- exactly one initiated HTTPS attempt per probe
- no retries
- redirects are rejected and never followed
- absolute response-body read deadline
- strict standards-compliant JSON parsing

The three probe bodies are intentionally the same bounded engineering shapes as the historical stream so the new evidence isolates the hardened transport path rather than changing the application contract.

## Fixed probes

1. `general_minimal_text` — non-empty text and exact model identity.
2. `general_minimal_json` — non-empty valid JSON object and exact model identity.
3. `general_d2_shape_json` — non-empty valid JSON object with exactly 8 legal actions and exact model identity.

The D2-shaped probe is transport-shape validation only. It carries no hidden policy, outcome-bearing experience, evaluation labels, or scientific scoring.

## Fresh transport-verification rule

For every probe the executed wrapper must record:

- initiated physical HTTPS attempt count;
- redirect-following disabled;
- redirects followed = 0;
- returned HTTP status;
- base response-contract validation;
- credential-safe bounded diagnostics.

`one_physical_request_per_probe_verified=true` requires exactly one initiated HTTPS attempt for every probe.

`redirect_history_verified=true` requires that every probe executed through the no-redirect opener, followed zero redirects, and satisfied one-attempt accounting. A surfaced 3xx response is a failed probe, not a redirect to follow.

The fresh transport qualifies only if all three probes:

- record exactly one initiated physical attempt;
- follow zero redirects;
- reach HTTP 200;
- return exact model `glm-5-turbo`;
- satisfy their content/JSON/action-shape contracts.

## Durable diagnostics

Raw credentials are never persisted. Raw provider error messages are never persisted. Response content is validated in memory but only bounded hashes/lengths and structural diagnostics are recorded.

The result is engineering evidence only. Even a clean qualification does not authorize a scientific source-acquisition campaign.

## Authorization boundary

Issue #206 authorizes construction, deterministic materialization, zero-provider tests/CI, exact-candidate freeze, and review only.

**No provider execution is authorized by this plan.** After the exact candidate is frozen and zero-provider gates pass, a separate explicit human authorization naming that exact candidate is required. The only permitted post-freeze mutation would then be a sole-child marker at `research/d2_general_api_requalification/RUN_D2_GENERAL_API_REQUALIFICATION`.

## Prohibitions

- no rerun of D2d workflow `33701860334`;
- no rerun/replacement of the historical issue #202 preflight;
- no scientific Field trajectory or capability scoring;
- no adaptive request count or retries;
- no registry mutation or Acceptance-plane promotion;
- no Historical Substrate activation;
- no provider call before separate exact-candidate authorization.
