# C3R G1 — Detached custodian receipt contract v0.6

**Status:** offline engineering fixture. No actual external deposit, no independently operated custodian, no trusted timestamp, no WORM retention, no Z.AI send, and **no G1 scientific acceptance**.

## What changed after v0.5

The v0.5 handoff exported a signed evaluator/witness journal and a self-described manifest, but had no independent receipt. The v0.6 prototype adds a **separate Ed25519 signing role**, a **run-scoped archived copy** and a **detached receipt** binding that exact copy.

Source: `src/resonance_world/c3r_g1_custodian_receipt.py`.
Regressions: `tests/test_c3r_g1_custodian_receipt.py`.

`LocalCustodianFixture` is purposefully named: **it is not a networked or institutional custodian**. It accepts only a complete v0.5 bundle that passes the existing public-key, frozen-cohort and signature-chain audit. It requires a third, cryptographically distinct signing key (not the evaluator or witness key), a bounded custodian name, a valid run identifier and a claimed receipt UTC timestamp that does not precede the supplied admission context.

Under a private owner-controlled directory it exclusively creates a per-run entry, keyed by SHA256 of the run ID, and stores:

| Artifact | Meaning |
| --- | --- |
| `bundle/signed-evaluator-journal.jsonl` | Byte-identical already-verified witness/evaluator signed journal |
| `bundle/handoff-manifest.json` | Byte-identical public-key-verifiable handoff manifest |
| `detached-custodian-receipt.json` | Custodian-signed binding of archive bytes, run/cohort and key fingerprints |

The receipt fixes the **exact manifest hash**, **journal hash**, enrollment/final event hashes, task-cohort digest, run identifier, all three role public-key fingerprints, custodian name and archive reference. The receiving fixture refuses duplicate run IDs and writes/f-syncs each archived file before emitting a signed receipt.

The read-only `verify_custodian_receipt` checks the archive from scratch with the out-of-band evaluator and witness public keys, then verifies the detached receipt's signature with an **out-of-band pinned custodian public key**. It rejects modified archives, substituted signers or names, extra/missing files, bogus policy/status claims, reused or mismatched run IDs, and changed receipts. A separate verification-only CLI is provided:

~~~bash
python -m resonance_world.c3r_g1_custodian_receipt \
  /private-custodian-inbox/<sha256-run-id> \
  --witness-public /pins/witness.hex \
  --evaluator-public /pins/evaluator.hex \
  --custodian-public /pins/custodian.hex \
  --custodian-id externally-registered-operator \
  --run-id prospective-run-001 \
  --admission-utc 2026-10-22T12:00:00Z \
  --units 8 --development 6 --qualification 8
~~~

**Never pass private keys to the verifier.** The signing constructor is a local *test* entry point, not a live custodian upload service. The source GitHub runner can generate all three keys in its own test process: passing tests therefore cannot establish independence of the human/operator managing the private keys.

## Verdict, not scientific authority

The successful verdict is deliberately:
`signed_local_archive_consistent_unattested`.

The result must always contain:

- `independent_operator_attested=false`
- `external_deposit_attested=false`
- `trusted_timestamp_verified=false`
- `immutable_retention_verified=false`
- `private_grading_truth_verified=false`
- `provider_billing_verified=false`
- `scientific_acceptance=false`

A cryptographic signature can establish **which pinned key signed which bytes**, but not independently prove **who controlled the key, that the clock was trusted, when the record was first published, or that the archive is write-once**. A local filesystem administrator and local custodian private-key holder can rewrite both archive and receipt. A SHA256-based per-run directory prevents accidental name reuse in this fixture only; it cannot establish off-platform non-equivocation.

### Hard scientific promotion gate (still unmet)

A real third-party custodian must: register an independently pinned public key and operator identity **before the G1 run**; independently verify the prior witnessed cohort and rule commitment; accept finished evidence through a separately owned channel; return an authenticated, externally timestamped acceptance receipt; retain the archive in an actually configured and externally auditable append-only/WORM facility; prevent re-registration of a run ID; and publish checkpoints to independent observers.

The G1 real-model study remains gated on provider entitlement/billing reconciliation, matched generation budgets, model/session isolation, evaluator-owned holdouts, validated sham histories, learner-unit replication and power, and independent blinded analysis. No trial results, W/H/D historical records or Pattern Register entries are changed.
