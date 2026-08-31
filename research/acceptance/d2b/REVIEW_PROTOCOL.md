# D2 Internal-Replication Independent Acceptance Review Protocol

## Status

**Prospective Acceptance-plane apparatus. No substantive external review is authorized by this file alone.**

D2-C2 established the registered D2 mechanism at `discovery_supported` after independent Acceptance on issue #183. D2b is a separately frozen fresh replication of that same mechanism and its frozen evaluator emitted `D2b-S3` after 360/360 analyzable pairs with no integrity defects.

The experiment, aggregator, and evaluator cannot promote themselves. The external reviewer must not be called unless `research/acceptance/d2b/RUN_REVIEW` is added as the sole post-lock change to this branch and the review runner independently verifies the exact preserved C2 and D2b evidence on GitHub `main` before any provider request.

Production/default Historical Substrate remains OFF.

## Transition under review

The sole promotive transition is:

`discovery_supported -> internally_replicated`

This review must not grant `schema_generalized`, `model_generalized`, `naturalistic_validated`, `integration_eligible`, `evolution_eligible`, or any higher authority. Internal replication is a fresh-data replication of the same registered mechanism under the same claim scope. Schema/model/naturalistic generalization are later rungs and are not prerequisites for this rung.

## Independent acceptor

- provider: Z.AI
- model: `glm-5-turbo`
- role: `independent_acceptance_plane_reviewer`
- proposer-side model: GPT-5.6 Sol
- substantive reviewer calls: exactly one valid substantive decision
- retries: transport/provider failure, returned-model drift, or invalid/unparseable decision recovery only
- a valid unfavorable decision is authoritative and must never be rerun to seek another judgment
- thinking: disabled
- sampling: disabled
- temperature: `0.0`
- structured JSON response

The proposer and acceptor identities must be distinct.

## Hard mainline-preservation gate

Before any Z.AI request, the runner must verify from GitHub `main` at minimum:

- registry node `d2_stochastic_capability_reproduction` is exactly `discovery_supported`;
- prior external D2 review preserved on main says `ACCEPT discovery_supported` for `proposed -> discovery_supported`;
- C2 scientific candidate `e8f719c3698b1f0180db07409c5eefd93facefbf`;
- C2 authorization `88ab2e26efaff6434606b16e9a4dd162784e6279`;
- C2 workflow `33312336871`, evaluator class `D2-S3`, fresh cohort `8341d573da2d626858d25abfb381c499cc4d3c640749045b0141c985828fc676`;
- D2b scientific candidate `cf938d895020120a0f979d035f0e428065e05140`;
- D2b authorization `b1402081d8a3252b28a788b7e5c75544aaacbe6d`;
- D2b workflow `33353320198`, attempt 1, success, 18/18 shards success, no rerun;
- D2b evaluator class `D2b-S3` / base `D2-S3`;
- D2b cohort `b4d8f39b9730de6869b6b3c3f9ceb4d16c76214b8eee9437c2bca62e85286b23`, distinct from C2;
- D2b evaluator result SHA-256 `1a602e3813f4a4f1c58e82c3dba8feb42485fa44cda11a23d289b0de72a27757`;
- D2b provider-output content SHA-256 `937ff737ec53b110542a75ee9e5a6e6f68ad31dab195446efc839f3cc163724f`;
- D2b preservation commit `b4494408b07d8404ced24f5edb786eb2013c01f9` is on main history;
- both studies satisfy minimum-N and integrity gates;
- registry promotion remains disabled in D2b closeout;
- Historical Substrate remains OFF.

Any failure of this gate prevents the provider call.

## Mandatory reviewer checklist

The reviewer must adjudicate each exact criterion once:

1. `registry_currently_discovery_supported`
2. `prior_discovery_acceptance_independent_and_preserved`
3. `c2_is_classifiable_discovery_study`
4. `d2b_is_fresh_replication_not_rerun_or_repair`
5. `d2b_identity_seed_cohort_fresh_and_disjoint`
6. `d2b_preregistered_before_provider_outcomes`
7. `scientific_contract_not_retuned_from_c2_outcomes`
8. `c2_and_d2b_p0_p1_p2_serial_gatekeeping_pass`
9. `minimum_n_and_integrity_pass_both_studies`
10. `capability_artifact_private_state_boundary_intact`
11. `no_same_stream_rerun_used_for_d2b`
12. `claim_ceiling_single_model_synthetic_individual`
13. `replication_supports_internal_replication_only_not_generalization`
14. `d2b_preservation_record_mainline_before_acceptance`
15. `historical_substrate_off`
16. `acceptor_distinct_from_proposer`

Allowed criterion statuses: `PASS`, `FAIL`, `INSUFFICIENT`. Missing material evidence must never be assumed.

## Allowed decisions

- `ACCEPT internally_replicated`
- `REJECT promotion; retain discovery_supported and document reason`
- `DEFER pending specified evidence/integration condition`

If the reviewer chooses `ACCEPT internally_replicated`, all 16 criteria must be `PASS`.

## Maximum accepted claim

If accepted, the claim may be no broader than:

> In two prospectively registered fresh cohorts of the same single-model synthetic individual-agent Field substrate using Z.AI `glm-5-turbo`, including an independently executed fresh replication, capability developed through stochastic model-mediated local experience was reproducibly reproduced in fresh destination agents through the registered public Capability Artifact mechanism beyond description-only and fresh controls while satisfying the preregistered 90% source-fidelity criterion.

No weight-learning, schema-generalization, cross-model/provider, naturalistic, team/swarm/relationship/institutional, composition, market, environment-spawning, production-readiness, or Historical Substrate claim is authorized.

## Authority boundary

The external review writes an immutable decision artifact and issue comment only. It cannot mutate the Mechanism Registry. An accepted decision requires a separate append-only promotion record and registry change.

Production/default Historical Substrate remains OFF.
