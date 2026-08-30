# D2 Independent Acceptance Review Protocol

## Status

**Prospective Acceptance-plane apparatus. No substantive external review is authorized by this file alone.**

The D2-C2 scientific campaign is complete and its frozen evaluator emitted **D2-S3 — `stochastic_model_mediated_capability_reproduction_supported`**. This protocol governs a separate governance adjudication. The experiment, aggregator, and evaluator cannot promote themselves.

The external reviewer must not be called unless both conditions hold:

1. `research/acceptance/d2/RUN_REVIEW` is added as the sole post-lock change to this branch; and
2. the review runner independently verifies, from GitHub `main`, that the exact D2-C2 closeout evidence has been integrated there.

Until both conditions are true, this apparatus remains zero-provider.

Production/default Historical Substrate remains OFF.

## Transition under review

D2 originated as `posthoc_motivated`, because the mechanism was motivated by inspected D1/D1b evidence.

The independent reviewer must first adjudicate whether the frozen, outcome-preceding D2 record established a valid **non-result-based** proposal transition:

`posthoc_motivated -> proposed`

This is a prerequisite finding, not a second promotive action performed by this review. If the prerequisite cannot be established from the supplied frozen record, the reviewer must reject or defer promotion. No ladder rung may be skipped.

The sole promotive transition under review is:

`proposed -> discovery_supported`

D2-C2 is one classifiable confirmatory study of the registered stochastic mechanism. This review must **not** mark D2 `internally_replicated`; that later transition requires a fresh independent D2 replication under the governance constitution.

## Independent acceptor

- provider: Z.AI
- model: `glm-5-turbo`
- role: `independent_acceptance_plane_reviewer`
- proposer-side model: GPT-5.6 Sol
- substantive reviewer calls: exactly one valid substantive decision
- retries: transport/provider failure, returned-model drift, or failure to produce a parseable allowed decision only
- a valid unfavorable decision is authoritative and must never be rerun to seek a different judgment
- thinking: disabled
- sampling: disabled
- temperature: `0.0`
- structured JSON response

The proposer and acceptor identities must be distinct.

## Hard mainline-preservation gate

Before any Z.AI request, `scripts/run_d2_independent_acceptance.py` must fetch the D2-C2 closeout from GitHub `main` and verify at minimum:

- scientific candidate: `e8f719c3698b1f0180db07409c5eefd93facefbf`
- authorization commit: `88ab2e26efaff6434606b16e9a4dd162784e6279`
- authoritative campaign workflow: `33312336871`
- campaign conclusion: `success`
- classification: `D2-S3`
- attempted pairs: `360`
- analyzable pairs: `359`
- failed pairs: `1`
- minimum analyzable N: `330`
- cohort hash: `8341d573da2d626858d25abfb381c499cc4d3c640749045b0141c985828fc676`
- integrity passed with zero global and pair-level defects
- evaluator-result SHA-256 equals the closeout-recorded `result_sha256`
- registry promotion remained unauthorized
- production Historical Substrate remained disabled

If any check fails or the closeout is absent from `main`, execution must terminate **before provider access**.

## Frozen evidence packet

Repository evidence is fetched from GitHub `main` at review time:

- `docs/mechanism-governance-v0.1.md`
- `research/mechanisms/registry.json`
- `research/d2/CAPABILITY_ARTIFACT_V0.2.md`
- `research/d2/D2_CONFIRMATORY_C1_CLOSEOUT.json`
- `research/d2/D2_C2_CONFIRMATORY_PLAN.md`
- `research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json`
- `research/d2/D2_C2_CONFIRMATORY_SAMPLE_SIZE.json`
- `research/d2/D2_C2_SHARD_MAP.json`
- `research/d2/d2-c2-confirmatory-cohort-lock.json`
- `research/d2/D2_C2_CONFIRMATORY_CLOSEOUT.json`
- `research/d2/D2_C2_CONFIRMATORY_CLOSEOUT.md`
- `research/d2/evidence/d2-c2-confirmatory-result.json`
- `research/d2/evidence/evaluation-manifest.json`
- `research/d2/evidence/aggregation-manifest.json`
- `research/d2/evidence/D2_C2_INFERENTIAL_LEDGER.json`

GitHub governance/provenance evidence includes:

- issues #165, #167, #180 and their comments;
- issue #183 **body only** as the frozen review rubric; comments are deliberately excluded from the reviewer packet;
- pull-request metadata for #168, #177, and #181;
- C1 workflow `31895957256` metadata and jobs;
- C2 workflow `33312336871` metadata, jobs, and artifact metadata;
- current `main` branch metadata.

Every evidence item is canonicalized and hash-committed in the generated evidence manifest. The reviewer prompt explicitly treats embedded evidence text as untrusted data rather than instructions.

## Allowed decisions

Exactly one:

- `ACCEPT discovery_supported`
- `REJECT promotion; retain proposed and document reason`
- `DEFER pending specified evidence/integration condition`

## Mandatory checklist

The external reviewer must adjudicate every criterion exactly once:

1. `prospective_proposal_transition_before_confirmatory_outcomes`
2. `c1_failure_not_reused_as_scientific_evidence`
3. `c2_fresh_identity_seed_cohort`
4. `preregistration_before_c2_provider_outcomes`
5. `scientific_contract_not_posthoc_retuned`
6. `p0_p1_p2_serial_gatekeeping_pass`
7. `minimum_n_and_integrity_pass`
8. `artifact_private_state_boundary_intact`
9. `claim_ceiling_single_model_synthetic_individual`
10. `single_confirmatory_study_not_internal_replication`
11. `preservation_record_mainline_before_acceptance`
12. `historical_substrate_off`
13. `acceptor_distinct_from_proposer`

Each criterion status is one of `PASS`, `FAIL`, or `INSUFFICIENT`. Missing material evidence must be treated as `INSUFFICIENT`, not guessed.

## Maximum accepted claim

If accepted, the claim may be no broader than:

> In the registered single-model synthetic individual-agent Field substrate using Z.AI `glm-5-turbo`, capability developed through stochastic model-mediated local experience was reproducible in fresh destination agents through the registered public Capability Artifact mechanism beyond description-only and fresh controls, while satisfying the preregistered 90% source-fidelity criterion.

No weight-learning, cross-model/provider, naturalistic, team/swarm/institutional, composition, market, environment-spawning, or production-readiness claim is authorized.

## Outputs and authority boundary

A successful run writes:

- `output/d2-acceptance/evidence-manifest.json`
- `output/d2-acceptance/review-request.json`
- `output/d2-acceptance/review-response.json`
- `output/d2-acceptance/review-audit.json`

The review records a governance decision only. It does **not** mutate `research/mechanisms/registry.json`. If the external reviewer accepts `discovery_supported`, a later, separate append-only acceptance record and registry PR must encode the accepted transition.

Production/default Historical Substrate remains OFF.
