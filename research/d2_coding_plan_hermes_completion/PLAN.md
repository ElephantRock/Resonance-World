# D2-vNext Hermes / Coding Plan completion-envelope qualification

Issue: #219

## Scope

This is a fresh engineering-only successor to completed issue #213 / merged PR #218. It does not rerun or replace the consumed #213 request stream and contains no capability-development trajectory, scientific task scoring, registry promotion, Acceptance action, or Historical Substrate activation.

PR #218 remains a valid negative qualification: the intended Coding Plan route was exercised with three bounded provider sends and no terminal HTTP 429 / code 1113, but two probes ended with `finish_reason=length` under the frozen one-iteration / 64-token completion envelope.

## Frozen environment

The provider/product environment is unchanged:

- Z.AI product: GLM Coding Plan
- supported product environment: Hermes Agent Python library
- Hermes repository: `hermes-agent-org/hermes`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package version: `0.8.0`
- pinned `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- OpenAI SDK: exactly `2.21.0`
- httpx: exactly `0.28.1`
- provider: `zai`
- API mode: `chat_completions`
- Coding Plan base URL: `https://api.z.ai/api/coding/paas/v4`
- requested model: exact `glm-5.3`
- sole provider credential: `ZAI_API_KEY`

No General API or alternate-provider fallback is permitted.

## Fresh completion/output envelope

Exactly three fresh logical probes are registered. Each uses a fresh `AIAgent` with:

- `max_iterations=2`
- `max_tokens=512`
- `enabled_toolsets=[]`
- `quiet_mode=True`
- `skip_context_files=True`
- `skip_memory=True`
- `persist_session=False`
- no fallback model/provider
- no conversation history
- no scientific cases or feedback

The second agent iteration is prospectively permitted only as ordinary Hermes completion behavior, including continuation following a length-limited first model response. It is not an application-level replacement probe.

## External-call bound

The predecessor source audit established a conservative maximum of 18 physical provider sends for one Hermes model-call iteration:

`3 Hermes application attempts/cycle × 2 possible cycles × 3 OpenAI SDK sends/attempt = 18`

This successor permits at most two model-call iterations per logical probe, so the registered hard ceilings are:

- `2 × 18 = 36` physical provider sends per probe
- `3 × 36 = 108` physical provider sends total

The same fail-closed process-wide httpx guard is reused. It blocks before transmission any URL outside the frozen Coding Plan base URL, the 37th send in a probe, or any send beyond 108 total. Workflow reruns and application-level replacement probes are prohibited.

## Qualification decision

A pass requires all three probes to:

1. complete successfully through Hermes;
2. produce a non-empty final response;
3. use between one and two observed Hermes model/API calls;
4. avoid terminal HTTP 429 / provider code 1113;
5. preserve the exact provider/model/base-URL/tool-disable contract; and
6. remain within the physical-send budget with zero blocked unregistered outbound requests.

Effective upstream model identity is preserved if observable without changing request semantics; otherwise it remains explicitly unobserved.

## Governance

Construction, tests, credential-free preexecution, and review are autonomous. Provider execution is not. The execution marker must be absent from the frozen construction candidate. Any provider execution requires explicit human authorization of that exact candidate, followed by a sole-child marker commit that is the only diff.

Future marker path:

`research/d2_coding_plan_hermes_completion/RUN_D2_CODING_PLAN_HERMES_COMPLETION_QUALIFICATION`

Future marker contents:

```text
candidate_sha=<exact frozen candidate SHA>
issue=219
authorization=D2_vNext_Hermes_Coding_Plan_completion_execution_explicitly_authorized
```

Historical Substrate remains **OFF**.
