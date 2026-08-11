# W2 — Individual Ecological Recruitment Preregistration

## Question

Can Resonance World satisfy an external mission by recruiting a previously developed agent from public life-history evidence, with response-time performance and economics competitive with constructing a new mission-specific agent after the need becomes known?

## Scope

W2 is individual-agent only. It does not test swarm recruitment, organizations, inter-Field migration, return-to-home learning, shared private substrate transfer, or corporate memory.

## Source populations

W2 develops new Fields rather than reusing W1 realized populations.

- discovery: seeds 111, 222, 333, 444, 555; 12 agents each;
- recruiter calibration: 111, 222, 333;
- held-out discovery: 444, 555;
- unseen replication: 777, 888, 999; developed only after the recruiter is frozen.

All source development uses the same neutral immortal fast-learning Field architecture pinned by the W2 workflow. Resonance Field itself is not modified.

## Public/private boundary

The selector receives ordinary public W1 life-history features plus two lossy labels: the strongest and second-strongest successful home skill areas. It never receives the counts behind those labels.

The transferred capsule carries exact private `practice_by_skill`. That vector is invisible to the recruiter. Home-private substrate/history and home reputation are not transferred.

## Baselines

1. **Recruited** — selected from the ecology using only public evidence; carries pre-existing practice.
2. **Fresh** — same base controller, zero practice, same mission execution budget.
3. **Purpose-built** — same base controller, zero prior practice, receives a target-specific four-unit curriculum after mission reveal.
4. **Equal-development upper bound** — purpose-built agent receives target-specific practice equal to the recruited agent's accumulated practice exposure.

## Seven experiments

### W2-01 — Mission-conditioned recruiter calibration

Calibrate only the mission-fit coefficient on three training Fields and freeze the abstention threshold before any held-out outcomes.

### W2-02 — Recruited vs fresh

Held-out Fields 444/555. Require at least +2 percentage points pooled completion lift and positive lift in both held-out Fields.

### W2-03 — Recruited vs purpose-built

Require recruited success to be non-inferior within two percentage points and recruited response utility to be at least as high as purpose-built response utility.

### W2-04 — Equal-development upper bound

Give the purpose-built comparator target-specific practice equal to the recruited agent's accumulated practice. This is descriptive and establishes the value of perfect foresight; it is not required to lose.

### W2-05 — Recruit or abstain

Include supported and deliberately unsupported missions. The frozen confidence rule must reduce failure risk by at least five percentage points relative to always recruiting while retaining at least 50% coverage of supported missions.

### W2-06 — Mission drift

Recruit for an initial two-skill mission and evaluate the same agent through progressively broader three- and four-skill requirements without re-recruitment.

### W2-07 — Unseen replication

After recruiter freeze, develop Fields 777/888/999 and reveal an unseen four-way compositional mission family. No retuning. Require +2 point recruited-vs-fresh lift, non-inferiority to purpose-built, positive lift in at least two Fields, and at least 67% recruitment coverage.

## Economics

W2 reports response economics separately from lifecycle ecology cost. Purpose-built curriculum is charged after mission reveal; the recruited agent's historical development is reported as lifecycle practice exposure and is not hidden inside response cost.

Any scalar utility is secondary to raw mission success, response practice cost, latency, and failure statistics.

## Claim boundary

If W2-02, W2-03, W2-05, and W2-07 pass, the campaign may claim **replicated individual ecological recruitment in the current deterministic skill-practice model**. It may not claim general LLM-agent cognition, foundation-model weight transfer, or superiority under perfect foreknowledge.
