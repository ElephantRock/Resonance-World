# W4A.1 — General Teamwork State Channel

Status: **ARCHITECTURAL EXTENSION / NO TEAMWORK-SKILL CLAIM**

Parent issue: #24

## Purpose

W4A made partner-specific coordination state representable. W4A.1 closes a second representational gap: the W4 factorial must also allow an agent to learn a coordination convention that can be carried to a new partner.

Without that channel, the outcome `C1 ≈ C2 > C3` would be impossible by construction and W4 could not distinguish partner-specific relationship capital from general teamwork skill.

## New state

`GeneralTeamworkModel` is owned by one agent and is not indexed by partner identity. It records, by coordination context:

- successful roles previously taken by the agent;
- same-role collision failures;
- total joint-episode exposure.

This state is separate from:

- `IndividualState.practice_by_skill`;
- partner-specific `PartnerModel` instances;
- pair-owned `SharedPairMemory`.

It can be reset independently.

## Decision-only influence

A controller may use a learned general successful role, or a learned collision convention when communication is available, while coordinating with a partner it has never encountered before.

`JointEnvironment.evaluate()` remains unchanged and accepts no teamwork, partner, pair-memory, relationship-history, or coordination-exposure state.

Therefore W4A.1 still prohibits:

`teamwork_history -> direct success bonus`

## Scientific boundary

W4A.1 proves only that the four-condition W4 inference map is representable:

- C1 `A+B`: partner-specific + general teamwork state;
- C2 `A+B'`: general teamwork state carried by A, no A↔B' pair history;
- C3 `A'+B'`: neither treated member carries formation history;
- C4 `A`: individual baseline.

Whether any of those states actually improve held-out performance remains an empirical W4 question.