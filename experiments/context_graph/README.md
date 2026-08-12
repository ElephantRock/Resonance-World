# Resonance World ContextGraph Research Lineage

**Status:** architectural graduation complete; this directory is frozen scientific provenance and compatibility infrastructure.

Branch: `experiment/context-graph`

Runtime ownership now lives in `ElephantRock/Resonance-ContextGraph`. Resonance World consumes the standalone package through `src/resonance_world/context_graph_runtime.py` and `context_graph_adapter.py`; the historical `context_graph_*` modules remain here as scientific fixtures until downstream imports are migrated.

The architectural parity gate passed on workflow `31638124103` against standalone commit `55ce7bb435b3d4a1ff888474a5ca76ccff843150`. The exact Actions-produced result is `context-graph-standalone-parity-result.json`; the extraction/provenance decision is recorded in `context-graph-graduation-record.json`.

## Architectural invariant

```text
world truth != evidence graph != agent belief != social/public state
```

ContextGraph may change **what evidence a decision process can inspect**. It must not silently mutate an agent's beliefs, promote evidence into canonical world truth, or directly modify an environment outcome law.

## Scientific sequence

The research sequence deliberately preserved failures rather than optimizing them away:

- **CG-0** — deterministic apparatus scaffold.
- **CG-1** — W3 topology retrieval advantage.
- **CG-2** — temporal/provenance/conflict filtering.
- **CG-3** — controlled decision causality.
- **CG-4** — first endogenous formation design; confirmatory **FAIL**.
- **CG-4F** — exploratory failure diagnosis: weak endogenous capability signal and single-positive-probe winner's curse.
- **CG-4M** — exploratory measurement sufficiency and event reconciliation.
- **CG-5** — active measurement + reconciled evidence + topology; confirmatory **PASS**.
- **CG-6** — unconstrained adaptive cell acquisition; calibration **FAIL**.
- **CG-7** — fixed 72-probe economy test; confirmatory **FAIL**.
- **CG-8** — constrained adaptive cell acquisition; calibration **FAIL**.
- **CG-9** — fixed 60-probe frontier point; confirmatory **FAIL**.
- **CG-10** — pair-stability stopping without a tail cap; exploratory **FAIL**.
- **CG-10B** — exploratory capped stopping repair.
- **CG-11** — fresh-cohort capped stopping replication; confirmatory **PASS**.

CG-11 reduced mean supplemental measurement from `216.0` to `111.2` probes per Field while meeting the frozen non-inferiority criterion. At matched stopped evidence cost, topology-aware retrieval retained a positive advantage over bundle-flat and shuffled-topology controls.

## Graduation parity

The standalone runtime was not accepted on API similarity alone. The parity workflow replayed immutable CG-5 and CG-11 source capsules after verifying their SHA-256 hashes.

CG-5 parity:

- 15 Fields / 90 decisions;
- 0 context mismatches;
- exact expected success `0.27763600681086903`;
- exact `47` claims / `13` complete bundles per decision;
- exact `3240` supplemental probe events.

CG-11 parity:

- 30 Fields / 180 final decisions;
- 210 checkpoint observations checked;
- 1260 checkpoint context decisions checked;
- 360 final stopped/fixed context decisions checked;
- 5040 balanced scheduler steps checked;
- 0 context mismatches;
- 0 checkpoint-observable mismatches;
- 0 scheduler mismatches;
- 0 stopping mismatches;
- exact stop histogram `60:8, 72:4, 96:3, 120:4, 144:2, 168:9`;
- exact stopped expected success `0.2790790551714306`;
- exact fixed-six expected success `0.28111686910074246`.

This authorizes deprecation of duplicate World runtime ownership. It does **not** authorize deletion of frozen experiment records.

## Extraction-time provenance findings

Two compatibility details were discovered only when the standalone implementation was replayed against immutable artifacts.

### Repeated same-observer deliveries

The frozen W3 generator can emit the same provenance `source_id` more than once when the participant is also selected as scout. The executed behavior filters confidence first, then lets the last admissible same-observer predicate delivery win; duplicate observers of one event still count as one independent event. The standalone adapter now preserves `source_id` as provenance and assigns delivery-unique transport claim IDs.

### CG-11 stopping contract discrepancy

The CG-11 preregistration prose described stopping when the six-mission selected-pair vector matched the immediately preceding checkpoint. The executed frozen evaluator additionally computed minimum selected-role event support and minimum selected-role score margin, and enforced thresholds `support >= 0` and `margin >= 0.0`. The support threshold is vacuous; the score-margin threshold can delay stopping.

The historical protocol and result are not rewritten. Architectural compatibility follows the executed frozen evaluator because that implementation generated the confirmatory result, and the discrepancy is recorded explicitly in the graduation record and the standalone repository.

## Epistemic layers

1. **World truth** — evaluator-hidden canonical state.
2. **Evidence graph** — append-only claims with provenance, confidence, and temporal validity.
3. **Belief graph** — agent-local beliefs changed only by explicit perception/adoption.
4. **Social/public graph** — externally visible relational state, distinct from evidence and belief.
5. **Context compiler** — bounded evidence assembly for decisions; no implicit belief write.

## Causal boundaries

- ContextGraph state may influence agent decisions.
- ContextGraph state must never directly change environment outcome laws.
- Evidence is not silently promoted to canonical truth.
- Contradictions remain representable.
- Retrieval does not mutate agent beliefs.
- Acquisition and stopping cannot inspect evaluator hidden capability or oracle state.
- `JointEnvironment.evaluate` receives no graph, evidence, relationship, organization, acquisition, or stopping state.

## Ownership after graduation

**Standalone ContextGraph owns:**

- evidence contracts;
- append-only evidence storage semantics;
- event reconciliation;
- uncertainty-aware estimation;
- bounded topology-aware context compilation;
- balanced measurement scheduling;
- observable measurement-sufficiency stopping.

**Resonance World retains:**

- environment/world dynamics;
- action/outcome laws;
- adapters from observed World events into ContextGraph evidence;
- immutable CG experimental configs, runners, results, and source-replay fixtures.

The persistent graph backend remains intentionally unspecified. The architecture is defined by epistemic and causal contracts, not a particular database.
