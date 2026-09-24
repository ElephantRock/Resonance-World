# D2-vNext-Q1 construction status

Tracking issue: #290  
Construction PR: #291  

## Frozen and constructed

The prospective qualification decision contract, staged sample sizes, mixed-schema shard topology, physical-send ceilings, joint-clearance rule, future resource-feasibility gate, and bounded terminal-failure observability schema are frozen as construction inputs.

The following credential-free construction surfaces now exist:

- fresh deterministic namespace `rw.d2-vnext-q1-acquisition-qualification.v1`;
- Q1-A cohort commitment `21ae386da6fdba2883a331864fcaffc51f9fa8adb58aa43ee9d68519cadc3686`;
- Q1-B cohort commitment `41124075eeda43439b392997b090ed7fe11275271b4bae86bc619371f86a750e`;
- deterministic Q1-A/Q1-B cohort locks and mixed-schema shard maps;
- byte-for-byte materialization checks and predecessor/cross-stage seed-overlap checks;
- Q1-specific bounded terminal-failure capture integrated around the frozen S2 supported-product call mechanism;
- stage-aware runner with fail-closed marker/env authorization;
- aggregation preserving bounded terminal-failure records without raw response content;
- qualification-only evaluator implementing the Q1-A continuation gate and Q1-B exact completion lower bounds/resource gate;
- independent Q1-B exchangeability-review schema and finalizer;
- zero-provider fixtures covering exact completion, eligible retry success, retry failure, terminal-adapter rejection, runtime failure, budget/attribution defects, raw-content non-retention, exact lower-bound sizing, and finalization boundaries;
- inert marker-triggered Q1-A and Q1-B provider workflows, with Q1-B divided into six sequential four-shard execution waves.

## Remaining construction closeout

Before the construction candidate can be recorded for independent review:

1. all current-head credential-free CI checks must be green, including repository-wide CI, Q1 contract, Q1 materialization, and Q1 preexecution;
2. the marker-triggered Q1-A/Q1-B workflow definitions must remain syntactically accepted by GitHub while no execution marker is present;
3. PR #291 must be updated with the exact final marker-absent candidate SHA and successful CI run identities;
4. issue #290 should receive the same exact construction-freeze record.

These closeout steps do not authorize provider/model execution.

## Authority

Provider/model execution remains **NOT AUTHORIZED**. There is no `RUN_D2_VNEXT_Q1_A` or `RUN_D2_VNEXT_Q1_B` marker. Construction work remains credential-free. A future Q1-A execution requires a separate explicit human authorization naming the exact marker-absent candidate SHA and authorizing at most 4,608 physical provider sends. Q1-B remains a later separate authorization boundary after a frozen Q1-A PASS closeout.
