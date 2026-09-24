# D2-vNext-S2 source-acquisition closeout

## Registered outcome

D2-vNext-S2 completed once under frozen candidate `d65f5bb803af966b79622d6104f00756b7e9e8c7` and sole-child activation commit `a5d99f9302166b3abb468bd84971c6abecd3dd16`.

Authoritative workflow run `35909017872`, run/attempt 1, concluded operationally `success`. All 24 provider-shard jobs completed successfully. The same request stream must not be rerun.

The frozen evaluator classification is **`D2-vNext-S2-A0` — `acquisition_envelope_integrity_or_minimum_n_failure`**.

- Attempted pairs: 384
- Complete pairs: 205
- Failed pairs: 179
- Minimum analyzable pairs required per schema: 88
- `threshold_at_4`: 96 attempted, 60 complete/analyzable, 36 failed
- `parity_pair`: 96 attempted, 71 complete/analyzable, 25 failed
- `interval_pair`: 96 attempted, 58 complete/analyzable, 38 failed
- `pairwise_order`: 96 attempted, 16 complete/analyzable, 80 failed
- Confirmatory gates entered: no
- Positive-control continuity: not established because the minimum-N condition failed
- Common confirmed acquisition budget: none

The four analyzable counts sum to the 205 complete pairs. The frozen evaluator reports no global defects, pair defects, or diagnostic defects. There is therefore no additional evaluator-eligibility loss after pair completion in this run: within each registered schema, complete pairs are the analyzable pairs.

The apparatus passed while the confirmatory experiment remained non-inferential. Descriptive developed-versus-fresh differences of roughly 0.70–0.76 across several cells are not confirmatory evidence because every registered schema remained below the prospectively frozen minimum analyzable N=88.

## Transport and pair-failure evidence

Transport integrity passed with 14,509 physical provider sends against the frozen 48,000 campaign cap, and no transport/integrity defects were recorded. Apparatus execution success does not substitute for schema-level analyzability.

All 179 failed pair records have:

- `failure_class=provider_pair_failure`
- `error_type=RuntimeError`
- one shared fingerprint: `6c4a6ce59b69ad55cfd186ea90d43a07eb2f694cc17f54e284879eaa5304a6f9`

Under the frozen runner's fingerprint rule, the verified preimage is:

`RuntimeError:D2-vNext-S2 logical call has no accepted exact completion`

This establishes the bounded application-level failure class. It does **not** establish which arm, phase, logical-call index, first-attempt parse diagnostic, or optional-retry diagnostic terminated each failed pair. `run_pair_safe` collapses that exception into the pair-level fingerprint, so those intra-pair causes are not preserved in the canonical failed-pair record and must not be invented post hoc.

The observed schema-specific completion yields are therefore descriptive evidence of strongly heterogeneous attrition, with `pairwise_order` especially low. They do not by themselves identify why the attrition differs by schema.

## Authoritative artifacts

Canonical provider output:
- artifact ID: `10783810505`
- artifact digest: `sha256:a0bd3ee00d83e2a016f90d8efed43e4915d5085bb2e6c2efefaeca6ec5a91a57`
- provider output SHA-256: `1419144f035ad1eafb3604f0a1859b134a2f9ddb280e1a04e4959d75e31042b2`

Frozen evaluation:
- artifact ID: `10783039997`
- artifact digest: `sha256:1f9ccfb6ee3c3a8d00ce7cb3a66a2d8ae62475a45decd19c9a19bc504d051dc6`
- result SHA-256: `f187defd4b27ca8f32858332c7e3448355d077a539574c2b97ffba1b919f4487`

Frozen cohort commitment: `a61a2667b088301bfedc9158662511179a4e806d4aaf679fb865e1c42ded6c94`.

## Scientific interpretation

This outcome does not establish that 40, 80, or 160 labeled cases succeed or fail to acquire any registered source capability. It does not authorize Acceptance, Mechanism Registry promotion, Historical Substrate activation, D2e execution, or a same-stream rescue/rerun.

The next programmatic question is diagnostic rather than confirmatory: quantify schema- and shard-level completion attrition from the preserved artifacts, retain the explicit non-identifiability of the terminal intra-pair failure phase, qualify a future acquisition envelope prospectively, and only then construct a fresh successor confirmatory stream whose acquisition design has a credible path to the frozen per-schema analyzability floor.

Historical Substrate remains OFF.
