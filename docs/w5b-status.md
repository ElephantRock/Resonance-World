# W5B Campaign Status

Status: **MIXED / DISCOVERY NOT FULLY REPLICATED**

Final synthesis status from the first complete hosted campaign: **`w5b_discovery_not_replicated`**.

- Parent issue: #37
- Implementation PR: #43
- Experiment count: 5
- Source architecture: Field-derived individual competence + W4 relationship state + W5B-00 PairModule
- Discovery source Fields: 5 x 12 agents = 60 fresh agents
- Held-out discovery Fields: 2 (520/641)
- Replication source Fields: 3 x 12 agents = 36 post-discovery agents (762/883/994)
- Pair modules per Field: 3
- Pair-formation depth: 12 episodes
- Evaluation trials: 128 per mission/condition
- Communication bandwidth: 1 bit in every pair condition
- Primary threshold/equivalence band: ±2 absolute percentage points
- Resonance Field pinned at `0914a21249261fe61e02c5191f4a36df416c672f`; Field was not modified.

## W5B-01 — Modular Pair Preservation: REPLICATED POSITIVE

Primary effect:

`intact PairModule - same two members / relationship state reset`

Held-out discovery:

- Field 520: **+9.6354 pp**
- Field 641: **+18.4896 pp**
- pooled: **+14.0625 pp**
- classification: **positive**

Post-discovery replication:

- Field 762: **0.0000 pp**
- Field 883: **+14.8438 pp**
- Field 994: **+3.1250 pp**
- pooled: **+5.9896 pp**
- positive Fields: **2/3**
- classification: **positive**
- replication requirement: **PASS**

Supported claim: W4 social state can survive deterministic capture and reinstantiation as a first-class reusable `PairModule`. This is **state modularization / organizational preservation of intact social capital**, not institutional memory independent of personnel.

## W5B-02 — Module Succession: REPLICATED NULL

Primary effect:

`same survivor + same newcomer with legitimately retained state - same survivor + same newcomer / fresh relationship state`

W5B-00 drops the old pair's partner-specific models and pair-owned episodes. Only the survivor's partner-independent general-teamwork state may remain.

Held-out discovery:

- Field 520: **0.0000 pp**
- Field 641: **0.0000 pp**
- pooled: **0.0000 pp**
- classification: **null**

Post-discovery replication:

- Field 762: **0.0000 pp**
- Field 883: **−2.8646 pp**
- Field 994: **0.0000 pp**
- pooled: **−0.9549 pp**
- classification: **null**
- replication requirement: **PASS**

Supported conclusion: no useful social-state inheritance across one-member replacement was detected under the registered succession mechanism. The validated module value remains bound to intact membership; the survivor's general-teamwork state alone did not bootstrap the replacement partner.

## W5B-03 — Cross-Module Composition: DISCOVERY POSITIVE, NOT REPLICATED

Two intact modules are composed sequentially; success requires both module-specific stages to succeed. There is no inter-module relationship or coordination state.

Held-out discovery:

- Field 520: **+6.7708 pp**
- Field 641: **+5.2083 pp**
- pooled: **+5.9896 pp**
- classification: **positive**

Post-discovery replication:

- Field 762: **0.0000 pp**
- Field 883: **+4.4271 pp**
- Field 994: **+1.5625 pp**
- pooled: **+1.9965 pp**
- positive Fields: **2/3**
- replication classification: **null**
- classification match: **no**
- replication requirement: **FAIL**

The pooled unseen effect lands just inside the preregistered +2 pp boundary. The threshold was not changed after observing this result. W5B therefore does **not** establish robust cross-module composition under the current sequential-composition design.

## W5B-04 — Module Library Accumulation: REPLICATED POSITIVE

Each condition uses the same six module-member agents; only the number of preserved pair modules varies from 0 to 3.

Held-out discovery:

- Field 520, zero→three modules: **+8.3333 pp**
- Field 641, zero→three modules: **+21.6146 pp**
- pooled: **+14.9740 pp**
- classification: **positive**

Post-discovery replication:

- Field 762: **0.0000 pp**
- Field 883: **+15.6250 pp**
- Field 994: **+6.5104 pp**
- pooled: **+7.3785 pp**
- positive Fields: **2/3**
- classification: **positive**
- replication requirement: **PASS**

Supported claim: under a fixed six-agent budget, preserving a larger library of already-developed pair modules can improve aggregate mission performance. This is evidence for an organizational capability **portfolio of intact modules**, not evidence that the organization has abstracted their know-how away from their members.

## W5B-05 — Unseen replication

Replication Fields 762/883/994 were generated in a separate fresh PostgreSQL evidence store after discovery execution. No W5B mission, source seed, threshold, formation depth, assignment rule, controller, module semantics, or environment success law was changed after observing discovery.

Experiment gates:

- W5B-01: **PASS**
- W5B-02: **PASS**
- W5B-03: **FAIL**
- W5B-04: **PASS**

Overall W5B replication gate: **FAIL**.

Final preregistered status: **`w5b_discovery_not_replicated`**.

## First complete evidence record

- exact scientific head: `73a6c4a14d58a218ec018cb2cd08a70b1f76d028`
- hosted CI / W5B campaign run: `31486499660`
- Ruff + pytest job: **PASS**
- full W5B campaign job: **PASS**
- evidence artifact: `9099339213`
- artifact digest: `sha256:ede7c3821b841a19e74130d6738e8da0fd64ce9f3ce031498df507e8eeba473f`

The earlier run `31486280121` is not scientific evidence: it completed discovery but failed before replication because a monolithic runner reused the discovery PostgreSQL database and Field migrations attempted to reapply an older experiment-number constraint. The runner was corrected to use independent discovery and replication databases; no scientific config or evaluator logic changed.

## Hard boundaries

- Resonance Field is unchanged.
- `JointEnvironment.evaluate()` cannot read module identity, module library, module history, organization identity, or institutional memory.
- No module or relationship success bonus is added.
- Old partner-specific state is never relabeled onto a replacement partner.
- Inter-module state is absent by design.
- Same-member and same-replacement controls use paired deterministic destination draws.
- W5B does not add a general procedure interpreter.

## Interpretation

The W5B result is narrower than the discovery-only picture:

1. **Intact social capital is modularizable.** W5B-01 replicated.
2. **It is not inherited by replacement personnel under the current mechanism.** W5B-02 replicated null.
3. **A portfolio of intact modules has replicated value at fixed agent count.** W5B-04 replicated.
4. **Independent modules did not demonstrate robust higher-order composition.** W5B-03 failed the frozen replication gate by a narrow margin.

Therefore W5B supports organizational preservation and accumulation of **intact social-capital modules**, but not institutional inheritance and not yet a reliably composable modular organization.

This result does not justify adding a generic procedural interpreter after the fact. Any later procedure-consumption architecture must be treated as a separate architectural extension and experiment series.
