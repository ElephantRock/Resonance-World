# C3R G1 — Witnessed evidence journal v0.4 (offline prototype)

**Status: construction-only, no external witness custody, no provider sends, no scientific acceptance.**

The original G1 protocol had a signed pretrial enrollment and a separate signed
evaluator receipt stream. It lacked a **persisted, sequential link** between
the admission and *each* evaluator message. This prototype fills that
engineering gap without claiming that a local file is physically immutable.

## What was implemented

`src/resonance_world/c3r_g1_witness_journal.py` contains:

- **WitnessJournal**: rejects an invalid enrollment before creating a journal.
  Requires a 32-byte witness signing seed and a valid witness-signed
  enrollment for the exact experiment run, public cohort, evaluator
  signing key, hidden-target commitment and admission time.
- Exclusive file creation using a private, owner-controlled parent directory
  and 0600 file permissions. Each event is serialized as canonical JSON,
  signed with Ed25519, appended sequentially and flushed with `fsync`.
  Overwriting an existing journal path is refused. Crash/interruption
  leaves a nonfinal fragment that is rejected during full audit.
- **Stage enforcement**: the enrollment is the first event, then signed
  evaluator readiness, all development receipts, grade-free qualification
  acknowledgments, and finally the complete evaluator outcome ledger.
  The final evaluator transcript must pass its own independent audit
  before the last event is appended. Failed/missing actions are part of
  the prescribed denominator, not removed.
- **JournaledEvaluatorSession** wraps the existing signature-validating
  evaluator session and writes *each receipt before releasing its reply*
  to the synthetic client. It is an **in-process demonstration**, not
  an independently operated witness service. Do not place a real
  witness signing secret in an agent process.
- **audit_witness_journal** checks every witness signature and prior-event
  digest, original admission signature, pinned evaluator key and run,
  full signed evaluator receipt sequence, all three treatment arms and
  complete prescribed task ledger. It requires only public keys.
- A read-only audit CLI emits `signed_structural_chain` on success,
  or `rejected` on failure; either way scientific admission is false.
  The caller must supply an externally established admission UTC time;
  this parameter alone is **not** a trustworthy timestamp.
- Regression tests include valid null fixtures, changed outcomes,
  removed/reordered/duplicated events, substituted keys/commitments,
  incomplete journals, exclusive creation and file permissions.

## Read-only audit example

The two public-key files must be independently pinned, not obtained
exclusively from the document being audited. The admission UTC input
should come from a separately retained pretrial record.

```bash
python -m resonance_world.c3r_g1_witness_journal \
  /audit/g1-witness-journal.jsonl \
  --witness-public /audit/witness-public-key.hex \
  --evaluator-public /audit/evaluator-public-key.hex \
  --run-id g1-prospective-run-id \
  --admission-utc 2026-10-22T12:00:00Z \
  --units 8 --development 6 --qualification 8
```

A passing verdict means only that the supplied journal is **internally
consistent with the pinned signing identities and complete public cohort**.
Its signatures demonstrate who held the keys, not that the record was
written when claimed, that the grader was unbiased, or that an
independent party controlled either key.

## Serious limitations

The append-only file is **not WORM/immutable storage**. The OS owner,
privileged administrator or anyone with the witness signing seed may
delete, replace or create a second signed timeline. An untrusted
operator could provide a different but internally valid complete
journal to different auditors. Exclusive creation, Linux file
permissions and `fsync` mitigate accidental damage but **do not
provide trusted timestamps, non-equivocation, independent origin or
durable external retention**.

Before scientific G1 work, deploy a witness-operated API under its
**own OS/service identity**, without exposing a witness private key to
the model process; require an off-platform timestamped pretrial
checkpoint and an external append-only/WORM retention system.
The witness must publish periodic signed checkpoints to independent
observers so that conflicting histories cannot be silently substituted.

Real-model prerequisites remain: independent and evaluator-owned
heldouts, independently controlled evaluator identity, matched model
settings and sham token budgets, physical-send/billing reconciliation,
pre-registered power and attrition, independent learner units and blind
replication. The local exercise makes **zero calls to Z.AI** and leaves
G1/G2/G3/G4, historical null results and the Pattern Register unchanged.
