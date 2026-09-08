# D2-vNext-S1 source-acquisition closeout

## Registered outcome

D2-vNext-S1 completed once under the frozen candidate
`816b19273632cd28a77df510bc9f252eaeb08766` and sole-child authorization commit
`da56e93bb98c339dc0caf738f5132d091ede6a90`.

Authoritative workflow `34183465027`, attempt 1, concluded operationally `success`.
All 24 provider-shard jobs, canonical aggregation, and the frozen evaluator completed.
The workflow must not be rerun.

The frozen evaluator classification is **`D2-vNext-S1-A0` —
`acquisition_envelope_integrity_or_minimum_n_failure`**.

- Attempted pairs: 384
- Complete pairs: 0
- Failed pairs: 384
- Minimum analyzable pairs required per schema: 88
- Analyzable pairs: 0 for every registered schema
- Common confirmed acquisition budget: none
- Positive-control continuity: not established
- 160/80/40 scientific gates: not entered

This is a completed but non-inferential calibration outcome. It is not evidence that
40, 80, or 160 development cases succeed or fail to acquire the registered source
capabilities.

## Transport and completion evidence

The frozen fail-closed Coding Plan transport contract passed with no registered
transport-integrity defects. The campaign observed 398 physical provider sends,
well below the 24,000 campaign ceiling. This establishes bounded registered sends;
it does **not** establish successful scientific logical-call completion.

All 384 pair records terminated as `provider_pair_failure`, with `error_type=RuntimeError`
and one shared fingerprint:

`12a1edde2a58000642c02a20fe4b32986d44495eac7c7a066f88029d493821de`

Under the frozen runner's fingerprint rule, the deterministic preimage is:

`RuntimeError:Hermes returned a non-completed scientific logical call`

That local error is raised when the supported Hermes result fails the frozen
completion predicate. The canonical evidence does not preserve the raw Hermes
result or an upstream finish reason, so it does not establish which specific
non-completion predicate or provider-side cause applied. No post-outcome causal
label is assigned.

As a bounded diagnostic only, shard 0 attempted 16 `threshold_at_4` pairs and
recorded 16 logical calls started, 0 completed, 16 logical-call failures, and
18 physical provider sends, with no budget or unexpected-outbound blocks. Thus
every pair in that shard failed on its first registered logical call. The canonical
aggregate does not preserve exact campaign-wide logical-call counters, so that
shard-specific statement is not generalized beyond shard 0.

## Authoritative artifacts and hashes

Canonical provider artifact:
- ID: `10039977080`
- digest: `sha256:6f9768cee1e855a97078705c9761f21a9321f133fa4d7cfefe81a5c34087edaf`
- provider output SHA-256: `757389293069e8aebfa4c78f8e2c036b9040b5674416730c72c49b332bbf0fd5`
- provider manifest SHA-256: `fad64992819b073ee1b3c9461994ff8c800f74f1a6416acbf047331b09b27248`

Frozen evaluation artifact:
- ID: `10039982178`
- digest: `sha256:4e65775d12a531b8975d81b80cd825bb16131e770632c67444ed78d04643d15d`
- result SHA-256: `4597df707287f32545a71cbc34fe7b396fe4ff71a3f09dd25af5ed2b5b8f1543`
- evaluation manifest SHA-256: `da872cc2d8b74d2bee75e3199f8b1532691a700c539f51c8d0eb23359f820108`

Frozen apparatus commitments:
- cohort pairs: `5f650a4c0c8054942781698f77dc918c50c1f3f685f7b9f1e7f1ce7539d4be8c`
- cohort lock file: `8ea44fbeaccfb6e6031a1980e8b498afe58fc805084353055e56524b83511b88`
- shard map: `22ba9b7cb26aeaf349ed562aab2e62aab643f73ca89a632a06bf7ca419bba1ef`
- PLAN: `6575bbe9f4801072b639d1cbe9f0fb3d6ca390fd2e6a40a4299d2f21328af9cb`
- request plan: `c0284da1f010764032bd26549e359dfc8ab3818bff60b8bb0cfe976797b65ea9`
- sample size: `ffda8effa314419ed8e7888f3fdb6e7ccae1c8d8a3da956584ec0bda17f0482a`
- schema suite: `451bc172fe58fdef3561f3987a3f830de14b6b92861b2fb03617b42c28480ee7`

## Scientific and governance interpretation

The acquisition envelope is not interpretable. D2e has no acquisition protocol
identified from this result, and these calibration schemas are not authorized for
D2e reuse. There is no registry promotion, Acceptance action, replacement,
adaptive-N rescue, or same-stream rerun.

The next programmatic question is engineering: prospectively qualify a
representative D2 scientific logical-call completion envelope on the intended
pinned Hermes/Coding Plan substrate before constructing any fresh
source-acquisition calibration stream.

The claim ceiling remains a single supported-product, synthetic,
individual-agent source capability-acquisition calibration under four frozen
D2-vNext-S1 schemas, requested model `glm-5.3`, with effective upstream model
identity unobserved. There is no capability-reproduction, schema-generalization,
provider/model-generalization, naturalistic, team/swarm/institution,
production-readiness, registry, Acceptance, or Historical Substrate claim.

Historical Substrate remains OFF.
