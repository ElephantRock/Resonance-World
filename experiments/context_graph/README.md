# Resonance World Context-Graph Experiment

Status: experimental branch scaffold

Branch: `experiment/context-graph`

## Objective

Test whether a provenance-bearing shared evidence graph improves cross-agent relational discovery relative to isolated evidence, without turning shared context into shared belief or changing the environment outcome law.

The experiment is deliberately smaller than a storage/platform decision. It first asks whether the mechanism is scientifically useful under deterministic conditions.

## Primary hypothesis

A bounded shared evidence graph will recover valid relationships that require combining observations from multiple agents more often than an isolated-evidence baseline, while preserving provenance, avoiding false-positive relational claims, and leaving agent-local belief state unchanged unless an explicit perception/communication step occurs.

## Epistemic layers

The scaffold keeps three layers separate:

1. **World graph** — hidden canonical facts used only as experimental ground truth.
2. **Evidence graph** — append-only claims with source, observer, confidence, and temporal metadata.
3. **Belief graph** — agent-local beliefs populated only through explicit observation in the first fixture.

The context compiler reads evidence to assemble bounded decision context. It does **not** write into belief graphs.

This separation is intentional: graph access is not omniscience.

## Conditions

### A. `isolated`

An agent can compile only evidence that it personally observed.

### B. `shared_evidence`

An agent can compile eligible evidence contributed by any observer, subject to the same hop and confidence limits.

The environment/world truth is identical across conditions.

## First fixture

The deterministic fixture uses three assets and three agents:

```text
asset-alpha --uses--> bridge-x   observed by agent-a
asset-beta  --uses--> bridge-x   observed by agent-b
asset-gamma --uses--> bridge-y   observed by agent-c
```

A low-confidence contradictory claim is also retained:

```text
asset-beta --uses--> bridge-z    observed by agent-c, confidence 0.40
```

The first positive query asks whether `asset-alpha` and `asset-beta` share a dependency. The answer is derivable only by combining evidence from multiple observers. No direct `asset-alpha <-> asset-beta` edge is materialized.

## Metrics

The initial harness exposes:

- relational answer recall;
- false-positive rate;
- exact-query rate;
- number of answers requiring evidence from multiple observers;
- provenance completeness;
- contradiction visibility;
- belief-state contamination checks.

The preregistered scaffold gates live in `experiment.json`.

## Experimental invariants

- Context-graph state may affect **what evidence a decision process can inspect**.
- Context-graph state must not directly change task/world outcome laws.
- Evidence is not silently promoted to canonical truth.
- Contradictory claims remain representable.
- Every evidence claim carries source and observer provenance.
- Shared graph retrieval does not mutate agent-local beliefs.
- The first implementation derives shared structure through graph topology rather than writing all pairwise correlations as edges.

These rules extend the existing Resonance World causal discipline around relationship and organization memory: memory can influence decisions, but hidden memory must not become an unmeasured success bonus.

## Files

- `experiment.json` — frozen first-fixture conditions, thresholds, and success gates.
- `evidence-envelope.schema.json` — storage-neutral evidence-envelope contract.
- `src/resonance_world/context_graph_experiment.py` — deterministic graph/belief/context substrate.
- `tests/test_context_graph_experiment.py` — semantic invariants and baseline-vs-graph checks.

## Next integration step

After the deterministic fixture passes, connect the evidence graph to existing World outputs rather than inventing a parallel simulation stack:

1. ingest W3 swarm/relationship evidence as provenance-bearing claims;
2. ingest W5 organization-memory events as a separate source class;
3. run matched mission queries under `isolated` and `shared_evidence` context policies;
4. measure cross-agent discovery lift, error, context size, and compute cost;
5. add an explicit communication/adoption intervention before allowing retrieved evidence to alter belief graphs.

Only after those gates should we choose a persistent graph backend or extract this layer into a standalone service/repository.

## Non-goals for the scaffold

- choosing Neo4j, Graphiti, or another graph database;
- embeddings or semantic search;
- LLM-based entity resolution;
- automatic belief synchronization;
- global truth inferred from majority vote;
- production integration with the World control plane;
- modifying existing W3/W4/W5 experiment outcomes.
