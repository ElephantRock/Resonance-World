# Resonance World v0.1 — Architecture Baseline

## 1. Objective

Resonance World is a federation layer for experiments involving multiple independently operating artificial cognitive societies.

Its purpose is to study higher-order emergence across societies without requiring Resonance Field to change its internal scientific program.

## 2. Boundary rule

The dependency is one-way:

```text
Resonance Field  --->  Resonance World
```

Resonance World may depend on explicit Field contracts. Resonance Field must not depend on Resonance World.

A Field remains a complete experiment when disconnected from the World.

## 3. Core entities

### Field
A sovereign experimental ecology with local agents, substrate, task market, economy, reputation evidence, lifecycle, and provenance.

### Agent Passport
A portable, evidence-backed summary of demonstrated capability and transfer history. Local reputation is source evidence, not a globally authoritative score.

### Organization
A cross-field institution created around a mission. It may recruit individuals or teams, maintain organizational memory, allocate resources, and accumulate independent performance history.

### Mission
An externally defined goal with budget, constraints, success conditions, evaluation protocol, and provenance requirements.

### World
The registry, protocol, market, event system, and experimental control plane that connect Fields and Organizations.

## 4. Logical topology

```text
                         Human / External Missions
                                  |
                           World Control Plane
                                  |
         +------------------------+------------------------+
         |                        |                        |
   Organization X           Organization Y          World Metrics
         |                        |                        |
         +----------- Recruitment / Contracts ------------+
                                  |
                         Inter-Field Protocol
                 +----------------+----------------+
                 |                |                |
              Field A          Field B          Field C
                 |                |                |
            local agents     local agents     local agents
            local memory     local memory     local memory
            local market     local market     local market
```

## 5. v0.1 Field contract

The first World implementation should require the smallest possible interface from a Field.

### Identity

- `field_id`
- `field_protocol_version`
- `runtime_version`
- `experiment_id`

### Capability discovery

- enumerate eligible agent identities;
- request an evidence-backed capability summary;
- request bounded transfer-test participation;
- expose team/co-working evidence where available.

### Recruitment

- offer a recruitment contract;
- accept/reject/expire an offer according to experiment policy;
- export a permitted agent capsule;
- mark local competitive availability when an agent departs or is seconded;
- receive return/migration evidence.

### Knowledge exchange

- export explicitly public traces or trace summaries;
- import permitted external knowledge with immutable source provenance;
- preserve source-field identity and lineage.

### Accounting

- represent cross-field resource transfers without mutating local ledger invariants;
- reconcile world-level contracts against field-level receipts.

### Events

Minimum world-facing events:

```text
field.registered
field.connected
field.disconnected
agent.passport.published
agent.transfer_test.completed
recruitment.offer.created
recruitment.offer.accepted
recruitment.offer.rejected
agent.seconded
agent.migrated
agent.returned
team.recruited
organization.created
organization.member.joined
organization.member.left
organization.memory.created
mission.created
mission.completed
knowledge.exported
knowledge.imported
contract.settled
```

## 6. Agent Passport

The passport is derived from evidence, not authored by the agent.

Suggested v0.1 fields:

```text
agent_id
source_field_id
passport_version
observed_cycles
completed_tasks
success_rate
capability_vector
calibration_metrics
adaptation_metrics
specialization_metrics
collaboration_metrics
transfer_tests
known_team_synergies
home_dependency_score
portable_capability_score
evidence_refs
issued_at
```

The World must distinguish:

- **local fitness** — performance inside the source Field;
- **portable capability** — performance across controlled foreign contexts;
- **team capital** — performance attributable to a recurring combination of agents beyond individual expectations.

## 7. Agent Capsule

A capsule is the transferable execution package for a recruited agent.

It may contain:

- stable identity reference;
- base runtime/model reference;
- permitted practice state;
- bounded memory export;
- capability passport;
- collaboration metadata;
- tool competency evidence;
- policy constraints;
- provenance references;
- transfer history.

It must not silently export private Field state or unrestricted substrate access.

## 8. Organizations

Organizations are not Fields.

A Field is a developmental society. An Organization is a mission-oriented overlay whose membership may span Fields.

An Organization owns:

- organization identity;
- mission portfolio;
- budget;
- membership contracts;
- organizational memory;
- internal coordination records;
- organization-level reputation/performance evidence.

An Organization does not own the source identity or complete local history of recruited agents.

## 9. Recruitment model

Recruitment should initially be system-controlled and experimentally transparent.

Candidate selection may use:

- demonstrated task competence;
- transfer robustness;
- adaptation latency;
- calibration;
- home-ecology dependency;
- complementarity with current members;
- prior team performance;
- cost/resource requirements.

No candidate should be selected from an occupational label assigned at initialization.

## 10. World-level metrics

Initial metrics should include:

### Capability
- unseen-mission success;
- adaptation latency;
- compute efficiency;
- portable capability lift over purpose-built baselines;
- team synergy / team capital.

### Mobility
- migration rate;
- secondment rate;
- return rate;
- source-field talent loss;
- brain circulation.

### Knowledge
- cross-field knowledge diffusion;
- lineage-preserving reuse;
- knowledge mutation after transfer;
- source diversity of organizational memory.

### Institutions
- organization persistence under member turnover;
- member concentration;
- source-field concentration;
- organization capability after founder departure;
- corporate memory contribution.

### World ecology
- between-field capability diversity;
- cultural/behavioral convergence;
- talent concentration;
- market concentration;
- source-field productive capacity before/after recruitment.

## 11. Safety and integrity invariants

- Every cross-field transfer is explicit and provenance-preserving.
- Local reputation is never silently rewritten into global reputation.
- Private Field state is non-exportable by default.
- Imported traces retain immutable source identity.
- Organization access does not bypass Field policy boundaries.
- External side effects remain behind explicit policy gateways.
- World accounting cannot create spendable local value without a reconciled receipt.
- Recruitment cannot delete or rewrite the historical evidence used to justify selection.

## 12. Initial experiment topology

The first implementation target is intentionally small:

```text
3 Fields x 20 active agents
1 cross-field Organization
1 unseen external Mission
```

The purpose is to validate contracts and transfer semantics before scaling population or institutional complexity.

## 13. Non-goals for v0.1

- geopolitical simulation;
- human-like nationality or ideology prompts;
- unrestricted agent self-migration;
- autonomous legal/financial contracting;
- global reputation as a single scalar;
- model-weight evolution;
- replacing Resonance Field internals;
- large-scale world simulation before transfer validity is established.
