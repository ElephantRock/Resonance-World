# Resonance ContextGraph v0.1.0 integration

Resonance World adopts the released `Resonance-ContextGraph` runtime as an **observer-only
Observatory substrate**. It does not import the historical ContextGraph experiment campaign
into World `main`, and it does not enable accumulated history as an agent or organization
intervention.

The program boundary is governed by #111: the North Star is sustainable, top-tier
organizations whose intelligence may eventually derive from both models and persistent
collective history. ContextGraph first serves as a scientific observatory so that later
historical-feedback interventions can be measured against a causally clean baseline.

## Runtime boundary

- World depends on ContextGraph through the optional `contextgraph` extra.
- Release metadata remains tag `v0.1.0`, while installation is pinned to immutable commit
  `b896891108fd954869a8cd0423f6e8440ab0cdc0`.
- `context_graph_adapter.py` accepts structural observation/mission protocols only.
- Every World transport `claim_id` is generated in a separate escaped delivery namespace;
  opaque producer `source_id` values remain provenance and are never reused as claim IDs.
- Hidden evaluator capability, oracle state, agent belief mutation, participant decision
  state, and environment outcome-law state remain outside the adapter contract.
- Production consumers import through `context_graph_runtime.py`.
- Production stopping requires complete `CheckpointObservation` values. The old
  `(budget, pair_vector)` compatibility shape is rejected so missing selected-role
  support/margin measurements cannot be synthesized as zero-valued evidence.

## Observatory causal boundary

The permitted direction is:

```text
World / Field / future PIANO observations
              |
              v
        ContextGraph
              |
              v
      researcher/evaluator
```

The forbidden direction remains:

```text
ContextGraph -X-> agent decisions
ContextGraph -X-> organization decisions
ContextGraph -X-> Field capability state
ContextGraph -X-> World outcome law
```

`INTEGRATION_MODE` is `observer-only` and `HISTORICAL_SUBSTRATE_ENABLED` is `False`.
The standing integration workflow verifies that World production modules cannot begin
consuming ContextGraph output outside the explicitly registered Observatory boundary.
Enabling participant historical access requires a separate preregistered intervention.

## O0 passive Observatory validation

O0 was preregistered in #113 and executed through PR #114. The accepted exact head was
`01b20965feed1e850f16040b144ff54527fe7f1e`; it was squash-merged as
`b2fb206196b73ee80fd28628d3c94f48d5f8e7f1`.

The authoritative exact-head workflow `31657145249` ran two isolated reproductions and a
downstream byte-comparison gate. Both reproductions and the comparison gate passed.

O0 classification:

`observatory_non_interference_pass`

The registered World traces were byte-identical across:

1. frozen pre-O0 World base;
2. candidate runtime with the observer disabled;
3. candidate runtime with the live ContextGraph Observatory recording after every episode.

All three authoritative World traces have SHA-256:

`dd8b5a30cf9ed85f96fcb9164f16ec3d958d7ccfc10c5ab157079e119978bb40`

The instrumented arm produced exactly 240 observed episodes and 2,160 provenance-bearing
claims, with exact semantic claim values cross-checked against the observed World trace,
no registered hidden-state leakage, and no participant read path. The accepted evidence
SHA-256 is:

`7e8ef1c9fcbfbc16eb5e50db477dcacc2b6830af86b50b8cf44c965c21ca456a`

The accepted result SHA-256 is:

`8a73026c1f76e00b52bc4eee8b8c005c351942f79fedcbf5f39bce304353463d`

The accepted manifest SHA-256 is:

`f6275d3de1d22fc2d880c2af42fab102a9fda1cc53eb672828f57da2de4538af`

Fresh exact-head Codex review found no major issues. After merge, the standing ContextGraph
integration gate ran on `main` as `31657484267` and passed.

O0 establishes **passive non-interference only**. It does not establish that ContextGraph
observations are sufficient to characterize organizations, that history improves decisions,
or that ContextGraph improves sustainability or organizational intelligence.

## Scientific provenance

The full CG-1 through CG-11 research history remains on `experiment/context-graph`. The
production adoption did not re-run, rewrite, or selectively import those experiments. The
prior release-parity proof remains World run `31641586497`, which reproduced frozen CG-5
and CG-11 semantics against ContextGraph `v0.1.0`.

CG-11 architectural parity follows the executed frozen evaluator. That evaluator enforced
pair-vector stability plus a non-negative minimum selected-role score margin;
preregistration prose described pair stability alone. The discrepancy remains explicit
and historical records are unchanged.

## Standing production gate

The dedicated `ContextGraph v0.1.0 Integration` workflow continues to prove:

- immutable release-commit installation and matching release metadata;
- minimal adoption scope, with no historical World ContextGraph implementation;
- observer-only causal isolation and no participant-side production consumer;
- provenance-record integrity;
- adapter/runtime/Observatory lint and synthetic contract behavior;
- collision-safe transport claim identities;
- complete executed stopping-observation semantics;
- World environment/controller outcome-decision isolation.

The same integration gate runs for relevant changes on `main`, so later World changes
cannot silently cross the observer-only boundary.

## Next scientific boundary

O0 permits the program to proceed to **observational validity** work: whether the passive
Observatory can accurately reconstruct and longitudinally characterize capability,
relationship, role, organization, turnover, and sustainability phenomena. It does not
permit Historical Substrate feedback. Participant access remains a later, explicitly
causal treatment.
