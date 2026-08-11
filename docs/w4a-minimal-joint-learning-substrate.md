# W4A — Minimal Joint-Learning Substrate

Status: **ARCHITECTURAL EXTENSION / NO RELATIONSHIP-CAPITAL CLAIM**

Parent issue: #21

## Why W4A exists

W4-00 established that the current Resonance Field runtime has no native persistent pair-level learned state. W4A therefore adds the minimum relationship-learning affordances in **Resonance World**, leaving Resonance Field unchanged.

The claim boundary is explicit:

> W4A makes partner-specific learning representable and independently manipulable. It does not establish that such learning is useful, emergent, portable, or superior to competence-only composition.

Those are W4 behavioral questions.

## State decomposition

### Individual state

`IndividualState.practice_by_skill`

This remains separate from every relationship object and represents the transferred intrinsic competence established by W1/W2.

### Partner-conditioned state

`PartnerModel`

Each agent may retain observations indexed by a specific partner and task context. The model records observed partner role choices. It does not contain a success multiplier.

### Pair-owned state

`SharedPairMemory`

A pair owns an episodic log of previous joint missions, actions and outcomes. It is serialized independently from both agents' individual practice and can be cleared without changing their competence.

### Communication policy

`CommunicationPolicy`

Communication bandwidth is explicit so experienced and stranger pairs can receive exactly the same channel in later experiments.

## Joint execution

A `JointMission` requires complementary `lead` and `support` actions. Both agents choose an action. If both choose the same role, the joint task fails coordination.

The generic `JointController` may consult:

- its own individual competence;
- a partner-conditioned prediction model;
- the pair's prior shared episodes;
- the explicitly bounded communication channel.

After execution, both partner models and the pair memory observe the episode.

## No-direct-bonus invariant

`JointEnvironment.evaluate()` does **not** receive `RelationshipStateStore`, `PartnerModel`, `SharedPairMemory`, relationship age, collaboration count, or W3-style `coordination_exposure`.

Its outcome depends only on:

1. the mission;
2. the two chosen roles;
3. each agent's individual skill practice;
4. a deterministic exogenous draw from the registered seed.

Therefore relationship history can affect success only indirectly by changing decisions.

W4A explicitly rejects mechanisms equivalent to:

`relationship_history -> success bonus`

## Independent ablations now possible

The architecture makes the following later W4 treatments operationally meaningful:

- reset both partner-conditioned models while preserving individual practice and pair memory;
- clear pair-shared episodic memory while preserving individual practice and partner models;
- clear both relationship components while preserving both agents' intrinsic practice;
- hold communication bandwidth equal while varying shared history.

These manipulations were not meaningful before W4A.

## Validation demonstration

The hosted W4A validation includes a deliberately symmetric pair whose members initially prefer the same role. With zero communication bandwidth and no relationship history, they collide. After the failed joint episode is recorded, their next decisions can differ because the shared history supplies a coordination observation.

This demonstration proves only that the architectural state can influence decisions. It is **not** evidence that repeated shared experience produces statistically positive or portable relationship capital.

## Next behavioral campaign

After W4A validation, W4 should be preregistered around the four-condition factorial:

- **C1:** original experienced pair `A+B`;
- **C2:** experienced member with competence-matched stranger `A+B'`;
- **C3:** competence-matched strangers `A'+B'`;
- **C4:** matched individual `A`.

Required controls remain:

- fixed pairing during formation;
- pre-treatment compatibility measurement;
- novel transfer task families;
- equal communication bandwidth;
- per-agent and total-team compute accounting;
- no direct relationship reward;
- post-freeze unseen replication.
