# PIANO validated-primitives extraction decision

Status: **experiment lineage complete; production extraction may proceed only for the primitives below.**

This decision follows the branch-first experimental plan: isolate the architecture, run controlled experiments, then extract validated primitives rather than merge the experimental package wholesale.

## Evidence boundary

The later PIANO lineage established three different classes of result:

1. **Runtime/control contracts remained stable and auditable.** Shared controller intention, executable action selection, grounded execution acknowledgement, exact logical-call accounting, and complete-case records supported the one-agent through institutional experiments without requiring a fork of the production Field runtime.
2. **Institutional authority passed a corrected confirmatory test.** After removing semantic-ID and action-order leakage, attested authority reduced spoof capture from 29/60 to 0/60 in Phase 4C, with the original advancement gate satisfied.
3. **Passive institutional memory did not satisfy the registered materiality standard.** Phase 5, 5B, and 5C did not advance. Phase 5D produced strong model-free directional validation at the independently selected information depth, but the untouched mean lift was +2.9576 percentage points, below the frozen +3-point threshold. No model-backed replication was unlocked.

The extraction policy therefore distinguishes **validated interfaces/invariants** from **unvalidated performance claims**.

## Promote to production contracts

### 1. Grounded execution acknowledgement

Promote the acknowledgement boundary currently exercised by the experimental Field adapter:

- exact request/correlation identity;
- policy/gateway result;
- observed outcome status;
- error, if any;
- expectation match as audit metadata;
- `grounded_success` derived from observed execution, never from model self-report.

This should become a reusable production-facing result contract around `AgentRuntime`, not a second runtime implementation.

### 2. Explicit controller decision bottleneck

Promote an optional controller result that can carry:

- high-level intention;
- intended executable action/strategy;
- confidence;
- provenance / controller metadata.

Output channels may consume the same controller decision, but the production runtime remains responsible for executable gating and action dispatch. The contract must not require every policy to use an LLM or four-call PIANO prompting.

### 3. Post-execution reporting must consume acknowledgement

Where an agent emits a post-action report, the production interface should make the execution acknowledgement available explicitly. Unsupported success claims should be mechanically measurable rather than left to prompt convention.

### 4. Attested institutional authority

Promote authority as a World-owned institution primitive with machine-verifiable provenance. The model-visible authority identifier must be semantically opaque; verification state must come from the authority contract, not naming conventions or prompt wording.

Required invariants:

- opaque notice/authority IDs;
- verification performed outside the model;
- model-visible trusted/untrusted status derived from verification;
- no semantic answer-key strings such as `grant`, `spoof`, `verified`, or policy labels embedded in IDs;
- presentation order must not encode authority priority.

### 5. Scientific provenance / complete-case execution

Promote the experiment infrastructure patterns that repeatedly prevented false conclusions:

- immutable source-artifact binding where identity affects downstream state;
- exact config digest on every record;
- pinned Field/World revisions and model snapshot;
- deterministic unit materialization;
- paired common-random-number environment trials where applicable;
- final analysis only after all preregistered records exist;
- transport retries do not create additional scientific observations;
- failed partial runs produce no scientific result.

These are research-platform contracts, not agent intelligence features.

## Promote only as experimental/optional interfaces

### Shared intention across channels

Keep shared intention as an optional policy/controller interface, not a mandatory production behavior. It is useful for cross-channel consistency and supplied the control surface for later PIANO work, but production code should not hard-code a particular prompt decomposition or provider call count.

### Organization-owned memory API

The World organization object may retain a generic memory/state interface because the experiments require memory to affect routing/decision policy rather than the environment directly. However, no particular passive memory representation should be declared performance-valid.

The production invariant should be:

> organization memory may influence controller decisions; the environment outcome law must not read memory directly unless an experiment explicitly studies such a causal path.

## Do not promote as validated performance mechanisms

### Passive winning-policy memory

Do not promote Phase 5's pre-turnover winning-strategy memory as a validated performance feature. It produced only +0.62 percentage points in the confirmatory experiment and failed the advancement gate.

### Fixed-context structural memory

Do not promote Phase 5B's fixed-context latent structural memory as a performance feature. It produced a complete null because fresh roster geometry removed the decision boundary.

### Decision-relevant passive structural memory as a >=3 pp claim

Do not claim that the Phase 5C/5D passive structural-memory mechanism yields at least +3 percentage points of post-turnover value. Phase 5C reached +2.539 points; Phase 5D untouched validation reached +2.9576 points and therefore still failed the registered materiality gate.

The mechanism is scientifically interesting and may remain available for research, but it is not a production-validated performance primitive.

## Do not extract

Keep the following experiment-local:

- phase-specific mission constructors and calibration searches;
- Phase 5B/5C/5D target-selection logic;
- provider-specific PIANO prompt templates;
- fixed four-call campaign orchestration;
- frozen experimental action/strategy vocabularies;
- preregistration-specific advancement thresholds;
- synthetic fixtures and answer-key fields.

These are experimental instruments, not product architecture.

## Recommended production extraction shape

### Resonance Field

Add reusable contracts adjacent to the existing runtime rather than replacing it:

- `ControllerDecision` — optional high-level intention plus intended action/provenance;
- `ExecutionAcknowledgement` — grounded result derived from the production `AgentRuntime` step;
- optional `PostExecutionReporter` protocol consuming `(decision, acknowledgement)`;
- redacted/auditable serialization helpers for World experiments.

The existing `AgentPolicy.choose(...) -> ActionRequest` path should continue to work unchanged. PIANO-aware policies should be composable adapters.

### Resonance World

Add reusable institution-level contracts:

- `AuthorityNotice` with opaque identifier and signed/attested provenance;
- `AuthorityVerification` performed outside model inference;
- generic organization memory snapshot interface with no direct environment coupling;
- experiment provenance helpers for immutable source/config/revision bindings.

### Integration rule

Implement extraction on dedicated integration branches in Field and World. Keep all experimental branches intact as evidence. Do not merge the `experiments/piano_society` package wholesale into production APIs, and do not merge to `main` without explicit approval.

## Final scientific decision

The PIANO investigation supports the architectural principle:

> Scale intelligence through explicit controller, institution, provenance, and feedback contracts rather than through larger prompts alone.

It does **not** support the stronger claim that the passive institutional-memory mechanism tested here has crossed the project's registered materiality threshold.
