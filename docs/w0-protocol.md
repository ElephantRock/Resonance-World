# W0 Field / World Protocol

## Purpose

W0 defines the smallest read-only contract by which Resonance World can observe an independently operating Resonance Field without importing Field runtime internals or mutating Field state.

The contract is an exported checkpoint evidence bundle. The source Field remains authoritative. World derives passports from the bundle and must preserve provenance back to source evidence.

## Boundary rule

```text
Resonance Field
    |
    | exported checkpoint evidence (read only)
    v
CheckpointJsonAdapter
    |
    v
WorldRegistry -> AgentPassport
```

World does not receive mutation methods for local tasks, traces, reputation, credits, practice, lifecycle, or markets.

## Bundle shape

A checkpoint bundle is one JSON object with three top-level collections:

- `field` — source identity and checkpoint metadata;
- `agents` — evidence-derived summary rows used to construct passports;
- `evidence` — immutable evidence payloads indexed by URI and SHA-256.

### `field`

Required fields:

- `field_id`
- `field_protocol_version`
- `runtime_version`
- `experiment_id`
- `checkpoint_id`
- `issued_at` — timezone-aware ISO-8601 timestamp

### `agents`

Each record requires an `agent_id`. W0 passport inputs are:

- `observed_cycles`
- `completed_tasks`
- `success_rate`
- `capability_vector`
- `calibration_metrics`
- `adaptation_metrics`
- `specialization_metrics`
- `collaboration_metrics`
- `home_dependency_score`
- `portable_capability_score`
- `evidence_refs`

`portable_capability_score` SHOULD remain `null` in W0 because portability has not yet been measured by transfer experiments.

There is deliberately no occupation, profession, persona, or self-authored capability field.

### `evidence`

Each evidence entry contains:

- `uri` — globally unique within the World experiment;
- `kind` — source evidence category;
- `source_record_id` — optional source identifier;
- `sha256` — canonical JSON SHA-256 digest;
- `payload` — JSON-compatible source evidence.

Canonical JSON uses sorted keys, UTF-8, no insignificant whitespace, and no ASCII coercion.

World rejects an evidence entry when the declared digest differs from the canonical digest. A passport cannot reference an evidence URI absent from the checkpoint bundle.

## Determinism

For the same checkpoint bundle:

- agent enumeration is sorted;
- capability and metric collections are sorted by their frozen protocol representation;
- evidence references are sorted;
- passport issuance time comes from the checkpoint rather than the observer clock;
- canonical passport serialization is deterministic.

This makes repeated W0 exports idempotence-testable.

## W0 non-interference gate

Matched runs compare an isolated Field control with an otherwise identical World-observed run.

Behavioral state is represented by authoritative state hashes such as market, reputation, trace, lifecycle, and other experiment-specific hashes. Emergence metrics are compared under an explicit numeric tolerance.

W0 passes observation only when:

1. state hashes are unchanged;
2. emergence metrics remain within the configured tolerance; and
3. World instrumentation overhead remains within the configured bound.

The initial code default is a maximum instrumentation ratio of 5%. This is an engineering threshold, not a scientific constant, and may be tightened after baseline measurement.

## W0 exclusions

The protocol does not yet allow:

- migration;
- recruitment;
- inter-field messages;
- shared substrates;
- global reputation;
- organizations;
- corporate memory;
- world-level economic transfers.

Those mechanisms require evidence from later World experiments.
