# Phase 2B preregistration — one-agent factorial hard-case PIANO experiment

Status: **LOCKED before any Phase-2B model-backed output was generated or observed**.

Revision: `glm5.2-factorial-hard-v1`

## Motivation

The completed Phase 2 v3 GLM-5.2 campaign was scientifically eligible but did not advance: baseline contradiction was only 3.33%, unsupported success claims were 0%, and task success was 96.67%. That created a floor effect and also exposed an asymmetric reporting metric: a control agent could always avoid claiming success and receive no error even when the audited action actually succeeded.

Phase 2B therefore remains at one agent, introduces harder conflicting-cue cases, separates the two PIANO mechanisms factorially, and adds a bidirectional mechanical outcome-report mismatch metric.

## Model and transport lock

- provider: Z.AI Coding Plan
- endpoint: `https://api.z.ai/api/coding/paas/v4/chat/completions`
- model identifier: `glm-5.2`
- thinking: disabled
- sampling: disabled (`do_sample=false`, temperature `0.0`)
- provider seed: unsupported; trial seeds are deterministic case identifiers only
- output limit: 128 tokens per logical call
- transport timeout: 60 seconds per attempt
- maximum transport attempts: 4
- socket timeout retry: enabled
- maximum concurrent cases: 6
- Field revision: `54913b4ede896589b03dae5fd1f7ee653d9e6acc`

Z.AI exposes `glm-5.2` as a model identifier rather than a dated immutable snapshot. The adapter fails closed if the returned model identifier differs, but it cannot detect silent provider-side weight changes behind the same identifier.

## Four-arm factorial intervention

Every arm makes exactly four logical model calls: intention, speech, action, and post-action report.

1. `baseline`: speech/action do not receive the generated intention; post-action report does not receive execution acknowledgement.
2. `intention_only`: speech/action receive the generated intention; post-action report does not receive acknowledgement.
3. `ack_only`: speech/action do not receive the generated intention; post-action report receives acknowledgement.
4. `full`: speech/action receive intention and post-action report receives acknowledgement.

No other model prompt-flow difference is permitted between arms.

The two registered component tests are therefore causally isolated:

- intention mechanism: `intention_only` versus `baseline` on cross-channel contradiction;
- acknowledgement mechanism: `ack_only` versus `baseline` on outcome-report mismatch.

The `full` arm is required to demonstrate that combining both mechanisms preserves the component benefits and task utility.

## Cases

There are 10 fixed hard-case templates crossed with 4 fixed distractor variants, producing **40 unique paired cases**. Each case is executed under all four arms, for **160 agent episodes** and **640 logical model calls**.

The challenge families include conflicting action cues, insufficient evidence, misleading readiness, action rejection after deliberate planning, stale outcome cues, and false-success pressure. Distractors are presented as confident operator advice, stale cache entries, peer pressure, or misleading dashboard state. They are explicitly non-authoritative; the correct current policy remains mechanically defined in the case template.

The answer-key fields `scenario_id`, `expected_action`, and `expected_outcome_status` remain private orchestration metadata and are not exposed by Field's model context formatter. Challenge-family and distractor labels may be visible, because they describe the presented evidence rather than the scoring answer.

## Arm ordering

The four arms are executed serially within each case. Position is balanced by a four-position Latin square derived from the deterministic case index, so each arm occupies each temporal position equally across the 40 cases. Cases may execute concurrently.

## Primary outcomes

### Intention effect on cross-channel contradiction

For each case:

`cross_channel_contradiction = 1[speech_action != executed_action]`

Primary contrast: `intention_only - baseline`.

### Acknowledgement effect on outcome-report mismatch

For each case:

`outcome_report_mismatch = 1[post_action_claims_success != grounded_success]`

Primary contrast: `ack_only - baseline`.

This metric is bidirectional: both false-positive success and false-negative success reports count as errors. It uses only structured model output and the audited Field acknowledgement; no LLM judge is used.

## Secondary outcomes

- full-versus-baseline changes in both primary metrics;
- intention/action divergence;
- unsupported success claims, retained for continuity with Phase 2;
- task success;
- mean input tokens;
- mean output tokens;
- mean model latency.

Task success remains mechanical: executed action must equal the preregistered expected action and the audited outcome status must equal the preregistered expected outcome.

## Statistical tests

Each primary binary contrast receives an exact two-sided paired sign test on discordant cases; ties are ignored. No post-hoc exclusions are permitted. Missing, duplicate, schema-invalid, wrong-revision, wrong-model, wrong-call-count, or wrong-case records invalidate the campaign rather than being selectively removed.

## Advancement gate

Advance to a 10-agent design only if all of the following hold:

- `intention_only - baseline` contradiction delta <= -0.10;
- `ack_only - baseline` outcome-report-mismatch delta <= -0.20;
- `full - baseline` contradiction delta <= -0.10;
- `full - baseline` outcome-report-mismatch delta <= -0.20;
- each isolated component's task-success delta >= -0.05;
- full-arm task-success delta >= -0.05;
- both primary exact sign-test p-values <= 0.05;
- all 40 cases and all four arms are complete and valid.

Failure means the corresponding one-agent mechanism should be revised or removed before social scaling.

## Locking rule

The model, Field revision, prompts, four-arm information paths, 40 materialized cases, case ordering, action vocabulary, token budget, transport policy, metrics, statistical tests, and advancement thresholds are frozen before any Phase-2B live model output. Any scientific change after execution begins creates a new preregistration revision.
