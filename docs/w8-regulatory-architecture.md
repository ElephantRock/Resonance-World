# W8-00 — Regulatory Architecture Gate

Status: architecture candidate pending hosted validation.

Parent issue: #68.

## Purpose

W8 asks whether World-level institutional rules can convert the extractive competitive
economy observed in W7 into sustainable or generative capability circulation.

W8-00 adds only the minimal regulatory primitives required to test that question. It
makes no behavioral claim and does not modify Resonance Field.

## Existing boundary

Before W8, Resonance World already contains:

- portable individual competence (`PortableAgentState`);
- explicit mobility lifecycle (`MobilityRegistry`);
- persistent organizations and organization-owned memory;
- scarce-talent offers/contracts (`TalentMarket`);
- mission-bounded cooperation agreements;
- W4 joint execution whose outcome law reads individual competence, actions and mission
  structure, but not relationship, organization or market metadata.

W8 regulation therefore governs access to these existing capabilities. It does not add
another capability source.

## Added primitives

### Source reserve

`SourceReserveRule` and `RegulatedServiceLedger` cap simultaneous external service rights
per immutable source Field. The ledger stores only contract metadata and immutable
portable-state digests. Grant/release operations never mutate `PortableAgentState`.

### Circulation schedules

`CirculationSchedule` represents deterministic external/home duty cycles. W8 can compare
4:2 and 3:3 schedules without encoding any learning or success advantage into the cycle
itself.

### Source dividends

`SourceDividendPolicy` maps contract prices to source-owned replacement-development
budgets. `ReplacementGrant` intentionally contains no departed-agent target, target
skill, specialization objective or curriculum instruction. Later W8 replacement agents
must develop through native Field ecology.

### Coalition coordination rights

`CoalitionCoordinationContract` stores mission-bounded subtask decomposition and a
bounded communication entitlement. It contains organization/agent identities, skills,
roles and provenance only. It does not carry organization memory, relationship state,
PairModule state or competence.

### Explicit budget dynamics

`BudgetUpdatePolicy` makes long-horizon economic feedback an explicit W8 variable:

- `neutral` resets each organization to the same base budget;
- `compounding` applies a preregisterable success-reward law subject to a maximum budget.

Budget dynamics remain economic state and do not enter mission-success probability.

### Ownership-invariant capability stock

`CapabilityStockObservation` records a benchmark assignment in which every living agent
may be counted at most once and every benchmark mission may be assigned once. This
prevents World capability from being inflated by counting the same agent simultaneously
through its source Field and an organization.

The observation can also report capability stock divided by cumulative developmental
compute. The optimization/benchmark scorer belongs to the behavioral campaign; W8-00
only enforces the ownership-invariant accounting boundary.

### Regulatory charter

`RegulatoryCharter` serializes the institutional rules and explicitly rejects competence
or pair/organization-memory payloads.

## Hard causal boundary

Regulation may affect:

- who may receive an external service right;
- how many rights a source Field may have active;
- when an agent is external versus home;
- how contract payments are split;
- what non-targeted replacement-development budget a Field receives;
- which bounded coordination rights a coalition receives;
- how organization budgets update between economic cycles.

Regulation may not directly affect:

- `practice_by_skill`;
- partner models or pair memories;
- organization memory;
- the W4/W5 mission-success law;
- Field developmental rules.

The W4 `JointEnvironment.evaluate()` signature remains regulation-blind and is enforced
by regression tests.

## Behavioral sequence enabled by W8-00

1. W8-01 — source reserve + source-loss-matched composition-efficiency frontier.
2. W8-02 — permanent recruitment vs 4:2 vs 3:3 circulation, including exposure-matched
   analysis.
3. W8-03 — source dividend / replacement regeneration plus developmental-contingency
   assay against an unperturbed Field counterfactual.
4. W8-04 — three decomposable and three non-decomposable coalition mission families.
5. W8-05 — full charter plus leave-one-out institutional ablations and roster-stability
   metrics.
6. W8-06 — long-horizon repeated economy with neutral-vs-compounding budgets, shocks,
   concentration, source regeneration and ownership-invariant capability stock.
7. W8-07 — fresh unseen Fields and economic histories after every mechanism and threshold
   is frozen.

## Candidate nested synthesis labels

- `replicated_sustainable_circulation`: organizations remain viable while source
  extraction is eliminated/bounded and positive coalition surplus survives replication.
- `replicated_generative_circulation`: sustainable circulation plus increasing
  ownership-invariant, compute-normalized capability stock over the long horizon.

Neither label is assumed. W8 may legitimately produce null, negative or mixed outcomes.
