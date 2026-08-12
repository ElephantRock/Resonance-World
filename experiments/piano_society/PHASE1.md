# Phase 1 — Live Resonance Field Contract

Status: **live contract implemented; deterministic cross-repo smoke test wired; scientific policy experiment not yet run**

Pinned Field revision: `ElephantRock/Resonance-Field@f9416d841887476bbbcc97ba12c919c89d626ddc`

## Implemented Field boundary

The companion Field branch `experiment/piano-agent-runtime` now provides an experimental adapter that composes around the existing production `AgentRuntime` rather than replacing its execution semantics.

A Field-owned `PianoPolicy` emits a `PianoProposal` containing:

- raw high-level intention text;
- raw speech proposal text;
- the normal Field `ActionRequest`;
- structured `intended_action` and `speech_action` labels for mechanical scoring;
- an explicit `speech_claims_success` flag; and
- optional expected outcome status/effects.

The existing Field runtime still performs retrieval, policy gating, execution, side effects, and decision-event tracing. Only after that normal step completes does the experimental adapter derive an `ExecutionAcknowledgement`.

The exported World record uses the production `DecisionEvent.action_payload`, so Field's existing audit redaction remains authoritative and raw action secrets are not exported.

## Why structured labels were added

Natural-language intention and speech alone would require an LLM judge to infer whether channels contradict one another. That would reintroduce evaluator entanglement into the primary metric.

Phase 1 therefore freezes explicit action labels beside the raw text. World can mechanically compute:

- speech/action contradiction;
- intention/action divergence;
- unsupported success claims; and
- expected-vs-observed execution failure.

Raw text remains available for later secondary semantic analysis, but it is not required for the primary coherence score.

## Cross-repo contract smoke

The pinned Field revision includes a deterministic Field-owned paired fixture. It emits three control records and three treatment records through the actual `AgentRuntime` action/gateway/event path.

Resonance World:

1. checks out the exact pinned Field SHA;
2. installs both repositories;
3. asks Field to emit the control and treatment records;
4. validates the exported schema;
5. requires identical agent/time pairing across arms;
6. scores the records mechanically; and
7. uploads the control, treatment, and scored result as a CI artifact.

This run is deliberately marked:

```text
phase = live-contract-smoke
scientific_claim_allowed = false
```

The deterministic fixture proves boundary integrity and instrumentation only. Its treatment advantage is constructed and must not be cited as evidence that PIANO improves real Resonance agents.

## Ownership

Resonance Field continues to own:

- agent cognition and proposal generation;
- `ActionRequest` creation;
- policy gating;
- action execution;
- local state mutation; and
- execution acknowledgement derivation.

Resonance World owns only:

- paired-arm orchestration;
- revision/seed/scenario freezing;
- exported-record validation;
- metric computation; and
- cross-run comparison.

World must not reconstruct or mutate Field-private cognitive state.

## Next scientific gate

The next experiment is a **one-agent model-backed paired protocol**, not a scale-up.

Both arms must freeze the same:

- Field revision;
- model snapshot;
- observation sequence;
- substrate/world state;
- primitive action vocabulary;
- gateway policy;
- tool availability;
- compute/token budget; and
- seeds where the model/runtime exposes deterministic seeding.

### Control

Speech and action proposals are generated without a shared high-level intention constraint, and success language is not required to consult execution acknowledgement.

### Treatment

A shared controller intention conditions both observable proposal channels, and any success claim must be generated only after execution acknowledgement is incorporated.

The experiment remains at one agent until repeated paired runs produce stable measurements and the scoring protocol is frozen. Only then may it progress to 10 agents, followed by 50 and 100 if the predeclared gates continue to pass.
