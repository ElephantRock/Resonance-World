# C3R G1 — one-shot live attempt reconciliation

**Evidence classification: UPLOADED_ARTIFACT_OBSERVED / RUN_ATTESTATION_UNRESOLVED / NO_AUTOMATIC_RETRY.**

## Operator-uploaded artifact received 2026-10-22 — important update

**Report availability: RESOLVED. Independent provider/run attestation: NOT RESOLVED.**

The operator uploaded `c3r-g1-authorized-smoke-20261021.zip`. The embedded
`technical-qualification.json` passed independent cohort-digest consistency
checks and reports 8/8 HTTP 200, **8/8 empty final-answer strings**,
8/8 `invalid_format`, 0/8 accepted, 0/2 paired-analyzable,
and 16/16 completion tokens used per call. This is an engineering
format/yield failure, **not** evidence of unsuccessful agent learning.

For archived SHA256 hashes, complete counts, interpretation and the bounded
reasoning-budget construction correction, read
`ONE_SHOT_ARTIFACT_ANALYSIS_20261022.md`. Do not discard the historical
report or rewrite the old run's results. Independent GitHub Actions execution
metadata and provider billing are still unavailable.



## What the repository proves

- PR #310 previously passed Ruff and 517 pytest cases after preparing a capped Z.AI Coding Plan technical smoke, using model `glm-5.3`.
- On 2026-10-21 an isolated branch named `experiment/c3r-g1-smoke-20261021` was created from the reviewed C3R construction head.
- Launch commit `463c3a1c2f89b1a069b2c141ab34deb862f26d73` introduced `.github/workflows/c3r-g1-authorized-once-20261021.yml`, a one-shot `push` workflow with a fixed commit-message predicate, the repository secret `ZAI_API_KEY`, and a maximum of 8 pre-reserved physical API sends.
- Retirement commit `07d8c00e6a2109cfb9abc9202f3058f2a10d4c09` removed the temporary workflow file. PR #310 remains a draft; `main` was not changed.
- These are **repository-change facts**; they are not proof that the GitHub Actions job started or reached the provider.

## What remains unknown

The connected GitHub workflow lookup lists only pull-request-triggered runs, not this prior push-triggered run. Public web/API access was unavailable. The **operator-provided artifact now reports eight provider HTTP 200 responses but zero analyzable actions**. The artifact itself is not cryptographically authenticated to an Actions run or provider-side receipt, so actual remote execution, environment approval, provider billing and independent provenance remain **unverified**.

**Rule:** no automatic live retry. The previous report has been recovered, but the proposed revised GLM-5.3 reasoning-budget settings require separate prospective review and authorization; the past zero-analyzable run cannot count as G1 evidence.

## Actions and artifact recovery

1. Open [GitHub Actions scoped to the one-shot branch](https://github.com/ElephantRock/Resonance-World/actions?query=branch%3Aexperiment%2Fc3r-g1-smoke-20261021).
2. Look for workflow name **C3R G1 Single Authorized Smoke** and launch commit `463c3a1c`. If a run exists, record its URL, trigger, job conclusion and the **Single authorized bounded provider smoke** step conclusion. Check whether `c3r-g1-authorized-smoke-20261021` was uploaded.
3. If an artifact exists, download its `technical-qualification.json` and run the offline validator from a trusted copy of this branch. **Do not rerun the job** merely to obtain an artifact.
4. If no run exists, record that observed absence separately from inability to access it. An access limitation is not a zero-send measurement.

### Offline validator

```bash
# Never needs API credentials or network:
python scripts/audit_c3r_g1_smoke.py technical-qualification.json --model glm-5.3 --route coding
```

A structurally valid diagnostic returns exit code `0` and status
`structurally_consistent_unattested`. Invalid, incomplete, contradictory or
fabricated JSON returns exit code `2`, with only bounded issue classes.
Missing/oversized input exits nonzero without interpreting it as a model result.

The audit checks the locked cohort, model and route, eight prescribed task
attempts (4 development + 2 learned + 2 fresh qualification), the a maximum of eight
pre-send reservations (with fewer permitted only after a terminal circuit-open failure), transport HTTP outcomes, accepted-action accounting,
source evidence count, paired-analyzable bound, observation digests, and the
absence of raw prompt/secret fields. It reconstructs the interleaved physical
send order separately from the grouping used in the report.

**Even a structurally consistent JSON artifact is not independently
attested.** The validator cannot authenticate provider identity, remote
execution, model capabilities, data provenance, billing or an evaluator-owned
frozen design. Scientific acceptance remains `false`.

## Promotion/continuation gates

- Technical status **unknown** until an Actions run and bounded artifact/step
  logs are reviewed; do not interpret a branch push as a successful experiment.
- A report with 0 accepted model actions cannot support model-mediated G1,
  even if all eight physical reservations are present and structurally valid.
- Evidence of a single provider response is a **technical smoke success only**.
  It does not prove trained-vs-fresh capability improvement, and in no case
  does it prove organization-level G2 (the honest C/D fixture intentionally ties).
- Any additional live campaign requires its own prospective cohort lock,
  independent evaluator, backend-authenticated send attribution, sample
  planning, stop/yield rules, and a fresh authorization for its expanded scope.

No old W/H/D results, World outcome laws, provider retry contracts, mechanism
registry states, or institutional continuity claims are affected.
