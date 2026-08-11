# W0 First Cohort

## Objective

Materialize the first Resonance World population from three completed, independent Resonance Field Experiment 001 runs without modifying or rerunning Resonance Field.

The cohort is deliberately pre-contact. It establishes three source societies and sixty evidence-backed Agent Passports before migration, recruitment, shared substrate access, or world-level economics exist.

## Source Fields

The durable Experiment 001 lab notebook identifies these full-system cells:

| World Field | Field seed | Run ID | Artifact |
| --- | ---: | --- | --- |
| `field-001-seed-101` | 101 | `7b7b3800-81d8-5d2c-bda1-698ad7a44cd4` | `emergence-full-seed-101` |
| `field-002-seed-202` | 202 | `156da5f8-974d-563a-aaa4-9b009d43c5ca` | `emergence-full-seed-202` |
| `field-003-seed-303` | 303 | `4ac57050-cffa-5bdc-a9a1-04f56668a6ad` | `emergence-full-seed-303` |

All three were produced from Resonance Field commit `8ad07a5213d24c489a3223773b04d478f1807f24` under the `full` arm. Each run contains 20 initially equivalent agents and 800 decision events.

The machine-readable source of truth is `configs/w0/first-cohort.json`.

## Artifact staging

Stage the three canonical Resonance Field artifact directories under one root:

```text
artifacts/
  emergence-full-seed-101/
    experiment.json
    agents.csv
    events.jsonl
    tasks.csv
    traces.csv
  emergence-full-seed-202/
    ...
  emergence-full-seed-303/
    ...
```

The PostgreSQL dump may be retained for independent replay/debugging but the W0 compatibility adapter does not require it for the initial passport export.

## Run

```bash
python -m resonance_world.w0_campaign \
  configs/w0/first-cohort.json \
  artifacts \
  evidence/w0/first-cohort
```

The runner refuses admission when a staged Field does not match the manifest run ID, code SHA, seed/ablation identity, or expected population size.

## Outputs

```text
evidence/w0/first-cohort/
  cohort-summary.json
  field-registry.json
  passports.jsonl
```

The outputs are deterministic for identical source artifacts.

`cohort-summary.json` records:

- Field count;
- total agent count;
- passport count;
- resolved evidence-reference count;
- distinct evidence-digest count;
- SHA-256 of the Field registry;
- SHA-256 of the passport stream.

`field-registry.json` records the three source Field identities and exact run provenance.

`passports.jsonl` contains one canonical Agent Passport per source agent.

## What this proves

A successful import demonstrates that:

1. multiple independently completed Fields can coexist behind one World protocol;
2. sixty agents can be enumerated without global identity collision;
3. passports can be derived from source evidence rather than self-description;
4. every exported passport claim can resolve back to hashed source evidence;
5. repeated imports are deterministic.

## What this does not prove

Historical artifact ingestion is post-hoc and therefore cannot measure live observation overhead. It does not by itself satisfy the matched control-versus-observed non-interference experiment in Issue #1.

It also does not establish portable capability. `home_dependency_score` and `portable_capability_score` remain unset until W1 performs controlled transfer tests.

W0 remains open until the live non-interference gate is measured and the full first-cohort evidence is published.
