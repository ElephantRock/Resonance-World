# Resonance ContextGraph v0.1.0 integration

This branch adopts the released `Resonance-ContextGraph` runtime as an **observer-only
Observatory substrate** for Resonance World. It does not import the historical ContextGraph
experiment campaign into World `main`, and it does not enable accumulated history as an
agent or organization intervention.

The program boundary is governed by #111: the North Star is sustainable, top-tier
organizations whose intelligence may eventually derive from both models and persistent
collective history. This integration establishes the observation substrate needed to
measure that thesis before historical feedback is allowed to influence the society.

## Runtime boundary

- World depends on ContextGraph through the optional `contextgraph` extra.
- The release metadata remains tag `v0.1.0`, while the install itself is pinned to immutable
  commit `b896891108fd954869a8cd0423f6e8440ab0cdc0`.
- `context_graph_adapter.py` accepts structural observation/mission protocols only.
- Every World transport `claim_id` is generated in a separate escaped delivery namespace;
  opaque producer `source_id` values remain provenance and are never reused as claim IDs.
- Hidden evaluator capability, oracle state, agent belief mutation, participant decision
  state, and environment outcome-law state are outside the adapter contract.
- Production consumers import through `context_graph_runtime.py`.
- Production stopping requires complete `CheckpointObservation` values. The old
  `(budget, pair_vector)` compatibility shape is rejected so missing selected-role
  support/margin measurements cannot be synthesized as zero-valued evidence.

## Observatory causal boundary

For this integration phase the permitted direction is:

```text
World / Field / future PIANO observations
              |
              v
        ContextGraph
              |
              v
      researcher/evaluator
```

The forbidden direction is:

```text
ContextGraph -X-> agent decisions
ContextGraph -X-> organization decisions
ContextGraph -X-> Field capability state
ContextGraph -X-> World outcome law
```

`INTEGRATION_MODE` is `observer-only` and `HISTORICAL_SUBSTRATE_ENABLED` is `False`.
The dedicated integration workflow also verifies that no other World production module
imports the ContextGraph adapter/runtime in this phase. Enabling participant historical
access requires a separate preregistered intervention after Observatory non-interference
and validity are established.

## Scientific provenance

The full CG-1 through CG-11 research history remains on `experiment/context-graph`. This
adoption branch does not re-run, rewrite, or selectively import those experiments. It
records the already completed release-parity proof from World run `31641586497`, which
reproduced the frozen CG-5 and CG-11 semantics against ContextGraph `v0.1.0`.

CG-11 architectural parity follows the executed frozen evaluator. That evaluator enforced
pair-vector stability plus a non-negative minimum selected-role score margin;
preregistration prose described pair stability alone. The discrepancy remains explicit
and historical records are unchanged.

This PR makes **no new efficacy, sustainability, memory, or evolutionary claim**. It is an
engineering/architecture adoption required before a separately preregistered O0
non-interference experiment.

## Merge criterion

The dedicated `ContextGraph v0.1.0 Integration` workflow must prove:

- immutable release-commit installation and matching release metadata;
- minimal adoption scope, with no historical World ContextGraph implementation;
- observer-only causal isolation and no participant-side production consumer;
- provenance-record integrity;
- adapter/runtime lint and synthetic contract behavior;
- collision-safe transport claim identities;
- complete executed stopping-observation semantics;
- World environment outcome-law isolation.

The same integration gate must run for relevant changes on `main`, so later World changes
cannot silently break the optional production contract while ordinary tests skip the
uninstalled extra.
