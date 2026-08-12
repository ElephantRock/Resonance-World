# Phase 1 — Live Resonance Field Contract

Status: **contract identified; live implementation not yet added**

Field reference inspected: `ElephantRock/Resonance-Field@e3f924eb33dcc811e208600cc8928d2b97d07f5d`

## Why Phase 0 cannot simply be pointed at Resonance Field

The current Resonance Field public agent boundary is intentionally narrow:

```python
class AgentPolicy(Protocol):
    def choose(self, agent_id: UUID, context: DecisionContext) -> ActionRequest: ...
```

`AgentRuntime.step()` then gates and executes the `ActionRequest` and returns a
`StepResult` containing the request, policy evaluation, action outcome, and decision
event.

That interface is appropriate for the current Field architecture, but it exposes only
one action proposal. A live PIANO experiment needs to observe at least two independently
produced channels before arbitration (for example speech/social output and physical or
substrate action) and then feed execution acknowledgement back into the experimental
cognitive state.

Using World-side guesses to reconstruct those hidden proposals would make the metric
circular and is therefore prohibited.

## Minimal experimental port

The smallest useful Field-side experimental contract is conceptually:

```python
@dataclass(frozen=True, slots=True)
class ProposalBundle:
    state_revision: int
    cognitive_intent: str
    speech_proposal: str
    action_request: ActionRequest


@dataclass(frozen=True, slots=True)
class ExecutionAck:
    state_revision: int
    request_id: UUID
    outcome: ActionOutcome


class CognitiveExperimentPort(Protocol):
    def propose(self, agent_id: UUID, context: DecisionContext) -> ProposalBundle: ...
    def acknowledge(self, agent_id: UUID, ack: ExecutionAck) -> None: ...
```

The exact production API does not need to look like this. These are the minimum
observables required by the experiment.

## Arm semantics

### Baseline

- cognitive, speech, and action proposals are allowed to diverge;
- no shared intention is broadcast before output generation;
- success language may be generated without consulting the execution acknowledgement.

### Treatment

- the same observation, model snapshot, tools, seed, and compute budget are used;
- a shared controller intention conditions the observable output channels;
- the execution acknowledgement updates experimental state before any success claim is
  emitted.

## Ownership

Resonance Field must continue to own:

- agent cognition,
- `ActionRequest` creation,
- policy gating,
- action execution,
- local state mutation.

Resonance World may own only:

- paired-arm orchestration,
- seed/scenario freezing,
- telemetry collection,
- metric computation,
- cross-run comparison.

The World experiment must not import or mutate Field-private cognitive state.

## Next implementation gate

A genuine Phase 1 run requires a **companion experimental change in Resonance Field**
(or an already-public equivalent port) that exposes the proposal bundle and execution
acknowledgement without changing production semantics.

Until that exists, Phase 0 remains instrumentation validation only. Do not report its
synthetic deltas as evidence that PIANO improves Resonance Field agents.
