# D2d provider/runtime engineering diagnosis

This stream is engineering-only. It follows the completed D2d `D2d-A0` campaign and cannot repair, rerun, replace, or reinterpret workflow `33701860334`.

## Objective

Determine whether a future provider call failure occurs at the endpoint/account layer, during structured-output handling, or only for the D2d-shaped request payload.

## Frozen diagnostic matrix

The probe contains exactly three single-attempt requests to the same frozen Z.AI Coding endpoint and model:

1. `minimal_json` — minimal neutral prompt, JSON response mode.
2. `d2d_shape_json` — D2d-shaped eight-action prompt, JSON response mode.
3. `d2d_shape_text` — the same D2d-shaped prompt with plain-text response mode.

All requests use `glm-5-turbo`, temperature `0.8`, thinking disabled, synchronous output, and no retry. The probe does not execute a scientific Field trajectory, does not score actions, and cannot create replacement D2d data.

## Interpretation

- If all three fail before a successful HTTP/model response, the leading class is endpoint/account/provider transport.
- If `minimal_json` succeeds while `d2d_shape_json` fails, the leading class is payload/prompt-specific.
- If `d2d_shape_text` succeeds while `d2d_shape_json` fails, structured JSON mode is implicated.
- A provider HTTP 5xx is recorded as a transport/server failure, not retried.
- A successful HTTP response that fails response parsing/validation is recorded separately from HTTP failure.

The probe records only bounded diagnostics: HTTP status, provider error code when structurally available, hashes and lengths of provider messages/bodies/content, response parsing stage, and model name. It never records the API key.

## Authorization

Issue #200 authorizes construction, tests, zero-provider CI, and exact-candidate freeze only. Provider execution is **not authorized** by this plan.

A future execution requires a separate explicit authorization naming the exact frozen diagnostic candidate. Only then may `research/d2d_diag/RUN_D2D_PROVIDER_DIAGNOSTIC` be created as the sole child diff from that candidate.

No D2d rerun, no scientific replacement data, no registry mutation, and no Historical Substrate activation are permitted. Historical Substrate remains **OFF**.
