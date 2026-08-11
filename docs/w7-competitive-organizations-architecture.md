# W7-00 — Competitive Organizations & Coopetition Architecture

W7 introduces competition **between** persistent cross-field organizations. The first
requirement is not a claim that competition is beneficial. It is an explicit World-side
institution that makes scarce talent allocation and selective cooperation causally
identifiable.

## Existing substrate

Before W7-00, Resonance World already supports:

- evidence-backed portable individual capability and recruitment;
- explicit relationship state and reusable PairModules;
- persistent organization identity, roster replacement, and organization-owned memory;
- explicit inter-field mobility and returned agent-owned learning.

What was missing was an arbiter for simultaneous claims by multiple organizations over
the same portable agent. Roster membership alone cannot represent scarcity, bidding,
contract price, or ownership of time-bounded service rights.

## W7-00 boundary

`TalentMarket` is a World-level ledger. It registers:

- portable agents;
- existing W5A `OrganizationState` objects;
- fixed organization budgets;
- public-evidence `TalentOffer`s;
- exclusive `TalentContract`s;
- mission-bounded `CooperationAgreement`s.

The market does not modify Resonance Field, intrinsic agent practice, organization
memory, or mission success probabilities.

### Service rights are not identity

A `TalentContract` grants one organization the exclusive right to deploy one registered
portable agent during one market window. It does not change:

- the agent's immutable home Field identity;
- the agent's `practice_by_skill`;
- the organization's identity or memory;
- the agent's ownership of its portable state.

This is deliberately narrower than permanent employment or migration. W6 mobility can
be composed with W7 contracts later when physical location becomes part of the
behavioral design.

## Deterministic sealed-bid allocation

For W7-00 the institution is intentionally simple:

1. every offer names an organization, agent, market window, positive integer bid, and
   public evidence provenance;
2. offers above the organization's frozen window budget are rejected;
3. agents are settled in deterministic agent-ID order;
4. offers for an agent rank by descending bid, then organization ID, then offer ID;
5. the highest-ranked offer affordable from the organization's remaining balance wins;
6. the winner pays its own bid;
7. exactly one contract may exist for an agent/window;
8. an organization can win multiple contracts only while its budget remains sufficient.

Agent-ID settlement order is part of the architecture contract. It is not presented as
an economically optimal mechanism; it exists to make later competition experiments
replayable and auditable.

## Public/private information boundary

`TalentOffer` contains no private practice vector or portable state. Later W7 bidding
policies may consume W2-style public recruitment evidence, but exact
`practice_by_skill` becomes available only after an agent has been allocated for
execution/evaluation.

The market therefore cannot use private capability as an oracle when deciding who wins
scarce talent.

## Coopetition

`CooperationAgreement` allows organizations that already own distinct contracts in the
same window to contribute selected contracted agents to one shared mission.

The agreement:

- requires at least two distinct organizations;
- rejects duplicate agent contributions;
- verifies that every contributed agent is actually contracted to the named
  contributing organization in that window;
- returns a temporary `CoalitionDeployment` containing only the contributed portable
  individual states;
- leaves every contract, budget, organization identity, roster, and organization memory
  unchanged.

Cooperation therefore shares **service**, not ownership or institutional memory.
PairModule transport is intentionally excluded from this first coalition primitive:
W5B and W6 did not establish route-general higher-order modular composition.

## Hard causal boundary

Market or coalition state is never an input to `OrganizationEnvironment.evaluate()` or
`JointEnvironment.evaluate()`. Mission outcome laws do not receive:

- bid or contract price;
- budget;
- number of rivals;
- market concentration;
- contract history;
- coalition identity;
- organization count.

Any later behavioral effect of competition must therefore arise through who is
available to which organization, not because the environment rewards competition.

## Architecture gates

W7 behavioral work is blocked until hosted CI verifies:

- deterministic exclusive allocation under rival bids;
- deterministic tie-breaking;
- no budget overspend;
- no double service rights;
- settlement leaves agent practice and organization memory unchanged;
- public offer schemas contain no private-practice channel;
- valid cooperation preserves ownership/budget/memory;
- invalid coalition ownership and duplicate contribution are rejected;
- market and coalition variables remain absent from mission outcome-law signatures;
- ledger snapshots and SHA-256 digests are deterministic.

## Next behavioral sequence

After W7-00 is authoritative on `main`, W7 can preregister experiments for:

1. non-rival recruitment vs genuine talent scarcity;
2. talent concentration and organizational differentiation under competition;
3. bid/wage pressure under overlapping mission demand;
4. source-field extraction costs when multiple organizations recruit from the same
   societies;
5. mission-specific cooperation between otherwise competing organizations;
6. defection/withholding controls and coalition value accounting;
7. post-freeze unseen replication on newly developed Fields.

Raw organization-level performance, source-field cost, talent concentration, and market
payments must remain separately visible. A high-performing winner combined with severe
source collapse or monopoly concentration is not automatically a successful World.
