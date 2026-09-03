# D2d Provider/Runtime Diagnostic Closeout

## Status

Completed engineering-only diagnostic. This is not scientific evidence and does not alter the completed D2d `D2d-A0` classification.

Production/default Historical Substrate remains **OFF**.

## Frozen authorization

- diagnostic candidate: `82d8c1b166234c18b89e7642bf5cf18d806dbf70`
- authorization commit: `3e23514c3ba247c5bc0a0f9893d5970bc3f73ce8`
- authorization issue: `#200`
- workflow: `33773673338`
- run attempt: `1`
- workflow conclusion: `success`
- result artifact: `9900677976`
- artifact digest: `sha256:e57e126560abbbb3a745059a042d4f31abcfd9b09cbc58424c2450e265c8bde2`
- canonical result file SHA-256: `be0d59cd98a821b4ceb7fd03545b04d0c3f6e79219383abf590cb903ec3fb4a9`

Authorization integrity passed and the authorization commit is exactly one child of the frozen candidate with only `research/d2d_diag/RUN_D2D_PROVIDER_DIAGNOSTIC` added.

## Diagnostic results

All three fixed one-shot probes reached HTTP 200. No retry was permitted or performed.

| Probe | HTTP | Returned model | Content result |
| --- | ---: | --- | --- |
| `minimal_json` | 200 | `glm-5.3-flash` | non-empty JSON; valid 8-action shape |
| `d2d_shape_json` | 200 | `glm-5.3-flash` | empty content; JSON invalid |
| `d2d_shape_text` | 200 | `glm-5.3-flash` | non-empty text |

The requested model in every probe was `glm-5-turbo`. The Coding endpoint therefore did not satisfy the frozen model-identity contract at diagnostic time: every successful response reported `glm-5.3-flash`.

The realistic D2d-shaped request also exposed a second independent incompatibility with the frozen structured-output assumption: under `response_format={"type":"json_object"}`, the returned content was empty even though the outer request completed with HTTP 200.

## Engineering interpretation

The diagnostic disproves a universal transport or credential-denial explanation at diagnostic time: the same account, endpoint family, and direct GitHub Actions workload successfully reached the provider and received HTTP 200 responses.

It establishes a concrete **model-routing incompatibility** with the frozen D2d client. The frozen D2d transport checks `outer.model == "glm-5-turbo"` before accepting a logical call. A response identifying itself as `glm-5.3-flash` therefore deterministically fails the frozen client as `model_drift:glm-5.3-flash`, even when the provider otherwise returns valid content.

It also establishes a concrete **structured-output incompatibility** for a realistic D2d-shaped request at diagnostic time: the JSON-mode probe returned empty content and would fail downstream JSON parsing even if model-identity enforcement were removed.

These findings are highly consistent with the completed D2d pattern of zero validated logical calls. They do **not** retrospectively prove the exact mechanism of every historical D2d pair failure because the D2d campaign intentionally did not preserve raw provider error bodies and provider routing can change over time. In particular, the preserved D2d campaign also contains a minority HTTP-500 terminal fingerprint, so the historical stream may have involved mixed failure modes.

## Provider documentation relevance

Current Z.AI documentation distinguishes the GLM Coding Plan endpoint from the General API endpoint and states that the Coding endpoint is intended for supported coding tools, while other/direct application use should use the General API. Current GLM-5-Turbo documentation shows `glm-5-turbo` requests against the General API endpoint.

Therefore any future fresh scientific source-acquisition campaign should be constructed prospectively around the General API transport (or another explicitly supported transport) and should include an engineering preflight that verifies exact model identity and structured-output behavior **before** freezing or authorizing the scientific campaign.

This recommendation is prospective only. It does not authorize any new provider call or scientific campaign.

## Scientific boundary

- no D2d rerun
- no failed-pair replacement
- no adaptive-N rescue
- no reinterpretation of `D2d-A0`
- no source-acquisition conclusion from D2d
- no Mechanism Registry mutation
- no Acceptance-plane promotion
- no Historical Substrate activation

A future source-acquisition study must be a new prospectively frozen campaign with new execution authority. It must not be represented as a rerun or repair of D2d workflow `33701860334`.
