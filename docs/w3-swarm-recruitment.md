# W3 — Swarm Recruitment & Relationship Capital

W3 tests whether two-agent swarms can be recruited from public developmental evidence and whether prior relationship history contributes transferable value beyond individual competence and simple skill complementarity.

## Scientific boundary

The campaign is restricted to the deterministic Resonance Field skill-practice model plus an explicit destination coordination law. It does not test general LLM teamwork, model-weight evolution, consciousness, or unrestricted autonomous organizations.

## Public/private state boundary

Public selection may use:

- individual life-history features;
- lossy dominant/secondary successful-skill labels;
- lossy pair-edge evidence derived from historical requester/winner interactions.

Selection may not read:

- either member's exact `practice_by_skill` vector;
- exact `coordination_exposure`;
- private home substrate/history;
- private reputation evidence.

Exact private practice and pair coordination state become available only after a pair has been selected for destination execution.

## Destination team law

A two-agent swarm receives the best available practice of either member for each required skill. It also receives a bounded coordination bonus based on the pair's frozen successful-collaboration exposure, minus a fixed team overhead penalty. The coordination mechanism is explicit and preregistered so its causal contribution can be ablated.

## Relationship-capital controls

W3 compares the relationship-aware recruited swarm against:

1. the best recruited individual;
2. a pair selected using the same public individual evidence but with relationship weight fixed to zero;
3. a pair selected after deterministic permutation of public relationship edges, while execution still uses each selected pair's true frozen relationship state;
4. an oracle upper bound selected with private practice and true relationship state.

All pair baselines use common deterministic destination draws for identical pair/mission identities. Therefore, selecting the same pair under two policies produces exactly the same outcome rather than sampling noise.

## Seven experiments

- W3-01 — Public pair-graph extraction and swarm-recruiter calibration
- W3-02 — Recruited swarm vs best recruited individual
- W3-03 — Recruited swarm vs competence-matched assembled pair
- W3-04 — Relationship ablation / shuffled-edge control
- W3-05 — Oracle pair upper bound
- W3-06 — Member-loss and mission-drift resilience
- W3-07 — Unseen swarm-recruitment replication

## Source cohorts

Discovery uses five new 12-agent Fields: seeds 121, 242, 363, 484, and 605. Calibration is restricted to 121/242/363; 484/605 remain held out.

Replication uses three additional 12-agent Fields: seeds 726, 847, and 968. These Fields are developed only after the W3-01 recruiter artifact has frozen.
