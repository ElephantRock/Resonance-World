# D2-vNext-Q3-D observability-failure forensics

## Finding

The frozen Q3-D run failed its observability contract because the semantic observer was attached to the wrong OpenAI client object.

Q3-D's `scripts/d2_vnext_q3d_hermes_client.py` decorates `agent.client.chat.completions.create` on the long-lived agent client before invoking `agent.run_conversation(...)`.

The pinned Hermes revision `036cbdfa0a3158454a0a2a7a7388cf70353326b4` uses a different object for the actual synchronous chat-completion request. Inside its interruptible API-call path, Hermes calls `_create_request_openai_client(reason="chat_completion_request")` and then invokes `request_client.chat.completions.create(**api_kwargs)` on that newly created request-scoped client.

Therefore the persistent-client wrapper can remain completely uncalled while Hermes legitimately increments its API-call counter and the lower-level HTTP transport guard observes physical provider sends.

## Evidence consistency

This apparatus defect is consistent with the frozen Q3-D evidence:

- 515 Hermes agent invocations recorded positive API-call counts;
- all 515 invocations recorded zero semantic completions;
- the HTTP transport ledger still observed 568 physical provider sends;
- transport and logical attribution integrity passed;
- the evaluator correctly failed closed with `Q3-D-OBSERVABILITY-FAIL` and 2,060 observability defects.

The defect explains the missing semantic records without requiring any claim about provider output, model behavior, Hermes terminalization, or adapter selection.

## Causal ceiling

This is an **instrumentation-path localization**, not a scientific or provider/model root-cause finding. The apparent Q3-D `provider_content_absent` boundary counts are non-authoritative because the provider semantic layer was not actually observed.

No conclusion may be drawn from Q3-D about whether the 13 strict clean-terminal-empty target events originated at the provider-content boundary, inside Hermes, or at the terminal adapter.

## Successor repair

Q3-D2 should make one instrumentation-only change: decorate every client returned by the agent's `_create_request_openai_client` factory, while calling the original factory exactly once and calling the returned client's original `chat.completions.create` exactly once with unchanged arguments.

The wrapper must return the exact original response object or re-raise the exact request exception. It may retain only the structural metadata already permitted by Q3-D. It must make zero additional provider requests and must not alter prompts, model settings, parser behavior, retry rules, iteration limits, tools, memory/session state, or fallbacks.

Credential-free qualification must fail closed whenever Hermes reports a positive API-call count that is not represented one-for-one by semantic-completion records.
