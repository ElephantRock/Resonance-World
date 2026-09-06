# D2d-S2 source-capability acquisition closeout

## Outcome

The authorized D2d-S2 source-capability-acquisition campaign completed once, on the exact frozen scientific candidate `62a54c3d38a238a95744cba46a4e9e0241477217`, through sole-child authorization commit `20c76cb9826589a02de9c82112cb0f10170c7d78`.

Authoritative workflow: `34059455948`, attempt 1, conclusion `success`.

The frozen evaluator classified the result as **D2d-S2-A0 — acquisition_envelope_integrity_or_minimum_n_failure**.

- attempted pairs: 384
- complete pairs: 0
- failed pairs: 384
- analyzable pairs: 0 in every schema
- minimum required analyzable pairs: 88 per schema
- positive-control continuity: not established
- common acquisition budget: none
- confirmatory 160/80/40 gates: not entered

This is a valid campaign closeout but a non-inferential scientific result. It does **not** show that 40, 80, or 160 labeled examples are insufficient for capability acquisition.

## Provider/runtime evidence

All 384 registered pair failures have the same frozen-runner error fingerprint:

`f2f3f6035b2c5e66e2dca9e16ac270fec911215205034703a0fab02e21099b41`

Under the frozen runner, that fingerprint is generated from:

`RuntimeError:provider_http_failure:429:body_read_ok`

Accordingly, the durable evidence establishes an HTTP 429 terminal response for every registered pair. Raw provider error bodies were not preserved, so the underlying provider-policy cause—rate limit, quota, account policy, or another 429 condition—is **not established**.

The evaluator reports its hardened transport-integrity field as passed because no completed record violated the complete-record transport contract. There were zero completed pairs, so this must not be interpreted as evidence that campaign-scale transport succeeded.

## Frozen provenance

- cohort commitment: `d74348dc2d15e2b1c1959726faa9ae473e01a3aeed46bcdc3b1c240e918b3d9f`
- plan SHA-256: `4206e6d51f06873dcebcb0840598b8154b0a52e84f2a89ccdc958c892260cd8d`
- request-plan SHA-256: `2094423d2e7d16ff124e46ba32c99892d9fee77438bfe87804930ff6e5296c46`
- schema-suite SHA-256: `1ae69bea53656459c3fb98a20f5bee46592be30e3cd644a695a913b92be66328`
- sample-size SHA-256: `a094d43dc96aeff3a3f466259170125caf2e3705120a98a83367fe0686e89f30`
- cohort-lock file SHA-256: `e4b5719a77c35384eb0976a5f364c91f930efb675d23de9998d6913c6245133a`
- shard-map SHA-256: `4ddd2513ed630fca3eb732a0515268b3fa2d3de35de055c6df8793054d779f74`
- canonical provider output SHA-256: `87478c3e2bcace47ee3022af94a9164a22b271651eea1d72cf7b27e3559ec70d`
- provider-output manifest SHA-256: `5977cd47a6c55f230fa801e5889455e941cf1b005c3fb2bee060a6ad10b65359`
- evaluator result SHA-256: `ce462acf863de8a00aaa4e4db42560d359d0e8865d063d5f204c5e25f55872c7`
- evaluation manifest SHA-256: `32b62510678c1df0e8a9b811209a1c52a61d02545a05b9fb9ddc116bc7c92783`

Durable workflow artifacts:

- canonical provider output: artifact `9997043003`, digest `sha256:cb44db6b6cc23e95c0fe9cf055406abcd018dcf437560164445ce22a4070525f`
- frozen evaluation: artifact `9997046414`, digest `sha256:a1a8a39c8b9dedde8564f645691ab45a224854ca9caf0d048c9cbdab25619ec6`
- all 24 registered provider-shard jobs completed and uploaded their shard evidence.

## Scientific interpretation

D2d-S2 does not identify an acquisition protocol and does not enter D2e. It supplies no efficacy evidence about the 40/80/160 exposure hierarchy because minimum analyzable N was not reached in any schema.

The immediate bottleneck is again provider/runtime compatibility, now localized more specifically to campaign-scale HTTP 429 behavior despite the earlier tiny hardened General API requalification. Before any new source-acquisition characterization campaign, a separate prospective engineering stream should determine a campaign-safe request schedule or provider constraint under the same fail-closed transport principles. Any external provider calls for that engineering work require separate authorization.

The same D2d-S2 request stream must not be rerun, rescued, resized, or selectively replaced.

## Governance

- no Mechanism Registry transition is authorized or supported;
- D2 remains `internally_replicated`;
- no Acceptance-plane promotion is entered;
- no D2c/D2d/D2d-S2 rerun or adaptive-N rescue is authorized;
- no Historical Substrate activation is authorized;
- production/default Historical Substrate remains **OFF**.

## Claim ceiling

No scientific source-acquisition efficacy claim is supported. The result is limited to this one-shot, single-model, synthetic individual-agent calibration execution and its observed HTTP-429/minimum-N failure. It supports no capability-reproduction, schema-generalization, provider/model-generalization, naturalistic, team/swarm/institution, production-readiness, or Historical Substrate claim.
