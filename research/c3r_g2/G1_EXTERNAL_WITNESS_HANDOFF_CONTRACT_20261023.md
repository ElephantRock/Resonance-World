# C3R G1 — Retired External Handoff Reference (2026-10-23)

> **SUPERSEDED — NOT A REQUIREMENT.** The project has chosen INTERNAL-ONLY verification and no independent/external auditor or archive. This file documents a former experimental interface for historical reproducibility, **not** a roadmap, prerequisite, approval gate or next step. The operative decision is [G1_INTERNAL_FIRST_FAST_PATH_DECISION_20261023.md](G1_INTERNAL_FIRST_FAST_PATH_DECISION_20261023.md). Do not deploy or extend the external path unless the project direction is explicitly changed.



**Status:** offline verification interface, experimental only; **not an independent archive service, independent witness attestation, trusted time, G1 causal proof or permission for 40 model sends**. Branch: research/c3r-g2-causal-foundation, PR #310 (Draft).

## Purpose and trust division

The fourth crossed pilot prescribes **16 development/source** and **24 qualification** logical attempts under its frozen plan. Existing infrastructure signs evaluator receipts (Ed25519), seals the first 16 receipts with a local custodian signature, and issues witness enrollment (sequence 1) plus a chained witness checkpoint (sequence 2) before qualification. A disposable **four-Linux-UID** CI test proves local role separation, not external autonomy.

The additional module **src/resonance_world/c3r_g1_crossed_external_handoff.py** provides a **read-only** source/terminal evidence verifier. It accepts a package from disk and public keys supplied separately by the investigator. It neither holds any signing key nor makes model, archive, timestamping, or network calls. A fifth cryptographic role, the proposed **archive/publisher signing authority**, is represented by a public verification key; **no external archive was connected**.

## Retired proposal requirements (not applicable to internal operation)

The former external-archive proposal would have required an independently operated archive authority to establish and publish an enrollment for its signing key out of band. Investigator custody of the expected run ID and four distinct public verification keys (evaluator, custodian, witness, archive) must be verifiable separately from the received evidence. A privileged experiment operator cannot be allowed to replace that source of truth.

The retired proposal also envisioned that an archive would retain the source bundle and resulting **archive receipt digest before the first qualification action**, under externally governed immutable retention, with independently checkable trusted time and availability. A claimed timestamp in locally signed JSON does **not** satisfy this. That retired proposal would have needed a separate arbiter to attest receipt/custody and reconcile evidence; source and archive signer keys alone cannot prove timing or remote storage.

## Source handoff — strict canonical form

Top-level JSON fields:
- schema = c3r-g1-crossed-handoff-v0.1
- enrollment (witness sequence 1 receipt)
- source_receipts (exactly 16 prescribed signed development attempts)
- custodian_deposit (signed custody receipt)
- witness_checkpoint (witness sequence 2 receipt)
- archive_receipt (archive authority's Ed25519 receipt sequence 1, run-matched)

The archive receipt signed payload is c3r-g1-crossed-archive-receipt-v0.1 with **exact fields**: schema, manifest_sha256, source_chain_head_sha256, witness_checkpoint_sha256, source_attempts=16, claimed_received_at_utc, independent_archive_custody_attested=false, trusted_timestamp_attested=false, immutable_remote_retention_attested=false, scientific_acceptance=false. The manifest SHA256 binds exact serialized source receipts, signed enrollment, signed custodian deposit, signed witness checkpoint, source-chain SHA256, frozen plan and run ID. The outer receipt uses the existing c3r-g1-ed25519-receipt-v0.1 envelope, signed under the **separately pinned fourth public key**.

The verifier checks signatures and full chain lineage, roles and exact frozen slot membership, source denominator, source-to-deposit-to-witness digests, and **claimed** chronology. Claimed chronology is not externally witnessed time. The result includes **archive_receipt_sha256** for separate custody. All scientific/attestation flags remain false. No private answer mapping is imported into this verifier.

## Terminal handoff — immutable source continuity

A terminal package adds exactly one field, terminal_receipts (40 logical signed attempts). Terminal verification **requires expected_prior_archive_receipt_sha256 supplied separately**, not derived from the terminal JSON. It fails if the archive receipt digest differs, the first 16 terminal receipts differ bytewise/structurally from the archived source package, or the remaining signed 24 records are missing, reordered, alien, or tampered. Attempt-level failures and not-sent slots remain in the denominator. The report remains **signed structural arithmetic**, not independently verified correctness, provider sends, or causal inference.

The terminal bundle contains holdout grade claims. **It must never be provided to the agent or qualification arms until the qualification stage is closed.** The source package may include graded development feedback and must be shared only with explicitly authorized learning paths.

## Historical, optional read-only offline CLI (not part of internal path)

Source example (placeholders, not live service endpoints):

    python -m resonance_world.c3r_g1_crossed_external_handoff \
      --bundle /archive/source-bundle.json --mode source \
      --run-id PRE_PINNED_RUN_ID \
      --evaluator-public-key-hex PINNED_EVAL_HEX \
      --custodian-public-key-hex PINNED_CUST_HEX \
      --witness-public-key-hex PINNED_WITNESS_HEX \
      --archive-public-key-hex PINNED_ARCHIVE_HEX

For terminal use --mode terminal with the 40-attempt bundle and **--previous-archive-receipt-sha256** from the separately retained source-stage report. A failing verifier returns a nonzero exit and a rejected verdict with scientific_acceptance=false. Do not derive pins or archival timestamps from the untrusted supplied bundle.

## Tests and evidence (2026-10-23)

**tests/test_c3r_g1_crossed_external_handoff.py** contains 11 local toy-signature tests: valid source and terminal handoff; missing/wrong prequalification archive fingerprint; changed terminal source prefix; tampered source; wrong signer; semantically invalid yet correctly signed archive claims; impossible timestamp order; cross-run/key replay; missing records and extra forbidden/private-target fields; public-key-only CLI. Toy signing keys generated in tests do not demonstrate outside authority or remote persistence.

Initial GitHub CI run **39897989475** passed **833 tests, 4 skipped**, Ruff, and the four-UID construction gate; Architecture Audit run **39897989415** also passed. Verify CI again at the latest doc-update head.

**Current internal scientific gates remain CLOSED:** authentic provider responses/session IDs and billing, tokenizer/compute parity, private-grade correctness checks, prospective design power, and scientific acceptance. External key ownership, third-party timestamping, independent external audits and remote archive retention are NOT required by the current internal architecture. No paid provider calls, pattern-register promotion or main-branch merge are implied.
