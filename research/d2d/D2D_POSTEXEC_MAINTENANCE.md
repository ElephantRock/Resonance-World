# D2d Post-Execution Apparatus Hardening

This maintenance record is **post-execution engineering work** performed after authoritative D2d workflow `33701860334` completed and after its `D2d-A0` evidence was preserved.

It does not rerun, repair, replace, or reinterpret the D2d scientific request stream. It does not modify the frozen provider output, evaluator result, cohort, thresholds, registered minimum N, attempted N, or D2d classification.

## Review findings addressed

1. **Provider substrate integrity.** The shard aggregator now rejects a shard unless its recorded model is exactly `glm-5-turbo` and its temperature is exactly `0.8`; accepted substrate metadata is preserved into canonical provider output and its manifest.
2. **Registered exposure provenance.** The evaluator now requires each primary arm to carry the registered development-case count, exact logical-call count, and complete call-record list before its actions can enter scientific scoring. Call records must also identify the frozen model and temperature. A malformed or truncated arm becomes a pair-integrity defect rather than analyzable evidence.
3. **Sample-size provenance.** The original frozen `D2D_SAMPLE_SIZE.json` is not rewritten. `D2D_POSTEXEC_SAMPLE_SIZE_CORRECTION.json` records the exact formula implied by the frozen inputs and the reproducible value `77.07462615601175`, while preserving the historical stored value `77.06764511331945`. The registered minimum remains 88 analyzable pairs per schema and attempted N remains 96 per schema; no scientific decision changes.
4. **Shallow merge-base finding.** The preexecution workflow already uses `actions/checkout` with `fetch-depth: 0`, so the review's shallow-history failure mode is not present on the integration head.

## Boundary

These changes harden future use of the archived apparatus and make review provenance explicit. They do not make the historical D2d stream analyzable: the authoritative campaign still has 384 attempted pairs, 0 complete pairs, 384 failed pairs, and 0 analyzable pairs in every schema.

No Mechanism Registry transition is authorized. Production/default Historical Substrate remains **OFF**.
