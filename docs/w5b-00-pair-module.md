# W5B-00 — Pair Module Architecture

Status: **ARCHITECTURE ONLY — NO MODULE PERFORMANCE CLAIM**

W5B-00 introduces a first-class transport/container for the W4 social state that
already exists in Resonance World.

A `PairModule` contains:

- a stable module identifier;
- exactly two member identities and source-Field identities;
- copies of both members' existing `IndividualState` values;
- the W4 partner-model slice for that pair;
- both members' partner-independent general-teamwork state;
- the pair-owned shared episodic memory;
- formation-evidence references, capability metadata, and provenance;
- deterministic canonical serialization and SHA-256 content identity.

## Operations

`capture_pair` captures an already-developed W4 pair.

`instantiate_intact` restores the two individual states and their captured W4
relationship state.

`instantiate_with_reset` restores exactly the same individual states with an empty
relationship store. This is the primary W5B-01 state-modularization control.

`replace_member` is intentionally conservative. If member B is replaced by B′:

- A's individual competence is retained;
- B′ receives only B′'s own individual competence;
- A↔B partner-specific models are dropped;
- A↔B pair-owned episodes are dropped;
- B's general-teamwork state is dropped;
- A may retain A's partner-independent general-teamwork state;
- no old pair state is relabeled as A↔B′ state.

This makes W5B-02 a genuine succession test rather than a state-transplant trick.

## Hard causal boundary

`PairModule` is not visible to `JointEnvironment.evaluate()`. Module identity,
module age, provenance, formation history, and relationship history cannot directly
change mission success probability.

The module changes outcomes only by determining which already-existing individual
and W4 relationship state is supplied to the existing controller.

No generic procedure interpreter or symbolic workflow executor is added here.
Resonance Field is unchanged.

## Claim boundary

A W5B-00 pass establishes only that W4 social state can be represented,
content-addressed, transported, restored, reset, and safely subjected to member
replacement. Behavioral value is tested separately in W5B-01 through W5B-05.
