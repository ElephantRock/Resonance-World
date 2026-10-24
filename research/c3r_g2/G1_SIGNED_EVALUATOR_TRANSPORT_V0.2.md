# G1 v0.2 — signed evaluator receipts and Linux UID-gated transport

**Status:** OFFLINE ENGINEERING CONSTRUCTION ONLY. No provider sends, signed
scientific attestation, trusted timestamps, independent deployment or G1 result.

## Boundary and components

The new evaluator receipts module (src/resonance_world/c3r_g1_evaluator_receipts.py)
uses Ed25519 to sign the evaluator's startup, **each** graded development
response, each grade-free qualification acknowledgement, and the final complete
outcome ledger. Each receipt binds a run identifier, ordinal, previous-receipt
SHA256, the public key fingerprint and the signed payload.

The model-side VerifiedEvaluatorSession checks each receipt against an
**out-of-band pinned public key** and separately registered run ID. Any
reordered, replayed, modified, missing or wrong-key message is rejected
before the sealed runner can use it for source learning or qualification.

The offline receipt auditor (src/resonance_world/c3r_g1_evaluator_transcript.py)
validates signatures, the full prescribed denominator, three-arm qualification
coverage, development feedback consistency, final record membership and
the final ledger digest against the public prospective cohort. It never
possesses the private evaluator seed or target answer key. It cannot prove
that a grader was correct or scientifically unbiased.

The Linux Unix-socket transport (src/resonance_world/c3r_g1_evaluator_unix.py)
provides a one-client, one-run evaluator listener with Linux SO_PEERCRED
UID pinning, no credential sharing to the client, and a group/world-write
prohibition on the socket directory. The service launches the existing
isolated evaluator worker as a child under the server's OS identity. The
agent connects using UnixEvaluatorClient and verifies every response
through VerifiedEvaluatorSession.

The optional Python extra named evaluator-crypto supplies the Ed25519
library. The dev extra includes it for automated tests. No encryption
primitives are implemented by hand in this repository.

## Separate-UID deployment contract (not performed in CI)

An independent operator must provision an unprivileged evaluator service
account **different** from the model-runner account.

| Resource | Required ownership/access |
| --- | --- |
| 32-byte private target seed (64 hex digits) | Evaluator UID only; regular file mode 0600 |
| Distinct Ed25519 private signing seed | Evaluator UID only; regular file mode 0600 |
| Socket parent directory | Evaluator UID; mode 0750, no group/world write |
| Unix socket | Evaluator UID; mode 0660, shared group connect only |
| Allowed client identity | Exact pre-registered agent UID from kernel SO_PEERCRED |
| Public key and expected run ID | Separately pinned by agent and auditor BEFORE the experiment |
| Long-term signed transcript | Retained by evaluator-operated, preferably write-once storage |

Operator-side example, launched **as the evaluator service UID** after
separately provisioning the files, socket directory and distinct account:

~~~bash
python -m resonance_world.c3r_g1_evaluator_unix \
  --socket-path /run/resonance-g1-evaluator/evaluator.sock \
  --allowed-peer-uid <PRE_REGISTERED_AGENT_UID> \
  --key-file /secure/evaluator/target-seed.hex \
  --signing-key-file /secure/evaluator/signing-seed.hex \
  --run-id g1-evaluator-example-001 \
  --units 2 --development 3 --qualification 2
~~~

The model-side process receives only the socket path, public cohort,
pre-pinned signing **public** key, and registered run ID. It must never
mount or inherit either private key or evaluator service credentials.
The evaluator does not need provider network access.

After full finalization, the already-verified
VerifiedEvaluatorSession.signed_receipts sequence can be written to a
JSONL file (one envelope per line). The independent offline verifier is:

~~~bash
python -m resonance_world.c3r_g1_evaluator_transcript \
  /audit/g1-run-signed-receipts.jsonl \
  --public-key-file /audit/pinned-signing-public-key.hex \
  --run-id g1-evaluator-example-001 \
  --units 2 --development 3 --qualification 2
~~~

Exit 0 means **signed_structurally_consistent** only. Exit 2 means rejected
or incomplete evidence. The output explicitly retains
scientific_acceptance=false, evaluator_independence_attested=false,
private_grade_correctness_verified=false and provider_sends_verified=false.

## Verified engineering tests

~~~bash
pytest -q tests/test_c3r_g1_evaluator_receipts.py \
  tests/test_c3r_g1_evaluator_unix.py
~~~

The automated socket test runs under **the same OS UID** as the model test
harness. This is a functional protocol test and does not demonstrate
production UID segregation or independently controlled signer identity.

## Scientific limitations and promotion gates

Receipt signatures show that the holder of a pinned private key emitted
a consistent transcript. They do not attest independently controlled key
custody, trusted timestamps, write-once retention, hidden-grade accuracy,
unbiased allocation, provider billing, paid send quotas or no key leakage.

Before a real prospective G1 study, independently witness the public key,
run ID and hidden-target commitment **before any source trial**; deploy
and test separate OS/host identities; register an append-only auditor-owned
record store; validate model-budget equality and placebo plausibility;
authenticate all provider send IDs; preregister powered independent learner
replicates and the ITT analyses. Do not reuse past diagnostic heldouts
as fresh evidence.

No new Z.AI call, main merge, positive scientific claim, architecture pattern
promotion or alteration of historical W/H/D records is made by this work.
