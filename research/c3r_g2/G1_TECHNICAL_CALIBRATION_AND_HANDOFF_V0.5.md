# C3R G1 — Technical Calibration and Evidence Handoff v0.5

**State: offline engineering construction, NOT G1 evidence or authorization for provider expenditure.** Draft PR #310.

## Source-derived reason for this step

The historical GLM-5.3 output-budget requalification records 8 prescribed logical tasks, 6 self-reported HTTP sends, 5 parseable answers, and **0/2 analyzable learned/fresh pairs** despite a 512-token budget. The earlier 16-token trial returned no parseable answers. These observations are unchanged (see OUTPUT_BUDGET_REQUALIFICATION_20261022.md).

## A. Two-schema calibration without scientific holdouts

Modules: src/resonance_world/c3r_g1_multischema_calibration.py, tests/test_c3r_g1_multischema_calibration.py.

The new calibration-only public task plan contains 8 logical prompts: 1 development-format prompt per task family (arithmetic, text transformation), followed by 3 qualification-format prompts per family (learned, fresh, placebo). This is **prompt formatting/output quality only**: no arm receives a scientific grade or learned feedback, no hidden answer key is used, and no G1 inference is made.

Default credential-free execution:

    python -m resonance_world.c3r_g1_multischema_calibration

The preexisting Z.AI port now offers a bounded complete_prompt(text) method without manufacturing an arithmetic ModelChoiceRequest for text schemas. It reuses the same pinned model, endpoint, maximum eight physical reservations per process, 30s timeout, up-to-512-token limit, disabled-by-default dispatch, no retries, no redirects, and fatal-error circuit breaker. Invalid input is rejected before reservation. The test doubles make **zero external provider requests**.

Engineering-only acceptance rule: all eight model outputs must be exactly A/B, nontruncated and correctly model-tagged, with both three-arm qualification triplets complete. On any invalid response or exception, stop attempting sends, but retain all unsent logical tasks in the prescribed denominator. A passing synthetic fixture is NOT measured GLM-5.3 performance. The report always states scientific_acceptance=false, provider_sends_verified=false, and provider_billing_verified=false.

Future live calibration remains gated by independently checked Z.AI entitlement/endpoint policy, reviewer approval, one global provider-side physical-send/financial limit, signed experiment enrollment, matched settings, and real backend/billing reconciliation. The earlier 512-token output budget still exhausted some final answers; no additional paid run is authorized here.

## B. Public-key evidence handoff to a separate custodian

Modules: src/resonance_world/c3r_g1_evidence_handoff.py, tests/test_c3r_g1_evidence_handoff.py.

Only a **complete, publicly verifiable** witness journal can be exported. The handoff creates a new private directory containing exactly:

- signed-evaluator-journal.jsonl — byte-for-byte copy of the signed event chain;
- handoff-manifest.json — run/cohort identity, journal SHA256/size/count, first and final event digests, evaluator/witness public-key fingerprints, no private material.

The manifest reports state=local_export_not_externally_deposited, external_custodian_receipt=null. The standalone verifier checks the full signed journal and exact manifest using **externally pinned public keys**. Verification verdict: public_key_verified_not_external_custody, never scientific acceptance.

Example commands (a real journal is required; never supply private keys):

    python -m resonance_world.c3r_g1_evidence_handoff prepare /secure/journal.jsonl --destination /private/new-g1-run --witness-public /pins/witness.hex --evaluator-public /pins/evaluator.hex --run-id prospective-run-001 --admission-utc 2026-10-22T12:00:00Z --units 8 --development 6 --qualification 8

    python -m resonance_world.c3r_g1_evidence_handoff verify /private/new-g1-run --witness-public /pins/witness.hex --evaluator-public /pins/evaluator.hex --run-id prospective-run-001 --admission-utc 2026-10-22T12:00:00Z --units 8 --development 6 --qualification 8

The admission time argument is caller-provided verification context, **not a trusted timestamp**. No network uploader or external WORM/append-only store is installed. Real independent custody requires an outside operator to pin and publish the enrollment **before learning**, receive the handoff, independently timestamp and retain it, and issue a verifiable outside receipt. A local manifest does not constitute such a receipt.

## Scientific gate

Before a confirmatory G1 study: establish third-party evaluator/witness ownership and external retention; provider billing and send attestation; equal generation/token budgets; plausible sham control; independently frozen heldouts; powered learner-unit-level inference; and blind replication. Nothing here authorizes 480 live sends, changes D2/W/H/C3R historical results, promotes the Pattern Register, or establishes G1/G2/G3/G4.
