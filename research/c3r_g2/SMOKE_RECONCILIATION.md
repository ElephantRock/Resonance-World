# C3R G1 — one-shot live attempt reconciliation

**Evidence classification: UNRESOLVED / DO NOT RETRY.**

## What the repository proves

- PR #310 previously passed Ruff and 517 pytest cases after preparing a capped Z.AI Coding Plan technical smoke, using model `glm-5.3`.
- On 2026-10-21 an isolated branch named `experiment/c3r-g1-smoke-20261021` was created from the reviewed C3R construction head.
- Launch commit `463c3a1c2f89b1a069b2c141ab34deb862f26d73` introduced `.github/workflows/c3r-g1-authorized-once-20261021.yml`, a one-shot `push` workflow with a fixed commit-message predicate, the repository secret `ZAI_API_KEY`, and a maximum of 8 pre-reserved physical API sends.
- Retirement commit `07d8c00e6a2109cfb9abc9202f3058f2a10d4c09` removed the temporary workflow file. PR #310 remains a draft; `main` was not changed.
- These are **repository-change facts**; they are not proof that the GitHub Actions job started or reached the provider.

## What remains unknown

The connected GitHub workflow lookup lists only pull-request-triggered runs, not this prior push-triggered run. The direct public web/API fetch and unauthenticated shell fetch were unavailable. Consequently the following cannot be asserted: whether GitHub scheduled the one-shot job, whether environment approval/secret resolution succeeded, how many API POSTs were attempted, what Z.AI returned, whether qualification was analyzable, or whether a diagnostic artifact was uploaded.

**Rule:** no new live provider requests until the one-shot branch's Actions event has been inspected and the previous physical-send count is reconciled.

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
