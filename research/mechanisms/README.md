# Mechanism Registry

This directory is the machine-readable scientific ledger for bounded causal mechanisms in Resonance World.

The registry is governed by `docs/mechanism-governance-v0.1.md`.

## Important distinction

Existing W/O/H evidence predates this registry. Those entries are imported as `historical_record` and are **not automatically promoted** into the new advancement ladder. Historical results remain valid within their original registered scopes; migration into a stronger registry status requires an explicit acceptance event and the prospective statistical/generalization requirements appropriate to that status.

## Promotion states

`proposed → discovery_supported → internally_replicated → schema_generalized → model_generalized → naturalistic_validated → integration_eligible → evolution_eligible`

Promotion is append-only and requires separate proposer and acceptor authority. Experiment output cannot write its own registry status.

## Files

- `registry.json` — current nodes and historical evidence pointers.
- future `acceptance/*.json` — append-only promotion events.

No numerical threshold in this directory should be interpreted as materially meaningful unless its `SESOI_type` and provenance are explicit.
