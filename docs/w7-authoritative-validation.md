# W7 Authoritative Validation Record

W7 — competing cross-field organizations and mission-bounded coopetition — is complete.

Authoritative scientific status: **`w7_discovery_not_replicated`**.

## Repository state

- Architecture issue: #61 — completed
- Architecture PR: #62 — merged
- Campaign issue: #64 — completed
- Campaign PR: #65 — merged as `134ccca5bf5864d8b876a3fc6ca4d5dc1c5ce375`
- Post-merge validation PR: #66 — merged as `80d29ede0ee8098bb6b3af3d7eb0d8a061bc3f10`
- Resonance Field pin: `0914a21249261fe61e02c5191f4a36df416c672f`
- Field modification for W7: **none**

## Authoritative post-merge execution

The W7 campaign branch was reset to merged `main`; its only additional change was a
documentation marker. Hosted CI then regenerated both source cohorts from Field.

- validation head: `1413cedec68da56057aced1578d609eedb31e94e`
- CI run: `31524167102`
- Ruff: **PASS**
- pytest: **PASS**
- W4-00 Architecture Audit: **PASS**
- W4A Joint-Learning Architecture: **PASS**
- W4A.1 General Teamwork: **PASS**
- complete W7 campaign: **PASS**
- evidence artifact: `9114250996`
- artifact digest:
  `sha256:7349b92ba0381fdc3b159fc3202178e94fce569593b6ead0c9764efac0a86067`

The execution independently regenerated:

- discovery: Fields 1663 / 1789 / 1913, 36 agents total;
- replication: Fields 2039 / 2161 / 2287, 36 additional agents in a fresh PostgreSQL
  evidence store.

## Reproducibility identity

Fresh Field executions produce fresh immutable checkpoint/evidence hashes. Therefore
`offer_digest`, `market_digest`, source checkpoint hashes, and whole artifact ZIP hashes
are expected to differ between complete executions.

Across accepted W7 runs, all decision-relevant source state is identical:

- agent and Field identities;
- public recruitment features;
- public dominant/secondary mission labels;
- private `practice_by_skill` vectors.

Removing only the two explicitly provenance-bearing phase fields `offer_digest` and
`market_digest` gives the canonical scientific-result payloads:

- discovery:
  `sha256:6bba562b8b766747830917a7a922a5b7feb1e6bbc46004cb1e1c36f3b67af1eb`
- unseen replication:
  `sha256:eee38e9ce7c859bdd64a557029f74b2670556bb350d72fb6e9af5357c71d9d35`
- synthesis full file:
  `sha256:8e90bbfa1dbc2100cd170cc169458e0a48c8a4f5de3957dae07e543534053d3d`

These hashes reproduced across the first scientific execution, documentation-only
pre-merge reproductions, and the authoritative merged-state validation. The synthesis
status remained unchanged.

## Accepted findings

### W7-01 — Competition performance: NOT ORGANIZATION-GENERAL

Pooled rival-minus-nonrival performance was positive in both phases:

- discovery: **+2.34375 pp**
- replication: **+4.6875 pp**

However only one of three organizations had a positive effect in either phase. The
preregistered non-null replication rule required matching sign in at least two of three
organizations.

**Gate: FAIL.**

The result supports a concentrated winner effect, not a general performance advantage
from organization competition.

### W7-02 / W7-03 — A real scarce talent market exists

Competition was active in both phases. Overlapping organization demand increased
contested talent and winning prices relative to the frozen disjoint-demand control.

This establishes allocation/price pressure only. Market variables never enter mission
success laws.

### W7-04 — Source extraction: REPLICATED POSITIVE

Pooled source-field capability loss after rival recruitment:

- discovery: **+3.7326 pp**, 2/3 Fields positive
- replication: **+4.0750 pp**, 2/3 Fields positive

**Gate: PASS / extraction regime supported.**

The tested institution can therefore produce organization-side competition while
reproducibly degrading some source societies.

### W7-05 — Coopetition: REPLICATED NEGATIVE

Mission-bounded coalitions used only already-contracted agents and preserved separate
organization ownership/memory. Compared with the best standalone organization on the
same mission/draws:

- discovery: **−4.6875 pp**, 3/3 missions negative
- replication: **−5.2083 pp**, 2/3 missions negative and one null

**Negative-classification replication gate: PASS.**

The tested cooperation contract creates no general cooperative surplus. The finding is
specific to this coalition mechanism and mission regime, not a claim that cooperation
is intrinsically harmful.

### W7-06 — Contribution-quality fragility

Support-side contribution degradation produced pooled costs of:

- discovery: **+13.5417 pp**
- replication: **+5.2083 pp**

This remains descriptive rather than a primary W7 gate.

## Interpretation

W7 establishes an artificial inter-society economy with genuine scarce-talent
competition, budget-constrained exclusive contracting, price pressure, and explicit
cross-organization cooperation. It does **not** establish a generally beneficial
coopetitive world.

The tested institution instead shows three simultaneous properties:

1. competitive gains can be concentrated in a single organization;
2. source-society extraction can replicate even when pooled organization performance
   rises;
3. simple mission-bounded service sharing between rivals can reproduce a negative
   coalition effect.

These boundaries are part of the result and were not tuned away.

## Cleanup

The branch-specific W7 hosted campaign hook is removed after this record. The ordinary
repository CI returns to Ruff + pytest only. W7 campaign code/configuration remains in
the repository as a reproducible historical experiment, but it is no longer executed
on unrelated future pull requests.
