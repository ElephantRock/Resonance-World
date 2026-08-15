# D1 result — reproduce a developed individual specialist capability

Status: **complete classifiable confirmatory study**.

Classification: `D1-S3` / `d1_capability_reproduction_supported`.

Authoritative preregistration: issue #160. Exact classifiable scientific candidate: `46010232f9b73e481eaa6de4b60cc721f4ad2273`. Authoritative confirmatory workflow: `31861296898`. Evaluator-only transport repair: `83f4b5d1877095163e8e5911bffb7f908675c96b`, workflow `31861464055`.

## Product question

Can Resonance characterize the developmental conditions that produced a useful capability in Environment A and deliberately produce the same class of capability in a fresh Environment B without transferring source-private capability state?

D1 intentionally tests the smallest controlled version of that product claim: an individual specialist capability in the deterministic Field skill/practice substrate.

## Registered outcome

Thirty-six independent source/destination Field pairs were frozen prospectively, with 12 pairs for each of three opaque skill aliases. All confirmatory seeds were disjoint from D1-0 development/calibration seeds.

Mean held-out specialist success rates:

| arm | mean |
|---|---:|
| `fresh_no_development` | 30.534% |
| `source_developed` | 88.889% |
| `reproduced_protocol` | 90.549% |
| `private_state_oracle` | 89.171% |

The private-state oracle was diagnostic only and permanently product-ineligible.

### P0 — source capability production

Estimand: mean(`source_developed - fresh_no_development`).

- estimate: **+58.355pp**
- n: 36 Field pairs
- normal two-sided 95% CI: **[+56.562pp, +60.149pp]**
- normal one-sided 95% lower bound: **+56.850pp**
- fixed-seed 100,000-replicate bootstrap two-sided 95% CI: **[+56.510pp, +60.069pp]**
- bootstrap one-sided 95% lower bound: **+56.825pp**
- registered gate: **PASS**

The controlled source ecology therefore produced a held-out specialist capability relative to the fresh baseline.

### P1 — destination capability acquisition

Estimand: mean(`reproduced_protocol - fresh_no_development`).

- estimate: **+60.015pp**
- n: 36 Field pairs
- normal two-sided 95% CI: **[+58.938pp, +61.092pp]**
- normal one-sided 95% lower bound: **+59.112pp**
- fixed-seed bootstrap two-sided 95% CI: **[+58.941pp, +61.068pp]**
- bootstrap one-sided 95% lower bound: **+59.115pp**
- registered gate: **PASS**

Fresh destination Fields therefore acquired the registered capability under the frozen Capability Artifact/development protocol.

### P2 — reproduction fidelity

Estimand: mean(`reproduced_protocol - source_developed`).

Registered non-inferiority boundary: **−5.9314pp**, derived from the prospectively frozen 90% reproduction-fidelity product convention. The margin is classified **conventional**, not natural materiality.

- estimate: **+1.660pp**
- n: 36 Field pairs
- normal two-sided 95% CI: **[+0.006pp, +3.314pp]**
- normal one-sided 95% lower bound: **+0.272pp**
- fixed-seed bootstrap two-sided 95% CI: **[+0.022pp, +3.288pp]**
- bootstrap one-sided 95% lower bound: **+0.293pp**
- registered non-inferiority gate: **PASS**

The descriptive fidelity ratio `(reproduced-fresh)/(source-fresh)` was `1.02845`. This ratio is descriptive; D1 did not preregister a superiority claim for reproduced versus source capability.

## Integrity result

All registered integrity gates passed:

- exact scientific candidate identity;
- exact frozen plan and lock identity;
- 36 unique confirmatory Field-pair seeds;
- development/confirmatory seed disjointness;
- 12/12/12 skill-alias balance;
- source/destination identities disjoint in every pair;
- no source agent identity, reconstructive source/environment seed, private practice state, conversation state, evaluator truth, or evaluation answers in the exported Capability Artifact;
- Capability Artifact schema intact;
- private-state oracle product-ineligible;
- confirmatory execution integrity intact;
- production/default Historical Substrate OFF.

Artifact target inference matched the source capability target in all 36 confirmatory pairs; this is descriptive because an inference miss would have been a scientific reproduction failure rather than an apparatus failure.

## Evaluator transport repair

The original frozen evaluator in workflow `31861296898` failed before reading the confirmatory output because the uploaded artifact was addressed with the wrong local path. The authoritative 36-pair output itself had already run twice and byte-compared successfully.

A prospective evaluator-only repair commit `83f4b5d1877095163e8e5911bffb7f908675c96b` changed only workflow artifact retrieval/path handling. It downloaded the exact frozen artifacts from the original run, verified the plan, lock, and confirmatory-output hashes before evaluation, and invoked the unchanged frozen evaluator twice against scientific candidate `46010232...`. The two evaluator runs produced byte-identical `result.json`, `audit.json`, and `manifest.json`, with exit status 0/0. No confirmatory Field pair was rerun.

## Provenance

- scientific candidate: `46010232f9b73e481eaa6de4b60cc721f4ad2273`
- authoritative confirmatory workflow: `31861296898`
- evaluator repair commit: `83f4b5d1877095163e8e5911bffb7f908675c96b`
- evaluator repair workflow: `31861464055`
- confirmatory plan SHA-256: `8223d441f8399d89901ecd7f704d8744c571a8035c7ebdc94150435f92ba8858`
- lock report SHA-256: `15f479faae0f9d2a9ec9d859b1359c103c2d1075628ba1e872cdb71a900e5cfd`
- frozen confirmatory output SHA-256: `f65e67fee740a5f0a2471479af08e18571c8592ca1e6c6f34c5c2486770df936`
- result SHA-256: `cd68485ff3ef1aeb783e442b5fd7fe7aa73132b620a4c57c63e5c3ce62d165e8`
- audit SHA-256: `2912519f61eaa086678cb7ef817c994a83ed36d683b48a44bc40a32260c88e6d`
- manifest SHA-256: `3fbf05c6dc38a72c008b2d9445bef538ae45ed7a56aaebbd33ecb6c9a61cec3f`
- original apparatus artifact: `9240646128` (`sha256:d9d7d3195b1a876938d903acf32e05f9065cad25023148e0ef18ab0a891f5b91`)
- confirmatory-output artifact: `9240651101` (`sha256:b1baac6c2ae582a4566bbd5ea3950ae6a902666aa6e3dfdb1cf56f7eea5dc659`)
- repaired evaluation artifact: `9240703702` (`sha256:a8958c107dfecfedf11e10da9dc45e0ef16aae6ba7d1421543a4a7a071c98844`)

## Bound claim

Within the preregistered deterministic individual-specialist Field substrate, Resonance prospectively characterized a capability-production contract from source development and used that contract to produce a statistically supported held-out capability in fresh destination Fields without passing source-private capability state through the Capability Artifact. The reproduced capability was non-inferior to the source-developed capability under the prospectively conventional 90% fidelity criterion.

This does **not** establish stochastic/model-based capability learning, transfer of semantic knowledge between foundation models, team/relationship reproduction, institutional reproduction, naturalistic domain transfer, or self-creating environments.

`D1-S3` is initial discovery support only. A separately preregistered fresh D1b cohort is required before any `internally_replicated` registry status. The experiment does not self-promote the Mechanism Registry.

No confirmatory D1 retuning or rerun is authorized after classification. Production/default Historical Substrate remains OFF.
