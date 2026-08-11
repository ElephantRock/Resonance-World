# W7 Competing Organizations & Coopetition — Status

Status: **MIXED / PRIMARY ORGANIZATION-CONSISTENCY GATE NOT REPLICATED**

First complete synthesis: **`w7_discovery_not_replicated`**.

- Parent issue: #64
- Implementation PR: #65
- Architecture gate: W7-00 / #61 / PR #62
- Discovery: 3 fresh Fields / 36 agents
- Post-freeze replication: 3 additional fresh Fields / 36 agents in a separate PostgreSQL evidence store
- Organizations: `org-alpha`, `org-beta`, `org-gamma`
- Budget: 220 credits per organization per allocation arm
- Public offers: top 8 candidates per organization
- Service trials: 128 per organization/shared mission
- Effect/equivalence band: ±2 percentage points
- Resonance Field: pinned at `0914a21249261fe61e02c5191f4a36df416c672f`; Field was not modified.

## W7-01 — Rival scarcity vs non-rival recruitment

The exact same public-evidence offers were used in both arms. The rival arm enforced one
exclusive service right per agent; the non-rival counterfactual allowed each organization
to settle independently against the same candidate pool and budget.

Discovery:

- mean non-rival success: **33.3333%**
- mean rival success: **35.6771%**
- pooled competition effect: **+2.34375 pp**
- organization effects:
  - `org-alpha`: **0.0000 pp**
  - `org-beta`: **−1.5625 pp**
  - `org-gamma`: **+8.59375 pp**
- pooled classification: **positive**
- positive organizations: **1/3**

Unseen replication:

- mean non-rival success: **39.0625%**
- mean rival success: **43.7500%**
- pooled competition effect: **+4.6875 pp**
- organization effects:
  - `org-alpha`: **0.0000 pp**
  - `org-beta`: **0.0000 pp**
  - `org-gamma`: **+14.0625 pp**
- pooled classification: **positive**
- positive organizations: **1/3**

W7-07 replication gate: **FAIL**.

The preregistered rule required a non-null discovery effect to retain sign, exceed the
2 pp band pooled, and have matching sign in at least 2/3 organizations on unseen
replication. The pooled uplift replicates, but the benefit is concentrated in
`org-gamma`; only 1/3 organizations is positive. This is therefore not a demonstrated
general competitive advantage across organizations.

## W7-02 — Competitive pressure and concentration

Competition is **active in both phases**.

Discovery:

- contested offered agents: **5 / 16 = 31.25%**
- contracts: **9**
- roster sizes: **3 / 3 / 3**
- contract-share HHI: **0.3333**
- source-Field HHI: **0.3580**
- mean winning bid: **62.1111 credits**
- spend: alpha **194**, beta **177**, gamma **188**
- preferred-candidate loss: alpha **0**, beta **1**, gamma **1**

Replication:

- contested offered agents: **7 / 13 = 53.85%**
- contracts: **9**
- roster sizes: **3 / 3 / 3**
- contract-share HHI: **0.3333**
- source-Field HHI: **0.4321**
- mean winning bid: **65.0 credits**
- spend: alpha **200**, beta **200**, gamma **185**
- preferred-candidate loss: alpha **1**, beta **0**, gamma **3**

The market is therefore not a nominal competition label: multiple organizations demand
the same agents, scarcity changes preferred acquisition sets, and budgets are actually
spent under exclusive contracts.

## W7-03 — Overlap pressure

Overlapping demand increases both contestation and price relative to the frozen
disjoint-demand control.

Discovery:

- overlap contested share: **31.25%**
- disjoint contested share: **15.79%**
- contested-share increase: **+15.46 pp**
- overlap mean winning bid: **62.1111**
- disjoint mean winning bid: **60.6667**
- price pressure: **+1.4444 credits**

Replication:

- overlap contested share: **53.85%**
- disjoint contested share: **46.67%**
- contested-share increase: **+7.18 pp**
- overlap mean winning bid: **65.0**
- disjoint mean winning bid: **62.0**
- price pressure: **+3.0 credits**

This is a market-pressure result only. Prices do not enter any mission success law.

## W7-04 — Source extraction: REPLICATED POSITIVE

Rival-contracted agents were removed from their source Field's available evaluation
roster, with each Field compared to its own no-recruitment service frontier.

Discovery:

- pooled source loss: **+3.7326 pp**
- source effects:
  - seed 1663: **+1.8877 pp**
  - seed 1789: **0.0000 pp**
  - seed 1913: **+9.3101 pp**
- positive source Fields: **2/3**
- classification: **positive / extraction regime**

Replication:

- pooled source loss: **+4.0750 pp**
- source effects:
  - seed 2039: **+3.7754 pp**
  - seed 2161: **+8.4495 pp**
  - seed 2287: **0.0000 pp**
- positive source Fields: **2/3**
- classification: **positive / extraction regime**

W7-07 extraction gate: **PASS**.

The tested competitive institution reproducibly transfers capability away from some
source societies. Organization-level gains cannot be used to erase this source cost.

## W7-05 — Coopetition: REPLICATED NEGATIVE

Rival contracts were frozen first. Each coalition then combined one already-contracted
lead contributor from one organization and one already-contracted support contributor
from another. Ownership, budgets, and organization memory remained separate. Coalition
performance was compared with the best standalone organization on the same mission and
draws.

Discovery:

- pooled coalition effect: **−4.6875 pp**
- alpha + beta: **−1.5625 pp**
- beta + gamma: **−3.1250 pp**
- gamma + alpha: **−9.3750 pp**
- negative missions: **3/3**
- classification: **negative**

Replication:

- pooled coalition effect: **−5.2083 pp**
- alpha + beta: **−5.46875 pp**
- beta + gamma: **0.0000 pp**
- gamma + alpha: **−10.15625 pp**
- negative missions: **2/3**
- classification: **negative**

W7-07 coopetition classification gate: **PASS**.

Under this mission-bounded service-sharing contract, cooperation between otherwise
competing organizations does not create surplus. It reproducibly underperforms the best
standalone organization. This is not evidence against all cooperation mechanisms; it is
a negative result for the specific W7 contract and mission regime.

## W7-06 — Contribution-quality / withholding stress

Support-side withholding was frozen before outcomes. The support organization replaced
its best required-skill contributor with its next-best contracted member when available.

Discovery:

- pooled withholding cost: **+13.5417 pp**
- mission costs: **+3.90625 / +28.125 / +8.59375 pp**

Replication:

- pooled withholding cost: **+5.2083 pp**
- mission costs: **0 / 0 / +15.625 pp**

This is a descriptive fragility result, not a primary W7 gate. It shows that the already
underperforming coalition mechanism can also be highly sensitive to contributor quality.

## W7-07 — Post-freeze unseen replication

Primary gates:

- competition active in both phases: **PASS**
- W7-01 organization-consistency replication: **FAIL**
- W7-04 extraction classification replication: **PASS**
- W7-05 coopetition classification replication: **PASS**

Overall status: **`w7_discovery_not_replicated`**.

The failure is localized to the W7-01 generality criterion. The pooled competition
uplift is positive in both phases but concentrated in one organization, so it cannot be
reported as a general cross-organization benefit.

## First complete evidence

Preregistered head:

- head: `8304950fa6cb268573e545c797510c769625cf55`
- hosted CI run: `31522975797`
- Ruff: **PASS**
- pytest: **PASS**
- complete W7 campaign: **PASS**
- W4-00 Architecture Audit: **PASS**
- W4A Joint-Learning Architecture: **PASS**
- W4A.1 General Teamwork: **PASS**
- evidence artifact: `9113818764`
- artifact digest: `sha256:9214a09c18714f950560019a4c92c964b14db223d4db1fcecb1e0d24dcb9be0e`
- discovery JSON: `sha256:069425c2e149e5bd0328f0f5073ff4364d952e548075771c94d829d0c2a0c6bf`
- W7-07 replication JSON: `sha256:bb17c7d892fb0522742eeae9c06705e7e10fa885c97955383db12e397c4e1410`
- synthesis JSON: `sha256:8e90bbfa1dbc2100cd170cc169458e0a48c8a4f5de3957dae07e543534053d3d`

The final redundant portable-state digest equality inside the campaign evaluator is not
used as scientific evidence; W7-00's independent architecture tests establish that
market settlement and coalition preparation do not mutate portable state or
organization memory. No post-outcome scientific parameter is changed in response to
this first result.

## Interpretation boundary

The tested world has a genuine competitive talent market, but it is **not yet a generally
beneficial coopetitive ecology**:

- competition redistributes scarce talent and produces measurable price pressure;
- the pooled organization-performance uplift is concentrated rather than general;
- source extraction is reproducible;
- selective cooperation under the tested contract creates no surplus and is
  reproducibly negative.

The negative/mixed boundaries are retained. The next acceptance step is exact-head
reproduction of these outputs without retuning any scientific parameter.
