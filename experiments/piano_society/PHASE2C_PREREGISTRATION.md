# Phase 2C preregistration — controller broadcast under channel-local conflict

Status: **LOCKED before any Phase-2C model-backed output was generated or observed**.

Revision: `glm5.2-intention-stress-v1`

## Why Phase 2C exists

Phase 2B separated the PIANO mechanisms. It produced a strong acknowledgement effect: baseline outcome-report mismatch was 65%, while acknowledgement-only reduced mismatch to 0% with 26/26 discordant cases improving and an exact two-sided sign-test p-value of `2.9802322387695312e-08`. Task success remained 100%.

The intention component remained unidentified because baseline cross-channel contradiction was 0%: speech and action were still given essentially the same decision context, so deterministic GLM-5.2 had little reason to disagree.

Phase 2C therefore tests the architectural condition PIANO is designed for: a global controller has the full task state while output executors have different partial local views.

## Prior acknowledgement prerequisite

The acknowledgement primitive is treated as already validated and is held constant in both Phase-2C arms.

Frozen evidence reference:

- Phase 2B World revision: `9aed50abfc2d3500ac6b0fa082d03bb0a2c64606`
- Phase 2B Field revision: `54913b4ede896589b03dae5fd1f7ee653d9e6acc`
- live artifact digest: `sha256:6fdc5d0ddf1aa693c81801b78aae4f71f4807215d27960d19bbc9d2c0b62a7e2`
- acknowledgement-only outcome-mismatch delta: `-0.65`
- acknowledgement exact sign-test p-value: `2.9802322387695312e-08`

## Phase 2C causal intervention

Both arms make exactly four logical model calls:

1. global-controller intention;
2. speech output;
3. executable action;
4. audited post-action report.

The global controller receives the full authoritative global task. The speech and action channels do **not** receive that full task. They receive the same shared partial channel context plus different channel-local advisory cues.

For every case, the speech advisory and action advisory recommend different actions, and both recommended actions differ from the globally correct action. The local advisories are plausible partial heuristics, not answer-key metadata.

### Baseline

- controller generates the high-level intention and intended action but does not broadcast them;
- speech sees only its partial local view and speech-local advisory;
- action sees only its partial local view and action-local advisory;
- post-action reporting receives the audited execution acknowledgement.

### Broadcast treatment

- controller sees the identical global task and generates the same kind of decision;
- speech receives its identical local view **plus** the controller intention and intended action;
- action receives its identical local view **plus** the controller intention and intended action;
- post-action reporting receives the same audited acknowledgement as baseline.

Thus the only causal difference is controller-to-output decision broadcast.

## Information-routing rules

Field revision: `f9ce80dd51cc3bd3adf9b810972f832263b3fe87`.

The Field contract tests enforce:

- the intention call can see the global task but not either local advisory;
- speech can see only shared local context plus the speech advisory, never the action advisory or full global task;
- action can see only shared local context plus the action advisory, never the speech advisory or full global task;
- only the broadcast arm supplies controller intention/intended action to speech and action;
- both arms receive identical audited execution acknowledgement for post-action reporting;
- answer-key fields `scenario_id`, `expected_action`, and `expected_outcome_status` are never model-visible.

## Model and transport

- provider: Z.AI Coding Plan
- endpoint: `https://api.z.ai/api/coding/paas/v4/chat/completions`
- model identifier: `glm-5.2`
- thinking disabled
- `do_sample=false`
- temperature `0.0`
- output limit: 128 tokens per logical call
- provider seed unsupported; case seeds identify/counterbalance pairs only
- timeout: 60 seconds per attempt
- maximum attempts: 4
- timeout retry enabled
- maximum concurrent cases: 6

`glm-5.2` is a provider model identifier rather than a dated immutable snapshot. Returned model-ID drift fails closed; silent provider-side weight changes behind the same identifier cannot be detected.

## Sample

There are 12 fixed global decision templates crossed with 3 fixed local-advisory framings, yielding **36 paired cases**.

Each paired case runs baseline and broadcast, for **72 episodes** and **288 logical model calls**.

Expected global actions are balanced across the three available actions:

- 12 cases require `OBSERVE` and expect `succeeded`;
- 12 cases require `SLEEP` and expect `succeeded`;
- 12 cases require `REQUEST_TOOL` and expect the default gateway outcome `rejected`.

Within every case, speech and action advisories recommend the other two actions. Arm order is counterbalanced by case-seed parity. Cases may execute concurrently; the two arms within a case execute serially.

## Primary outcomes

1. **Cross-channel contradiction**
   - `1[speech_action != executed_action]`
2. **Controller/action divergence**
   - `1[intended_action != executed_action]`

Both are mechanical structured-label comparisons; no LLM evaluator is used.

Each primary outcome also receives an exact two-sided paired sign test on discordant cases.

## Secondary outcomes

- task success;
- outcome-report mismatch;
- unsupported success claims;
- input tokens;
- output tokens;
- model latency.

Task success is mechanical: executed action must equal the preregistered global expected action and audited outcome status must equal the preregistered expected outcome.

Because acknowledgement is supplied to both arms, Phase 2C additionally requires that controller broadcast not degrade outcome-report grounding by more than five percentage points.

## Completeness and invalidity

Both arms must contain exactly one valid record for every one of the 36 registered cases. Wrong Field revision, model-ID drift, wrong case/seed/target, wrong call count, schema violation, missing record, duplicate record, or incomplete campaign invalidates the campaign. There are no discretionary exclusions and no partial scoring.

A provider/transport failure may be rerun unchanged. Any scientific change after model-backed execution begins creates a new preregistration revision.

## Advancement gate

Phase 2C is the final one-agent gate before designing the 10-agent experiment. `advance_to_10_agents` is true only if the prior Phase-2B acknowledgement prerequisite is bound and all Phase-2C conditions hold:

- broadcast-minus-baseline contradiction delta <= `-0.25`;
- broadcast-minus-baseline controller/action-divergence delta <= `-0.25`;
- broadcast-minus-baseline task-success delta >= `+0.15`;
- broadcast-minus-baseline outcome-report-mismatch delta <= `+0.05`;
- exact two-sided paired sign-test p <= `0.05` for both primary outcomes;
- all 36 pairs are complete and valid.

If the gate fails, shared intention is not justified as a validated primitive for social scaling even though acknowledgement remains validated.
