# Resonance World

**A research platform for artificial multi-society systems.**

Resonance World studies what happens when independent artificial cognitive societies interact across persistent institutional boundaries.

Where [Resonance Field](https://github.com/ElephantRock/Resonance-Field) asks whether useful organization can emerge **within** an artificial cognitive ecology, Resonance World asks whether higher-order organization can emerge **between** such ecologies through migration, recruitment, trade, knowledge diffusion, cooperation, competition, and cross-field institutions.

## Core research question

> Can independent artificial societies develop distinct capabilities, exchange talent and knowledge, form persistent cross-society institutions, and collectively solve problems no single society was prepared for?

## Architectural boundary

Resonance World is a separate research program built above Resonance Field.

- **Resonance Field** owns agents, local substrate, local task markets, reputation evidence, lifecycle, succession, and within-field emergence.
- **Resonance World** owns field identity, federation, migration, portable capability evidence, inter-field exchange, recruitment, organizations, and world-level experiments.
- Resonance Field MUST remain fully operational without Resonance World.
- Resonance World SHOULD interact with a Field through explicit contracts rather than importing its internal state model directly.

```text
Human / External Missions
          |
   Resonance World
   /      |       \
Org X   Org Y    World Metrics
  |       |           |
  +--- Inter-Field ---+
       Protocol
      /    |    \
 Field A Field B Field C
      \    |    /
       independent
       local ecologies
```

## Initial primitives

### FIELD
An independently operating artificial cognitive society with its own local history, agents, substrate, economy, and institutions.

### AGENT PASSPORT
Evidence-backed portable capability metadata derived from observed behavior. It is not a self-authored résumé and does not automatically transfer local reputation.

### ORGANIZATION
A mission-bound institution that can recruit agents or teams from multiple Fields, maintain organizational memory, allocate resources, and accumulate its own performance history.

### WORLD
The protocol and experimental environment that enables identity, exchange, migration, contracts, recruitment, knowledge movement, and measurement across Fields and Organizations.

## v0.1 hypothesis

The first falsifiable hypothesis is:

> Cross-field organizations assembled from agents selected by demonstrated life history can outperform equally resourced purpose-built organizations on unseen missions without collapsing the diversity or productive capacity of their source Fields.

## v0.1 experimental progression

1. **Independent Fields** — operate multiple isolated Fields long enough to establish distinct developmental histories.
2. **Controlled contact** — introduce bounded information exchange, trade, and temporary migration.
3. **Recruitment** — select individuals and stable teams using evidence-backed portable capability signals.
4. **Cross-field organizations** — assemble mission-driven organizations from multiple source Fields.
5. **Persistent organizations** — add corporate memory and organizational reputation independent of current membership.
6. **World dynamics** — measure brain drain/circulation, knowledge spillovers, concentration, cultural convergence, and institutional competition.
7. **Unseen mission holdout** — compare recruited organizations against purpose-built baselines under equal model, tool, and compute constraints.

## Initial scale

Start small enough to remain falsifiable:

- 3 independent Fields
- 20 active agents per Field
- 1 cross-field Organization
- 1 unseen external mission

Scale only after the field boundary, evidence model, transfer semantics, and experimental invariants are validated.

## Design constraints

- Do not assign occupational roles merely to make recruitment easier.
- Local reputation is not automatically global reputation.
- Recruitment must rely on observed evidence and controlled transfer tests.
- A team may be a more meaningful unit of capability than an individual agent.
- Public knowledge and private agent state must have explicit export rules.
- World-level success must not be allowed to consume all source-field diversity.
- Side effects remain governed by explicit policy boundaries.
- Every consequential cross-field event must be provenance-preserving and auditable.

## Repository direction

```text
docs/
  architecture.md
  research-program.md

src/resonance_world/        # world runtime (future)
tests/                      # unit/integration experiments (future)
configs/                    # versioned world experiments (future)
.github/workflows/          # reproducible campaigns (future)
```

This repository begins as a research specification. Runtime code should be added only as required by falsifiable experiments.
