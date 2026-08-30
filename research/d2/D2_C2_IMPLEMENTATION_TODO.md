# D2-C2 zero-provider implementation TODO

This checklist is subordinate to issue #180 and does not authorize provider execution.

- [ ] Port the frozen C1 per-pair scientific treatment into a C2 runner with explicit `--start-pair` / `--end-pair` bounds.
- [ ] Set local provider concurrency to 1 inside each shard runner.
- [ ] Generate the fresh 2,200,000-base C2 cohort and freeze its aggregate hash.
- [ ] Add shard-output schema and shard manifest with exact registered range.
- [ ] Add credential-free aggregator that canonicalizes exactly 360 attempted pairs.
- [ ] Make missing shard artifacts explicit failed attempted ranges without synthetic scientific outcomes.
- [ ] Reject duplicate, foreign, overlapping, mismatched, or pre-classified shard data.
- [ ] Port/freeze evaluator against canonical C2 provider output.
- [ ] Add deterministic synthetic fixtures covering complete, one-shard-missing, two-shard-missing, and corrupt-shard cases.
- [ ] Add dedicated C2 zero-provider preexecution workflow.
- [ ] Ensure no provider secret is available in audit, aggregation, or evaluator jobs.
- [ ] Add provider workflow only after all zero-provider gates pass; trigger must remain absent until final authorization marker commit.
- [ ] Post exact scientific candidate SHA and audit workflow IDs prospectively to issue #180.
- [ ] Add authorization marker only as the sole post-lock change.

Production/default Historical Substrate remains OFF throughout.
