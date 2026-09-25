# D2-vNext-Q3-D2 construction status

Mode: **credential-free construction only**.

Issue: #300.

## Purpose

Q3-D2 repairs the semantic-observability attachment point discovered after consumed Q3-D run `36068734507` returned `Q3-D-OBSERVABILITY-FAIL`.

The sole construction intervention in this revision is to observe the request-scoped OpenAI client returned by Hermes' `_create_request_openai_client` factory instead of decorating only the persistent `agent.client` object.

## Invariants

- preserve the frozen Q2/Q3-D provider, model, prompt, parser, retry, iteration, token, tool, memory/session, fallback, and transport behavior;
- call the original Hermes request-client factory exactly once with unchanged arguments;
- call the returned client's original `chat.completions.create` exactly once with unchanged arguments;
- return the exact response object unchanged, or re-raise the same exception;
- retain only structural metadata, bounded enums/counts/lengths, token counts when returned, and SHA-256 commitments;
- retain no raw prompt, provider body, assistant content, retry content, or terminal content;
- fail closed when positive Hermes API-call counts are not represented one-for-one by semantic-completion records.

## Authority boundary

Provider/model execution is **NOT AUTHORIZED**.

There is no Q3-D2 execution marker and no provider-triggering Q3-D2 workflow in this revision. No fresh live cohort or campaign send ceiling is frozen by this revision.

Q3-D is consumed and must not be rerun. Q2-A/Q2-B are not authorized. Scientific-effect gates, Acceptance, registry promotion, D2e, deployment/publication, credential/permission changes, and Historical Substrate actions remain unauthorized.

Any future Q3-D2 live diagnostic requires a fresh namespace and cohort/sample plan, a frozen marker-absent exact candidate, an explicit physical-provider-send ceiling, and separate explicit human authorization naming the candidate and ceiling.
