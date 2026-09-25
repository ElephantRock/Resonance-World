# D2-vNext-Q3-D3 construction status

Status: **fresh execution envelope frozen; marker absent; provider execution unauthorized**.

Construction issue: `#304`. Freeze issue: `#306`.

Q3-D3 is a diagnostic-only successor to the consumed Q3-D2 stream. It observes the response bytes after HTTPX reading/content decoding but before OpenAI SDK JSON/object decoding, while preserving the already-qualified Q3-D2 request-scoped semantic observer and all Q2 behavioral semantics.

## Frozen diagnostic envelope

- namespace: `rw.d2-vnext-q3d3-http-sdk-boundary-diagnostic.v1`
- schema: `pairwise_order` only
- fresh pair count: `8`
- seed base: `17,000,000`, step `100`
- cohort commitment: `648884eaaf39dda5f37ee03a75ba030308e631ba8b51e536255418efa48af661`
- predecessor seed overlap: zero through Q3-D2
- 2 shards × 4 pairs
- provider-local concurrency: 1
- workflow max parallel: 2
- maximum registered logical calls/shard: 220
- maximum physical sends/logical call: 36
- maximum physical sends/shard: 1,152
- maximum campaign sends: **2,304**
- budget borrowing: false
- adaptive N: false
- failed-pair replacement: false
- same-stream rerun: false

## Single new apparatus intervention

Q3-D3 temporarily decorates `httpx.Response.read` and `httpx.Response.aread`. The wrapper calls the original method exactly once per caller invocation, observes only the returned bytes and immutable response/request metadata, records bounded structural metadata/hashes, and returns the exact bytes unchanged. It does not issue a request, consume a stream early, or change request arguments, headers, retries, timeouts, model/provider configuration, prompts, parser behavior, iteration/token limits, tool/memory/session state, fallback behavior, or concurrency.

## Future execution gate

The future marker path is `research/d2_vnext_q3d3/RUN_D2_VNEXT_Q3D3`. The future provider workflow is `.github/workflows/d2-vnext-q3d3-diagnostic.yml` on branch `qualification/d2-vnext-q3d3-http-sdk-boundary`.

The marker is absent at freeze. Provider/model execution is **not authorized** by construction. Any future live Q3-D3 diagnostic requires separate explicit human authorization naming the exact final marker-absent candidate SHA and an explicit maximum of **2,304 physical provider sends**. The authorization commit must be a marker-only child of that exact candidate and the workflow must be run attempt 1.

No Q3-D2/Q3-D rerun, Q2-A/Q2-B, scientific-effect, Acceptance, registry promotion, D2e, deployment/publication, credential/permission, or Historical Substrate action is authorized.
