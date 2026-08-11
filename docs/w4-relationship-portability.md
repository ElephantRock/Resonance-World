# W4 — Relationship Formation & Portability

Status: **PROTOCOL FROZEN / EXECUTION PENDING**

Parent issue: #26

## Research question

Can repeated fixed-pair joint experience create productive coordination state that is separable into partner-specific relationship capital and partner-independent teamwork skill, and does either effect survive transfer to novel task content and unseen source populations?

## Architecture

W4 runs on the W4A/W4A.1 World-side joint-learning substrate. Resonance Field supplies only developed individual competence (`practice_by_skill`) and remains unchanged.

The environment outcome law does not read relationship state, teamwork state, shared memory, partner models, collaboration count, or relationship age. Learned coordination state may change joint actions only.

## Fresh cohorts

Pinned Field revision: `0914a21249261fe61e02c5191f4a36df416c672f`.

Discovery source Fields: 137, 258, 379, 491, 612; 12 agents each.

- W4-01/W4-02 calibration/formation fields: 137, 258, 379.
- W4-03 through W4-06 held-out discovery fields: 491, 612.

W4-07 replication source Fields: 733, 854, 975; these are generated only after the discovery job completes.

## Fixed assignment

Within each Field, agent identity is deterministically shuffled from `(field_id, agent_id)` before any joint outcome exists.

- first six agents: treatment population;
- remaining six: untreated external controls;
- treatment agents form three fixed original pairs;
- no pair dissolves after poor performance.

The same six treatment agents are then deterministically re-paired for C2. No original pair is retained.

## W4-01 — Formation depth

Formation depths are frozen at 0, 2, 6 and 12 joint episodes per original pair. Deep formation is preregistered as 12 episodes and is not selected after observing W4-01.

The formation-probe missions share coordination contexts but use task combinations distinct from the actual formation sequence.

## W4-02 — Coordination learning curve

Registered checkpoints are 0, 1, 2, 4, 6, 8 and 12 episodes. W4-02 measures the trajectory; it does not tune the W4-03 treatment depth.

## W4-03 — C1/C2/C3/C4 factorial

### C1 — original experienced pair

The six treatment agents retain both partner-specific state and partner-independent teamwork state and execute with their original formation partners.

### C2 — experienced strangers

The exact same six experienced agents are re-paired so no C2 pair has shared history. Their general teamwork state remains. Pair-specific state for the new pairing is absent.

### C3 — coordination reset

The exact same agents and C2 pairing are used with a fresh coordination-state store. Individual practice is unchanged. This removes both general teamwork state and pair-specific state.

### C4 — individual ceiling

For each original pair and mission, the stronger individual on the registered two-role probability product executes both roles. Two role-actions are charged, matching the pair's total action count.

## Primary causal effects

Partner-specific effect uses a compatibility-adjusted difference in differences:

`(C1_post - C1_pre) - (C2_post - C2_pre)`

C1 and C2 use the same six agents, so composition is exactly held fixed. Pre-treatment probes quantify intrinsic original-vs-rotated pair compatibility before relationship formation.

General teamwork effect:

`C2_post - C3_post`

C2 and C3 use the same agents and same rotated pairing. Only retained coordination state changes.

Threshold: 2 absolute percentage points.

Classification:

- partner > 2pp, general <= 2pp: `partner_specific`;
- partner <= 2pp, general > 2pp: `general_teamwork`;
- both > 2pp: `both`;
- neither > 2pp: `neither`.

## W4-04 — Relationship reset

Original experienced pairs are evaluated under:

- full state;
- pair-specific reset preserving general teamwork state;
- full coordination reset preserving individual competence.

This is now an operational ablation because W4A made the state components independently manipulable.

## W4-05 — State decomposition

Original pairs are also evaluated after independently removing:

- partner-conditioned models only;
- pair-shared episodic memory only.

These are mechanism decomposition results, not additional selection criteria.

## W4-06 — Transfer boundary

Primary transfer uses task combinations never used during formation while preserving the registered coordination contexts. This asks whether coordination learning transfers across task content.

A secondary stress condition renames the contexts entirely. Because the current models are context-indexed, this tests the boundary of context generalization and is not required to match same-context transfer.

## Communication and compute controls

Every pair condition receives the same one-bit communication policy. Communication bandwidth is therefore not a treatment.

Each pair trial uses two role-actions. C4 also receives two role-actions, but from one identity. Results report pair effects separately from individual competence; W3 already established the general two-agent swarm advantage.

## W4-07 — unseen replication

The W4 protocol, formation depth, effect threshold, assignment algorithm, mission contexts and evaluation law are frozen before replication sources exist.

Replication passes only if:

1. the qualitative discovery classification reproduces;
2. every effect required by that classification is positive in at least two of three unseen Fields;
3. if discovery is `neither`, both pooled replication effects remain within the 2-point threshold.

All four classifications are scientifically valid outcomes.