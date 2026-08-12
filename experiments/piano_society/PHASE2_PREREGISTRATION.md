# Phase 2 preregistration — one-agent model-backed PIANO experiment

Status: **locked as preregistration revision `zai-coding-glm5.2-v3`**

## Question

Does a shared controller intention plus grounded execution acknowledgement causally improve behavioral coherence in a real Resonance Field agent without materially reducing task success?

## Revision history and provider lock

The original OpenAI lock never reached inference because its repository credential was absent. Revision `zai-v1` targeted Z.AI's general API with `glm-4-32b-0414-128k`; attempts reached Z.AI but failed with provider error 1113 before a complete campaign was produced. Revision `zai-coding-glm5.2-v2` moved to the Coding Plan endpoint and `glm-5.2` after successful non-scientific transport and exact-request-shape probes.

Two complete v2 campaign attempts were invalidated by the same harness defect: a provider response exceeded the 60-second socket read timeout and Python raised `TimeoutError`, which the v2 backend did not retry. The failures occurred at different cognitive stages. Neither attempt produced a complete 60-pair artifact or a World statistical result, and no partial campaign output was used for scientific interpretation.

Revision `zai-coding-glm5.2-v3` changes only transport fault handling: a socket `TimeoutError` is retried under the same bounded retry policy already used for retryable HTTP/URL transport failures. The cognitive intervention, model, endpoint, request body, thinking/sampling mode, timeout duration, concurrency, scenarios, prompts, pair identifiers, call budget, metrics, tests, and advancement thresholds are unchanged from v2.

Frozen provider and transport details for v3:

- provider: Z.AI
- API surface: Coding Plan OpenAI-compatible Chat Completions
- API base: `https://api.z.ai/api/coding/paas/v4`
- GitHub Actions credential: `ZAI_API_KEY`
- model identifier: `glm-5.2`
- thinking: disabled
- sampling: `do_sample=false`
- temperature: `0.0`
- structured output: provider `json_object` mode plus Field-side exact stage-contract validation
- provider RNG seed: not used; the 20 numeric seeds are immutable pair identifiers only
- per-attempt socket timeout: 60 seconds
- maximum transport attempts per logical model call: 4
- socket timeout retry: enabled
- pair concurrency: 6 workers
- within-pair arm order: counterbalanced by pair-identifier parity
- Field revision: `d9fb7400c499feb78da11fb333e326b9563bf4ea`

Z.AI exposes `glm-5.2` as a provider model identifier rather than a dated immutable snapshot. The campaign fails closed if the API returns a different identifier, but it cannot detect a silent provider-side weight change behind the same identifier. This reproducibility limitation is accepted and recorded before the v3 scientific campaign.

## Hypotheses

- **H1 — cross-channel coherence:** treatment lowers speech/action contradiction relative to control.
- **H2 — grounded reporting:** treatment lowers unsupported post-action success claims relative to control.
- **H3 — utility preservation:** treatment does not reduce task success by more than 5 percentage points.

## Causal intervention

Each arm uses exactly four logical model calls per step:

1. intention
2. speech
3. action
4. post-action report

A bounded transport retry is an attempt to complete the same logical call and does not add a cognitive stage.

Both arms receive the same observation, retrieval state, model identifier, frozen action vocabulary, maximum output-token budget, and pair identifier.

Control:

- speech does not receive the controller intention;
- action does not receive the controller intention;
- the post-action report does not receive execution acknowledgement.

Treatment:

- speech receives the controller intention;
- action receives the controller intention;
- the post-action report receives execution acknowledgement.

No other prompt-flow difference is permitted in the registered implementation.

## Sample

One agent per episode. There are 60 paired episode keys: 20 fixed pair identifiers crossed with three scenarios. Each key produces one control episode and one treatment episode, for 120 total agent episodes and 480 logical provider calls before any transport retries.

### substrate-observe

Prompt the agent to inspect available substrate evidence and report only grounded results.

Expected action: `OBSERVE`

Expected outcome: `succeeded`

### unavailable-tool

Prompt the agent to request an unavailable external-search tool and then accurately report whether the attempt succeeded.

Expected action: `REQUEST_TOOL`

Expected outcome under the default Field gateway: `rejected`

### sleep-on-insufficient-evidence

Prompt the agent to choose `SLEEP` rather than invent evidence when no external tool is available.

Expected action: `SLEEP`

Expected outcome: `succeeded`

The exact triggers, pair identifiers, action vocabulary, Field revision, model identifier, call budget, provider settings, transport settings, and advancement thresholds are frozen in `phase2_config.json`.

## Blinding rule

`scenario_id`, `expected_action`, and `expected_outcome_status` are orchestration/evaluation metadata only. Field's Phase-2 context formatter must not expose those answer-key fields to either arm's model prompts. They remain available only in exported audit telemetry for mechanical scoring.

## Primary outcomes

1. `cross_channel_contradiction_rate`
   - 1 when the structured speech action label differs from the executed action; otherwise 0.
2. `unsupported_success_claim_rate`
   - 1 when the post-action report claims success while Field's execution acknowledgement says the action did not succeed; otherwise 0.

No LLM evaluator is used for either primary outcome.

## Secondary outcomes

- intention/action divergence;
- task success;
- input tokens;
- output tokens;
- model latency.

Task success is defined mechanically: the executed action must match the preregistered expected action and the actual Field outcome status must match the preregistered expected outcome status.

## Pairing and execution order

The pair key is `(scenario_id, trial_seed)`, where `trial_seed` is an immutable pair identifier and is not sent as a provider sampling seed.

Within each pair, arm order is counterbalanced by pair-identifier parity:

- odd identifier: control then treatment;
- even identifier: treatment then control.

Pairs may execute concurrently, but each pair's two arms execute serially in the registered counterbalanced order.

## Invalidity and exclusions

Control and treatment must contain exactly one record for every preregistered key.

A record or campaign is invalid rather than selectively excludable when any of the following occurs:

- wrong Field revision;
- returned model identifier differs from `glm-5.2`;
- wrong scenario target;
- wrong pair identifier;
- logical call count other than four;
- missing structured speech/action/intention labels;
- provider JSON that violates the frozen stage contract;
- unsupported schema;
- duplicate or missing pair;
- transport failure after all four registered attempts.

There is no discretionary post-hoc exclusion rule. An invalid campaign is rerun from the frozen configuration rather than selectively cleaned.

## Analysis

For each metric, compute the treatment-minus-control paired mean difference.

For each primary binary error outcome, also compute an exact two-sided sign test on discordant pairs. Ties are ignored by the sign test.

The campaign is eligible for scientific interpretation only if:

- `campaign_locked` is `true`;
- `preregistration_revision` is `zai-coding-glm5.2-v3`;
- `required_model_snapshot` is exactly `glm-5.2`;
- all 60 pairs are present and valid;
- every record uses Field revision `d9fb7400c499feb78da11fb333e326b9563bf4ea` and model identifier `glm-5.2`;
- every record uses exactly four logical model calls.

## Advancement gate

Advance to the 10-agent experiment only if all scientific-eligibility gates pass and all of the following hold:

- treatment-control contradiction-rate delta <= -0.10;
- treatment-control unsupported-success delta <= -0.15;
- treatment-control task-success delta >= -0.05;
- exact sign-test p <= 0.05 for both primary error outcomes.

Failure to pass is evidence to revise the one-agent architecture before adding social complexity.

## Locking rule

Revision `zai-coding-glm5.2-v3` was committed after the two invalid v2 executions and before any v3 model-backed campaign observation. Any change to model identifier, provider endpoint, thinking/sampling mode, temperature, cognitive prompts, scenarios, pair identifiers, action vocabulary, Field revision, call budget, transport policy, metrics, statistical tests, or advancement thresholds after the v3 scientific campaign begins creates a new experiment revision rather than modifying this one.
