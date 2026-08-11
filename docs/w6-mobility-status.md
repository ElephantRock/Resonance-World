# W6 Mobility Campaign Status

Status: **MIXED / PRIMARY MOBILITY CLASSIFICATIONS NOT FULLY REPLICATED**

Final synthesis status from the first complete hosted campaign: **`w6_discovery_not_replicated`**.

- Parent issue: #55
- Implementation PR: #56
- Discovery: 6 fresh Fields / 72 agents / 3 home→host routes
- Post-freeze replication: 6 additional Fields / 72 agents / 3 new routes
- Service trials: 128 per window
- Destination learning: 12 explicit episodes
- Source recovery cap: 24 local episodes
- Effect/equivalence band: ±2 absolute percentage points
- Individual probability law: W1 portability law (base 0.38, practice gain 0.14, cap 0.90)
- Resonance Field pinned at `0914a21249261fe61e02c5191f4a36df416c672f`; Field was not modified.

## W6-01 — Secondment accounting

Discovery pooled immediate effects:

- mean source loss: **+1.5721 pp**
- mean host gain: **+0.6499 pp**
- mean world-total change: **−0.9222 pp**
- source-loss routes: **2/3**
- host-gain routes: **2/3**

Unseen replication:

- mean source loss: **+2.5046 pp**
- mean host gain: **+2.2229 pp**
- mean world-total change: **−0.2818 pp**
- source-loss routes: **3/3**
- host-gain routes: **2/3**

Interpretation: moving a publicly selected agent can create a real source opportunity cost, but host gain is heterogeneous and does not automatically exceed that cost. W6 therefore publishes source and host effects separately rather than treating mobility as intrinsically world-positive.

## W6-02 — Mobility-mode leakage control: PASS

Secondment and temporary migration used the same identity/location movement, no learning, and identical service evaluation. First-window home and host outputs were exactly identical in every discovery and replication route.

This is the expected negative control: lifecycle metadata did not leak into the outcome law.

## W6-03 — Permanent migration / brain drain: NO PERSISTENT BRAIN DRAIN UNDER LOCAL RECOVERY

The preregistered brain-drain effect is post-recovery persistent source loss:

`pre-move home frontier - home frontier after the fixed local recovery curriculum`

Discovery:

- pooled persistent source loss: **−5.2365 pp**
- route effects: **−8.3086 / −3.3677 / −4.0332 pp**
- classification: **negative**
- all 3 routes recovered within the 24-episode cap
- mean replacement latency: **3.67 episodes**
- immediate source loss before recovery: **+1.5721 pp**

Unseen replication:

- pooled persistent source loss: **−4.8514 pp**
- route effects: **−1.9028 / −5.2768 / −7.3747 pp**
- classification: **negative**
- all 3 routes recovered
- mean replacement latency: **3.00 episodes**
- immediate source loss before recovery: **+2.5046 pp**

W6-07 classification gate: **PASS**.

A negative persistent-loss value means the fixed local curriculum ultimately pushed the best remaining source roster above its own pre-migration service frontier. This does not erase the measured short-run absence cost; it means the preregistered persistent brain-drain claim is not supported under the tested recovery mechanism.

## W6-04 — Return migration / returned learning: REPLICATED POSITIVE

Both arms received the same 12 destination-learning episodes. The only difference at return was whether the acquired agent-owned state was carried home or discarded.

Discovery:

- pooled returned-learning effect: **+3.0377 pp**
- route effects: **+4.0151 / +2.1857 / +2.9123 pp**
- positive routes: **3/3**
- classification: **positive**

Unseen replication:

- pooled returned-learning effect: **+4.2531 pp**
- route effects: **+3.6878 / +4.9144 / +4.1570 pp**
- positive routes: **3/3**
- classification: **positive**

W6-07 classification gate: **PASS**.

Supported claim: destination-acquired **agent-owned portable learning** can return to the source ecology and improve its service frontier. This is a causal returned-learning result, not an implicit migration bonus: the no-learning movement state is byte-identical, and the learned state requires explicit destination provenance.

## W6-05 — Brain circulation: SUPPORTED IN BOTH PHASES

The preregistered brain-circulation gate requires:

1. pooled W6-04 returned-learning effect > +2 pp;
2. positive returned-learning effect in at least 2/3 routes;
3. pooled learned-return home performance no worse than 2 pp below its own pre-move baseline.

Discovery and replication satisfy all three conditions. Learned-return performance is above the corresponding pre-move home frontier by the same +3.0377 pp and +4.2531 pp returned-learning effects.

Supported interpretation: under the tested explicit destination curriculum and return contract, mobility can operate as **brain circulation** rather than one-way extraction.

This does not imply that every movement route is beneficial: W6-01 still observes source opportunity costs and heterogeneous host gains while the agent is away.

## W6-06 — Mobility unit / PairModule: DISCOVERY POSITIVE, ROUTE-CONSISTENCY NOT REPLICATED

The same two agents were moved in both arms. The treatment carried their intact W5B relationship state; the control reset relationship state. Communication and destination draws were paired.

Discovery:

- pooled intact-pair mobility effect: **+15.3646 pp**
- route effects: **0.0000 / +21.8750 / +24.2188 pp**
- positive routes: **2/3**
- classification: **positive**

Unseen replication:

- pooled effect: **+7.0313 pp**
- route effects: **0.0000 / +21.0938 / 0.0000 pp**
- positive routes: **1/3**
- pooled classification: **positive**
- preregistered route-consistency requirement: at least 2/3 routes positive
- W6-07 gate: **FAIL**

The threshold and route rule were not changed. W6 therefore does **not** establish a route-general pair-mobility advantage, even though one replication route preserved a large positive relationship-state effect.

This experiment does not test higher-order module composition; W5B-03 already failed that separate claim.

## W6-07 — Post-freeze unseen replication

Primary gates:

- W6-02 mobility leakage control: **PASS**
- W6-03 permanent-migration classification: **PASS**
- W6-04 returned-learning classification: **PASS**
- W6-06 PairModule mobility classification + route consistency: **FAIL**

Overall W6 primary replication gate: **FAIL**.

Final status: **`w6_discovery_not_replicated`**.

The failure is localized to the PairModule mobility route-consistency criterion. The individual mobility findings—no mobility-state leakage, rapid local source recovery, and positive returned learning / brain circulation—replicated on the new Fields.

## Evidence

First complete scientific execution:

- head: `97a286c1ff9b24ecc3b1b930c77f3169fe8fc3ce`
- hosted CI run: `31493079999`
- W6 campaign job: **PASS**
- standard CI on that head: Ruff-only formatting failure; no scientific failure
- evidence artifact: `9101858163`
- artifact digest: `sha256:71c75f3b4b9a4c185e867cb8766584076747e4762ec7a9c69e7da4897e78a432`

Corrected exact head (formatting/test-layout only):

- head: `fceaf2d6dc00aaa63bf887230b63038001f7568d`
- hosted CI run: `31493535912`
- Ruff: **PASS**
- pytest: **PASS**
- complete W6 campaign: **PASS**
- evidence artifact: `9102041281`
- artifact digest: `sha256:f01816d6e6dafcbf389fd72ecc7c4c74c203bf43e38b61fc208d25de2fe546e1`
- discovery JSON SHA-256: `111d956bae44db8c5ae2a261cc657c5fe1ac77acd6cfa6946a20749ce3cf691a`
- W6-07 replication JSON SHA-256: `0453f1bb5b466079819ab480bfdc97bc62132e2b9c2fd23fef5cb7ad5c39bc58`
- synthesis JSON SHA-256: `8f12f8c91c7829b263bbaa8653cd832ab1b974e8a60a775b2c38f0b98d66776a`

The three scientific JSON outputs are byte-for-byte identical across the first complete run and the corrected exact-head run. The failed W6-06 gate is therefore reproducible and is not being tuned away.

## Boundary

- movement itself never changes `practice_by_skill`;
- selection is public-evidence-only;
- returned learning is explicit, provenance-bearing agent-owned state;
- source cost is World-side availability, not Field mutation;
- pair state appears only in the explicit W6-06 treatment;
- no individual outcome law reads mobility mode, location, affiliation, history, or time away;
- Resonance Field remains unchanged.
