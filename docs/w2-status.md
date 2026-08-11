# W2 Campaign Status

Status: **PR EVIDENCE PASS — REPLICATED INDIVIDUAL ECOLOGICAL RECRUITMENT**

- Parent issue: #14
- PR: #15
- PR evidence run: `31460954422`
- Frozen recruiter SHA-256: `0c1094f6f467484f2df26afd56d1eba68aab56b6dfcf72c817eebded2aaaa8a0`

## Source populations

- discovery source Fields: seeds 111/222/333/444/555, 5 x 12 agents = 60 agents;
- calibration Fields: 111/222/333;
- held-out discovery Fields: 444/555;
- unseen replication Fields: 777/888/999, 3 x 12 agents = 36 agents;
- replication Fields were developed only after the recruiter was frozen.

## W2-01 — Mission-conditioned recruiter

The calibrated mission-fit coefficient was `alpha = 1.0`. Mean calibration success increased from 42.90% with `alpha = 0` to 60.62% at the frozen setting. The abstention threshold was frozen at 0.8324172952.

The recruiter can inspect public life-history features and lossy dominant/secondary successful-skill labels. It cannot inspect `practice_by_skill` or home-private substrate/history.

## W2-02 — Recruited vs fresh

- pooled completion lift: **+16.11 percentage points**;
- Field 444 lift: **+19.63 points**;
- Field 555 lift: **+12.59 points**;
- gate: **PASS**.

## W2-03 — Recruited vs purpose-built

- recruited mean success: **55.19%**;
- purpose-built mean success: **54.44%**;
- recruited response-utility delta: **+0.01941**;
- two-point non-inferiority margin satisfied;
- gate: **PASS**.

## W2-04 — Equal-development upper bound

When the purpose-built comparator received target-specific development equal to the recruited agent's accumulated practice exposure, it exceeded recruited success by **8.15 points** on average. This establishes the expected value of perfect foreknowledge and bounds the W2 claim: ecological recruitment is competitive under response-time constraints, not superior to perfectly targeted development with equal historical budget.

## W2-05 — Recruit or abstain

- always-recruit failure risk: **49.93%**;
- selective failure risk: **40.69%**;
- risk reduction: **9.24 points**;
- supported-mission coverage: **100%**;
- unsupported false recruitments: **0**;
- gate: **PASS**.

## W2-06 — Mission drift

The same recruited agent lost **8.89 percentage points** on average from the initial mission phase to the final broadened phase. Recruitment is therefore useful but not invariant to requirement drift.

## W2-07 — Unseen recruitment replication

The frozen recruiter was applied without retuning to unseen Fields 777/888/999 and an unseen four-way compositional mission family.

- recruited-vs-fresh pooled lift: **+18.46 points**;
- Field 777 lift: **+16.67 points**;
- Field 888 lift: **+13.70 points**;
- Field 999 lift: **+25.00 points**;
- recruited mean success: **56.36%**;
- purpose-built mean success: **52.28%**;
- non-inferior to purpose-built: **yes**;
- recruitment coverage: **100%**;
- gate: **PASS**.

## Conclusion

Within the current deterministic Resonance Field skill-practice model, a frozen mission-conditioned recruiter using only public life-history evidence can select previously developed agents that outperform fresh generic agents, remain competitive with a mission-aware purpose-built response baseline, abstain on unsupported work, and replicate on new Fields and an unseen higher-order mission family.

The result does not establish general LLM-agent cognition, foundation-model weight transfer, or superiority to purpose-building under perfect foreknowledge. An authoritative `main` run is still required before Issue #14 is closed.
