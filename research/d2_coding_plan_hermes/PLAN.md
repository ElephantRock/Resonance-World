# D2-vNext Hermes / Coding Plan qualification

Issue: #213

## Scope

This stream is an engineering-only qualification of the intended GLM Coding Plan substrate through Hermes Agent. It is not a D2d-S2 rerun and contains no capability-development trajectory, held-out scientific evaluation, mechanism scoring, registry promotion, Acceptance action, or Historical Substrate activation.

The historical General API evidence remains unchanged. Issue #212 records the corrected entitlement interpretation: the project had a Coding Plan from the beginning, so the General API endpoint was not the intended subscription path.

## Frozen environment

- Z.AI product: GLM Coding Plan
- supported product environment: Hermes Agent Python library
- Hermes repository: `hermes-agent-org/hermes`
- Hermes revision: `036cbdfa0a3158454a0a2a7a7388cf70353326b4`
- Hermes package version at that revision: `0.8.0`
- pinned `run_agent.py` blob: `4c0d3be4b0c2d364c550fa663d34f6545c9e6d20`
- OpenAI SDK: exactly `2.21.0`
- httpx: exactly `0.28.1`
- provider: `zai`
- API mode: `chat_completions`
- Coding Plan base URL: `https://api.z.ai/api/coding/paas/v4`
- requested model: `glm-5.3`

The probe intentionally exercises Hermes' provider router. The process exposes `ZAI_API_KEY` as the sole provider credential and sets `GLM_BASE_URL` to the frozen Coding Plan base URL. `AIAgent` is not given an explicit API key or base URL, so bypassing the Hermes Z.AI provider router is not allowed. No General API or alternate-provider fallback is configured.

## Probe contract

Exactly three fresh logical probes are registered. Each probe creates a fresh `AIAgent` with:

- `max_iterations=1`
- `enabled_toolsets=[]`
- `quiet_mode=True`
- `skip_context_files=True`
- `skip_memory=True`
- `persist_session=False`
- no fallback model/provider
- no conversation history
- no scientific cases or feedback

The prompt is deterministic and non-scientific. Qualification requires only a non-empty final response and adherence to the frozen product/routing contract; response content is not scientifically scored.

## External-call bound

The first construction draft incorrectly treated the OpenAI SDK retry count as the complete retry envelope. Exact-source audit of pinned Hermes revision `036cbdfa...` shows that the main agent loop has three application attempts and may perform one additional direct-provider transport-recovery cycle. OpenAI SDK `2.21.0` is frozen with `DEFAULT_MAX_RETRIES == 2`, so a single application attempt can physically send at most three SDK requests.

The conservative registered envelope is therefore:

`3 Hermes application attempts/cycle × 2 cycles × 3 SDK attempts/application attempt = 18 physical provider attempts/probe`

and:

`3 logical probes × 18 physical provider attempts/probe = 54 physical provider attempts maximum`

This is not merely an arithmetic assumption. During the authorized execution window, a process-wide guard wraps the pinned httpx `Client._send_single_request` and `AsyncClient._send_single_request` physical-send boundaries. The guard:

1. permits only requests whose URL is under the frozen Coding Plan base URL;
2. blocks any unregistered outbound HTTP request before it is physically sent;
3. blocks the 19th attempted provider send within any probe before it is physically sent;
4. blocks any send beyond 54 across the entire three-probe campaign.

Thus unexpected Hermes recovery behavior can make the qualification fail but cannot increase provider exposure beyond the registered maximum.

No application-level replacement probe is permitted. The GitHub Actions workflow may execute only at `run_attempt == 1`; reruns fail closed.

## Result ceiling

A passing result establishes only that the supported Hermes / Coding Plan path can complete three bounded GLM-5.3 requests under the frozen account/environment contract without terminal HTTP 429 / code 1113 and with a non-empty final response.

Hermes' ordinary product boundary does not necessarily expose the provider's upstream effective-model field. If upstream effective identity is not directly observable, the result must record that limitation and may not infer it from the requested model slug.

A pass does not establish capability acquisition or schema generalization. It only clears the engineering dependency for constructing a fresh D2-vNext GLM-5.3 scientific stratum.

## Governance

Construction and credential-free CI are autonomous under the operating charter. Provider execution is not. The execution marker must be absent from the frozen construction candidate. Explicit human authorization of that exact candidate is required before a sole-child marker commit is created.

Future marker path:

`research/d2_coding_plan_hermes/RUN_D2_CODING_PLAN_HERMES_QUALIFICATION`

Future marker contents:

```text
candidate_sha=<exact frozen candidate SHA>
issue=213
authorization=D2_vNext_Hermes_Coding_Plan_execution_explicitly_authorized
```

Historical Substrate remains **OFF**.
