# D2-vNext-Q3-D3 construction status

Status: **upstream observer implemented; provider execution unauthorized; sample not frozen**.

Issue: `#304`.

Q3-D3 is a diagnostic-only successor to the consumed Q3-D2 stream. Q3-D2 localized seven strict clean-terminal-empty target events to `provider_content_absent` at the request-scoped SDK semantic layer. Q3-D3 narrows the unresolved upstream interval by observing the HTTP response bytes **after HTTPX body reading/content decoding but before OpenAI SDK JSON/object decoding**, while preserving the exact Q3-D2 request-scoped semantic observer and all Q2 behavioral semantics.

The construction phase contains no execution marker, no provider-triggering Q3-D3 workflow, no frozen cohort, and no provider/model authority.

## Single new apparatus intervention

Q3-D3 temporarily decorates `httpx.Response.read` and `httpx.Response.aread`. The wrapper calls the original method exactly once, observes only the returned bytes and immutable response/request metadata, records bounded structural metadata/hashes, and returns the exact bytes unchanged. It does not issue a request, consume a stream early, or change request arguments, headers, retries, timeouts, model/provider configuration, prompts, parser behavior, iteration/token limits, tool/memory/session state, fallback behavior, or concurrency.

## Required fail-closed invariants

- one HTTP-body structural record for every response-bearing physical transport send;
- logical-send order must match the existing guarded transport ledger;
- every Q3-D2 semantic completion provider-send slice must map only to recorded transport sends and corresponding HTTP-body records where a response existed;
- duplicated or missing response-body observations are observability defects;
- raw prompt/provider/assistant/retry/terminal content is prohibited from retained evidence;
- instrumentation must preserve response-body bytes and request behavior exactly in credential-free synthetic tests.

## Construction stop

The apparatus may be merged after credential-free tests are green. A future sample plan, marker-gated workflow, frozen candidate, or provider execution requires a separately governed construction/freeze phase. No Q3-D3 provider/model execution is authorized here.
