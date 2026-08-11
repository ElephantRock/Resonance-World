# W6-00 — Inter-Field Mobility Architecture

W6 begins the Resonance World mobility program. Its first requirement is not a migration
experiment; it is an explicit lifecycle that makes migration effects causally separable
from the portability, relationship, and organization mechanisms already established in
W1–W5B.

## Audit finding

Before W6-00, World could export individual competence, recruit individuals or swarms,
retain W4 relationship state, capture W5B pair modules, and maintain W5 organization
state. It did **not** have a primitive that represented all of the following at once:

- an immutable home Field identity;
- a current operational Field;
- whether home affiliation survives movement;
- whether the agent is currently available to its home ecology;
- a migration/return event history;
- the exact agent-owned state carried out and returned.

Recruiting an exported capsule is therefore not equivalent to observing secondment,
brain drain, or brain circulation.

## W6-00 object boundary

`PortableAgentState` is the only payload accepted by an individual mobility contract.
It contains:

- `agent_id`;
- immutable `home_field_id`;
- intrinsic `practice_by_skill`;
- provenance references.

It intentionally excludes partner-specific models, pair-owned memory, `PairModule`
state, and organization-owned memory. Those assets have different owners and cannot be
silently relabeled as individual migrant state.

`MobilityRegistry` owns World-side location/affiliation state. It never mutates a
Resonance Field runtime. Source-field cost is represented by **availability**: while an
agent is away, World cannot select that agent for home-field work through the mobility
registry.

## Four transitions

### Secondment

The agent moves operationally to a destination Field while retaining home affiliation.
The same agent-owned portable state is carried unchanged. The agent is unavailable for
home work until an explicit return migration.

### Temporary migration

The agent moves to a destination Field and retains home affiliation, but is operationally
resident only at the destination. As with secondment, movement itself changes no skill or
success probability.

### Permanent migration

The agent moves to a destination Field and relinquishes home affiliation. Home identity
remains immutable for provenance and possible later return-migration analysis.

### Return migration

An away agent moves explicitly back to its immutable home Field and home affiliation is
restored. The return transition may receive a new `PortableAgentState` only when it:

- has the same agent identity;
- has the same immutable home Field;
- does not reduce existing practice;
- carries explicit destination-learning provenance when agent-owned state changed.

A round trip with no returned learning is byte-identical at the portable-state level.

## Causal invariants

W6-00 enforces the following boundaries:

1. Mobility alone does not change `practice_by_skill`.
2. Only current operational location controls World-side availability.
3. Home affiliation and operational location are separate state variables.
4. Individual mobility cannot carry relationship, pair-module, or organization memory.
5. Returned learning is an explicit provenance-bearing state update, not a mobility bonus.
6. `JointEnvironment.evaluate()` remains blind to migration mode, migration history,
   home identity, current Field, affiliation, and time away.
7. Resonance Field remains unchanged.

## Why the distinction matters

Without these separations, a future positive migration result could be caused by hidden
extra state, and a negative source-field effect could be simulated by directly damaging
Field internals. W6 instead treats movement as a resource-allocation intervention:
capability is temporarily or permanently unavailable at one location and available at
another. Learning acquired while away becomes a separate, observable return channel.

## Behavioral W6 sequence after W6-00

The architecture is intended to support a preregistered campaign with at least these
causal contrasts:

1. **W6-01 — Secondment:** destination value versus matched no-move control, including
   simultaneous source opportunity cost.
2. **W6-02 — Temporary migration:** longer absence with the same retained-home-affiliation
   boundary.
3. **W6-03 — Permanent migration:** source-field brain-drain effect and replacement
   latency after capability permanently leaves the source roster.
4. **W6-04 — Return migration:** return with versus without validated destination-acquired
   agent-owned learning.
5. **W6-05 — Brain circulation:** source recovery and capability gain after return,
   compared with never-moved and migration-with-no-learning controls.
6. **W6-06 — Mobility unit:** individual movement versus explicitly moving an intact W5B
   `PairModule`; pair state is carried only in the pair-unit arm.
7. **W6-07 — Post-freeze unseen replication:** new Fields and migration routes generated
   only after the protocol and thresholds are frozen.

The W6-06 pair-unit experiment must not be interpreted as robust higher-order module
composition: W5B-03 did not replicate that claim. It tests only whether moving an intact
validated pair preserves more capability than moving its members independently.

## W6-00 acceptance gate

Architecture acceptance requires executable tests showing that:

- all four transitions work;
- secondment/temporary migration retain home affiliation;
- permanent migration relinquishes it;
- return migration restores home location/affiliation;
- source/destination availability follows current location;
- movement without learning leaves portable state unchanged;
- explicit returned learning can update agent-owned practice with provenance;
- invalid identity/home/origin/destination transitions fail;
- pair/organization state has no input path into individual mobility;
- environment outcome laws remain mobility-blind.

No behavioral migration result is claimed by W6-00.
