# D2-vNext-Q3-D4 construction status

Status: **credential-free observer qualification only; no sample frozen; provider execution unauthorized**.

Construction issue: `#308`.

Q3-D4 is the apparatus repair successor to consumed Q3-D3. Q3-D3 failed observability because its global `httpx.Response.read` / `aread` observer produced zero HTTP-body records despite 194 transport sends and 154 downstream logical-call records.

## Observer boundary

Q3-D4 decorates the request-scoped OpenAI client's `_process_response` method after the already-qualified Q3-D2 request-client factory observer is installed. At that boundary the `httpx.Response` is available immediately before OpenAI object parsing.

The Q3-D4 observer:

- inspects `response.content` only if `response.is_stream_consumed is True`;
- never calls `read()` or `aread()`;
- never creates or retries a request;
- does not mutate request arguments, response bytes, headers, provider/model configuration, prompts, parser behavior, token/iteration limits, tools, memory/session state, fallback behavior, or concurrency;
- retains only bounded structural metadata, counts, lengths, selected enums, token counts, and SHA-256 commitments;
- calls the original `_process_response` exactly once with unchanged arguments and returns its exact result;
- fails closed structurally when the response is not already buffered or cannot be identified.

## Qualification boundary

Credential-free qualification must use exact `openai==2.21.0` and `httpx==0.28.1` with `MockTransport`, plus pinned Hermes revision `036cbdfa0a3158454a0a2a7a7388cf70353326b4` to exercise its real `_interruptible_api_call` worker-thread path. The harness must prove that the observer adds no `Response.read()` call and composes with the unchanged Q3-D2 semantic observer.

No Q3-D4 namespace, seed range, sample size, shard plan, send ceiling, execution marker, provider-triggering workflow, or qualification branch is frozen by this phase.

Provider/model execution remains unauthorized. No Q3-D3/Q3-D2/Q3-D rerun, Q2-A/Q2-B, scientific-effect, Acceptance, registry promotion, D2e, deployment/publication, credential/permission, or Historical Substrate action is authorized.
