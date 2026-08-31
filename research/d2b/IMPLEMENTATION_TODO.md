# D2b implementation checklist

Status: **zero-provider implementation work only**.

The replication study is preregistered on issue #186. This checklist is not provider authorization.

## Scientific identity

- [x] Same mechanism node as D2-C2, not a posthoc child.
- [x] Replication target is later eligibility for `discovery_supported → internally_replicated`.
- [x] D2-C2 scientific thresholds/N/model/task law are retained without outcome-based retuning.
- [x] Fresh namespace reserved at `3,200,000`.
- [x] Historical Substrate remains OFF.

## Before candidate freeze

- [ ] Deterministically materialize all 360 fresh pair locks from the frozen R2 substrate generator.
- [ ] Verify exact zero source/destination feature overlap for every pair.
- [ ] Verify exact zero development/evaluation feature overlap for every pair.
- [ ] Prove no seed/case/request identity overlap with C1/C2/calibration records.
- [ ] Freeze aggregate cohort hash.
- [ ] Freeze 18×20 shard map.
- [ ] Replace request-plan draft with final request plan carrying exact cohort hash.
- [ ] Derive D2b provider runner from D2-C2 with only study/cohort identity changes.
- [ ] Derive D2b aggregator from D2-C2 with only study/cohort identity changes.
- [ ] Derive D2b evaluator from D2-C2; statistical gates must be unchanged.
- [ ] Add zero-provider tests for cohort, shard map, missing shard, duplicate/foreign/preclassified input, model/temperature/request drift, N=329→S4, and deterministic synthetic S0–S3 behavior.
- [ ] Add dedicated credential-free D2b preexecution audit.
- [ ] Ensure provider credential is scoped only to later provider shard jobs.
- [ ] Ensure authorization marker is absent.
- [ ] General CI success.
- [ ] Dedicated D2b audit success.
- [ ] Post exact candidate SHA + cohort hash prospectively to issue #186.

## Provider boundary

Do not create `research/d2b/RUN_D2B_REPLICATION` until separate explicit authorization after the exact scientific candidate is frozen and posted to #186.

Any provider execution must be run-attempt 1 only. No shard/job rerun is permitted after provider execution starts. No registry mutation belongs in the provider workflow.

## After execution

- [ ] Preserve all shard artifacts, canonical provider output, evaluator result, and hashes.
- [ ] Never replace failed registered pairs.
- [ ] Map frozen evaluator D2 S-class one-to-one to D2b S-class in immutable closeout.
- [ ] If D2b-S3, preserve evidence first; only then construct a separate independent Acceptance-plane review for `internally_replicated`.
- [ ] Keep production/default Historical Substrate OFF unless separately and explicitly authorized.
