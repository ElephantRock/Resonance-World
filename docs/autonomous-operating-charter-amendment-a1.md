# Resonance World — Autonomous Operating Charter Amendment A1

Status: **active only after human-approved merge to `main`**. Tracks issue #225 and amends `docs/autonomous-operating-charter-v0.1.md`.

This amendment implements the human operator's explicit instruction that their standing general authorization covers the Autonomous Operating Charter. Its purpose is narrow: remove repeated per-candidate human confirmation for bounded provider/model execution while preserving prospective freezing, exact-head review, scientific authority separation, resource limits, and evidence integrity.

Where this amendment conflicts with Sections 6, 7, 11, or 13 of Charter v0.1 on per-candidate provider/model authorization, this amendment controls. All other Charter v0.1 provisions remain in force.

## 1. Standing execution authority

After activation, the AI operator may autonomously initiate an external provider/model execution for a frozen scientific or engineering campaign **without obtaining a new human authorization for that candidate** only when every condition below is satisfied:

1. **Prospective freeze** — the applicable issue/plan/request materialization is frozen before any outcome-bearing provider/model execution and identifies an exact candidate SHA.
2. **Bounded execution contract** — the frozen contract specifies the provider/model route, experiment or engineering purpose, stopping rule, and a finite hard ceiling on provider/model calls or physical provider sends.
3. **Exact-head readiness** — the frozen candidate is the current intended head, all applicable credential-free exact-head CI/preexecution checks are successful or intentionally skipped by contract, all blocking review threads are resolved, and a fresh exact-head review finds no blocker.
4. **No hidden authority mutation** — no post-freeze change has expanded scientific claims, changed a frozen treatment/evaluator/cohort/stopping rule after outcome-bearing data, or otherwise bypassed mechanism governance.
5. **Existing resource path only** — execution uses only already-configured credentials, subscriptions, provider accounts, and workflow permissions. It must not purchase resources, change billing, create material external spend, rotate/create/expose credentials, or grant new external permissions.
6. **Candidate-bound activation** — execution is activated by a one-use marker or equivalent durable record that names the exact candidate SHA. When the workflow contract uses a sole-child marker, the marker must be the only diff from the frozen candidate.
7. **Fail-closed workflow** — the workflow verifies the exact frozen candidate, registered ceilings, run attempt 1, and any other prospective integrity checks before provider execution. A failed integrity check must prevent provider/model traffic.
8. **No same-stream rerun** — a workflow/request stream registered as one-shot or no-rerun may not be rerun after any outcome-bearing execution, regardless of success, failure, or apparatus classification.
9. **Preservation** — authoritative outcomes, including negative, mixed, null, transport, quota, apparatus, or integrity failures, are preserved under the registered claim ceiling without outcome-based rescue or replacement.

A head change invalidates prior exact-head readiness. The operator must repair/re-freeze/re-run credential-free checks and fresh review as necessary, but **does not need a new human authorization** solely because the candidate SHA changed.

## 2. Scientific campaigns

This standing execution authority may satisfy the human-authorization component for initiating a prospectively frozen scientific campaign, provided Section 1 is satisfied.

It does **not** weaken `docs/mechanism-governance-v0.1.md`. In particular:

- prospective preregistration and apparatus/treatment integrity requirements remain unchanged;
- post-outcome retuning remains prohibited unless prospectively allowed;
- the AI operator may generate evidence but may not act as final Acceptance-plane authority where proposer/evidence-generator and acceptor separation is required;
- Mechanism Registry promotion still requires the applicable independent acceptance record;
- claim ceilings remain binding;
- Historical Substrate remains OFF unless separately authorized.

## 3. Resource boundary

This amendment does not establish a new monetary budget. Default discretionary external spend remains **USD 0**.

Provider/model execution under an already-paid or otherwise already-available subscription/resource path may proceed under Section 1 only when it creates no new purchase, billing change, material spend commitment, credential change, or permission grant.

If execution would require a purchase, recharge, billing modification, new paid service, or other material external commitment, the operator must stop for explicit human authorization for that resource action.

## 4. Authorities not delegated

This amendment does not delegate autonomous authority to:

- make final Acceptance-plane decisions where independent acceptance is required;
- promote or rewrite Mechanism Registry scientific status without required acceptance;
- activate production/default Historical Substrate;
- publish externally or make an official public scientific claim;
- deploy publicly or materially alter production infrastructure;
- purchase resources or change billing;
- create, rotate, expose, or materially change credentials or external permissions;
- delete or rewrite authoritative evidence, artifacts, historical experiment records, or accepted decisions;
- override a frozen no-rerun, treatment-integrity, dependency-order, or preservation requirement.

## 5. Audit record

Each autonomous provider/model execution under this amendment must leave a durable record sufficient to recover at least:

- exact candidate SHA;
- governing issue/PR/plan;
- provider/model route requested by the frozen contract;
- registered provider-call ceiling;
- workflow/run identity and attempt number;
- authorization basis: `Autonomous Operating Charter Amendment A1 — standing execution authority`;
- outcome/artifact identities and applicable claim ceiling.

## 6. Activation and revocation

The human approval required by Charter v0.1 Section 13 was explicitly supplied before this amendment was authored: the human operator stated that their general authorization is intended to cover the charter and that they need not author the amendment text personally.

This amendment becomes active only after review-clean human-approved merge to `main`. The human operator may revoke or narrow the standing authority at any time; once such revocation is communicated, no new provider/model execution may begin under this amendment until durable governance is reconciled.

This amendment is prospective only. It does not retroactively alter historical authorization records, campaign outcomes, or scientific interpretations.
