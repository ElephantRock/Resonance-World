# Q3-D3 observability-failure forensics

Q3-D3 attempted to observe response bytes by globally decorating `httpx.Response.read` and `httpx.Response.aread`. In the live qualification, the transport ledger recorded 194 physical provider sends and the Q3-D2 request-scoped semantic observer produced 154 logical-call records, but the Q3-D3 recorder captured zero HTTP-body rows. The frozen evaluator therefore failed observability.

## Source-verified runtime path

Pinned OpenAI Python `2.21.0` calls `self._client.send(...)` in `SyncAPIClient.request`, then passes the resulting `httpx.Response` into `_process_response`. For ordinary non-streaming responses, `_process_response` creates an `APIResponse` and calls `parse()`. `APIResponse.parse()` calls `read()`, which delegates to `self.http_response.read()` before JSON/object parsing.

Pinned HTTPX `0.28.1` also calls `response.read()` in `Client.send()` when `stream=False`.

Pinned Hermes `036cbdfa0a3158454a0a2a7a7388cf70353326b4` runs each chat-completion request in a worker thread, creates a request-scoped OpenAI client inside that worker, calls `request_client.chat.completions.create(**api_kwargs)`, waits for the worker to terminate, and then returns the response or error.

These source paths mean the simple claim “the pinned stack never calls `httpx.Response.read()`” is unsupported. The live zero-record outcome instead demonstrates that the global `Response.read`/`aread` monkeypatch was not an authoritative attachment point in the actual qualification apparatus. The frozen evidence did not retain runtime class/method identity, so the exact live attachment divergence cannot be reconstructed retrospectively.

## Repair direction

Q3-D4 observes the already-buffered `httpx.Response` passed directly to the request-scoped OpenAI client's `_process_response` method. The observer does not call `read()` or `aread()`. It inspects `response.content` only when `response.is_stream_consumed` is already true, retains bounded structure/hashes only, calls the original `_process_response` exactly once with unchanged arguments, and returns the exact original result.

Credential-free tests must exercise both the exact OpenAI `2.21.0` / HTTPX `0.28.1` stack with `MockTransport` and the pinned Hermes `_interruptible_api_call` worker-thread path. This establishes apparatus qualification only; it does not establish the scientific cause of terminal-empty events.
