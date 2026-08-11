# W4-00 — Relationship-State Architecture Audit

Status: **ARCHITECTURE A — NO NATIVE PAIR-LEVEL PERSISTENT STATE**

Parent issue: #18

## Purpose

W4-00 is an architecture and provenance audit. It does not test whether relationship capital exists. It establishes which relationship-level manipulations are scientifically meaningful in the current Resonance Field / Resonance World stack.

## Audited revisions

- Resonance Field: `0914a21249261fe61e02c5191f4a36df416c672f`
- Resonance World W3 baseline: `b377c68abeb2151e57fc4c4c45e64c0d3fd92f98`

The machine-readable audit is `configs/w4/relationship-state-audit.json`; `resonance_world.w4_architecture_audit` enforces its classification and claim boundary.

## Finding

The current Field architecture has persistent **individual competence** and a persistent **global shared substrate**, but no persistent pair-owned learned state.

| Primitive | Exists? | Native learned state? | Relationship-specific? |
| --- | --- | --- | --- |
| individual `practice_by_skill` | yes | yes | no |
| shared stigmergic traces | yes | yes | no |
| requester↔winner interaction history | yes | evidence only | yes |
| candidate/opportunity topology observations | yes | evidence only | no |
| persistent pair object | no | no | yes |
| partner-conditioned policy | no | no | yes |
| pair-owned memory | no | no | yes |
| joint execution state | no | no | yes |
| persistent role allocation | no | no | yes |
| Field-native portable pair capsule | no | no | yes |

Therefore the current architecture is classified as:

> **A_NO_NATIVE_PAIR_STATE**

A relationship can be *observed* in the provenance graph without being a persistent learned object in the runtime.

## Field evidence

### Individual competence

`src/resonance/experiments/integration_campaign.py` maintains practice keyed by `(winner_slot, required_skill)`. The success law reads the winner's own accumulated practice and increments that individual counter after the task. No `(agent_a, agent_b)` learned state is updated.

### Shared substrate

`src/resonance/substrate/models.py` defines a `Trace` with optional `author_agent_id` and shared visibility. The object does not contain a pair owner, partner set, pair identifier, or pair-only visibility scope.

### Coordination topology

The later Coordination Topology campaign records append-only candidate-edge observations and changes pre-award opportunity routing. It does not add a persistent learned relationship object.

## W3 clarification

W3 did **not** transfer a Field-native relationship phenotype.

`src/resonance_world/w3_source_export.py` derived `coordination_exposure` in World by counting successful requester↔winner histories. `src/resonance_world/w3_swarm_core.py` then added a destination success bonus proportional to:

`coordination_gain * sqrt(coordination_exposure)`

subject to a cap.

That mechanism is a deliberate **World-derived experimental proxy with a direct outcome effect**. It is not a learned pair state emitted by Resonance Field.

The W3 numerical campaign remains valid under its registered destination model. The safe interpretation is narrower:

> W3 replicated a two-agent swarm advantage under a World destination model containing an explicit coordination-exposure proxy; independent relationship-aware selection did not replicate against the competence-only pair baseline.

W3 is **not** evidence that partner-specific relationship capital spontaneously emerged inside the current Field runtime.

## Operations blocked by W4-00

Until a pair-level state becomes independently manipulable, the following terms are operationally undefined and must not be used as behavioral treatments:

- relationship reset;
- joint-memory ablation;
- partner-policy ablation;
- portable pair-capsule transfer.

A null result produced by "removing" a state that the architecture never possessed would not be informative.

## Required next phase: W4A

The next phase is an architectural extension campaign, **W4A — Minimal Joint-Learning Substrate**.

W4A may add only generic affordances that make relationship learning *possible*:

1. a genuine joint-execution environment;
2. partner-conditioned experience/history;
3. pair-shared episodic memory;
4. matched communication channels for experienced and stranger pairs;
5. fixed pairing during formation, with baseline compatibility measured before treatment.

### Critical prohibition

W4A must **not** implement a direct rule of the form:

`more relationship history -> higher success probability`

or any equivalent scalar relationship bonus.

If relationship value is later observed, it must arise because generic joint-learning affordances allow agents to make better coordinated decisions—not because the evaluator rewards relationship history directly.

## Behavioral campaign after W4A

Only after W4A provides independently manipulable relationship state should W4 use the four-condition partner-swap factorial:

- C1: original experienced pair `A+B`;
- C2: experienced member with matched stranger `A+B'`;
- C3: matched strangers `A'+B'`;
- C4: best matched individual `A`.

Interpretation:

- `C1 > C2 ≈ C3`: partner-specific capital;
- `C1 ≈ C2 > C3`: general teamwork skill;
- `C1 > C2 > C3`: both;
- `C1 ≈ C2 ≈ C3`: neither.

The transfer tasks must be novel relative to relationship formation, pairing must remain fixed during treatment, communication bandwidth must be equalized, and compute accounting must separate per-agent from total-team resources.
