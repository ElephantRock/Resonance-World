# D2-C2 preauthorization checklist

This checklist is subordinate to issue #180 and does not authorize provider execution.

- [x] Port the frozen C1 per-pair scientific treatment into a deterministic shard-bounded C2 runner.
- [x] Set local provider concurrency to 1 inside each shard runner.
- [x] Generate the fresh 2,200,000-base C2 cohort and freeze its aggregate hash.
- [x] Add shard-output schema and shard manifest with exact registered range.
- [x] Add credential-free aggregator that canonicalizes exactly 360 attempted pairs.
- [x] Make missing shard artifacts explicit failed attempted ranges without synthetic scientific outcomes.
- [x] Reject duplicate, foreign, overlapping, mismatched, or pre-classified shard data.
- [x] Port/freeze evaluator against canonical C2 provider output.
- [x] Add deterministic synthetic fixtures covering complete, one-shard-missing, two-shard-missing, and corrupt-shard cases.
- [x] Add dedicated C2 zero-provider preexecution workflow.
- [x] Ensure no provider secret is available in audit, aggregation, or evaluator jobs.
- [x] Add marker-gated provider workflow with 18×20 shards, local concurrency 1, matrix max-parallel 4, 240-minute shard timeouts, immutable artifacts, credential-free aggregation, and deterministic evaluation.
- [ ] Obtain successful general CI and dedicated zero-provider C2 preexecution audit on the exact final scientific candidate.
- [ ] Post exact scientific candidate SHA, cohort hash, and audit workflow IDs prospectively to issue #180.
- [ ] Add `research/d2/RUN_D2_C2_CONFIRMATORY` only as the sole post-lock change after prospective posting.

Production/default Historical Substrate remains OFF throughout. No registry promotion is authorized.
