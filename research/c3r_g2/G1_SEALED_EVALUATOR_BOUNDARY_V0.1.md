# C3R G1 — sealed evaluator subprocess boundary v0.1

**Status:** offline, local-process construction only. Not independently attested,
not production hardened, and not authorization for paid experiments.

The multischema pilot previously kept its evaluator in the agent runner's
Python process. The new runner passes actions over a strict JSON-lines
channel to a **separate Python process**. That worker keeps the target
assignment in private memory, derived from a 32-byte evaluator-owned key.

## Components and responsibilities

- src/resonance_world/c3r_g1_sealed_evaluator.py — private-key-derived
  context targets, prescribed membership, duplicate blocking, phased outcome
  disclosure, a self-authored target commitment and one-shot finalization.
- src/resonance_world/c3r_g1_evaluator_worker.py — separate process CLI
  using an evaluator-owned regular key file with Unix mode 0600; rejects
  symlinks (on Linux), malformed messages, wrong task IDs, and premature
  finalization without echoing secret content.
- src/resonance_world/c3r_g1_sealed_runner.py — drives three arms and
  source-history acquisition through a supplied evaluator session. No
  evaluator secret or answer-key object is available to the model ports.
  It requires fresh learned-arm qualification sessions and rejects
  qualification acknowledgements that contain early grade fields.
- tests/test_c3r_g1_sealed_evaluator.py — tests the actual subprocess
  boundary, key permissions, strict enrollment, complete denominators,
  refusal of early holdout disclosure and eventual full-record reconciliation.

## Bounded interaction

At startup the worker publishes only the public cohort digest, target
commitment and frozen counts of required development and qualification
attempts. The client must verify those counts against its own cohort.

Only the learned development arm receives a Boolean grade after an exact
accepted action. Invalid actions count as failed development attempts.

**No qualification grade, success counter or answer-key data is sent during
qualification.** Every qualification action is only acknowledged. A
qualification request is forbidden until *all* development attempts across
all learner units have been submitted; no development can resume thereafter.

A single finalize operation is permitted only when every scheduled
development and three-arm qualification attempt has been accounted for.
It returns a complete sanitized attempt ledger and a record digest. The
runner cross-checks final records with its submitted actions and source
feedback; the existing independent multischema ledger auditor can then
recalculate arm-level, family-level and learner-level results.

## Local engineering demonstration

Create a strong, unique 32-byte key as 64 hex digits in a file outside the
repository, owned by the evaluator operator and chmod 0600. Never commit
or paste a real evaluator secret.

Run the worker in its own process:

~~~bash
python -m resonance_world.c3r_g1_evaluator_worker \
  --key-file /secure/evaluator-owned-key.hex \
  --units 2 --development 3 --qualification 2
~~~

The worker accepts one JSON object per input line on stdin and emits
one bounded JSON object per output line. Sending fewer than all prescribed
tasks does not produce any finalized holdout grades.

Verify the full three-arm end-to-end process with synthetic constant-A
model ports (no provider calls):

~~~bash
pytest -q tests/test_c3r_g1_sealed_evaluator.py
~~~

The test suite uses a conspicuously synthetic key in a temporary folder.
It is an engineering regression only; it is not a scientific result.

## Epistemic and security limitations

A separate process under the **same OS identity** is not a hardened
isolation boundary. Another same-user process may have permission to
read the evaluator's key file or process memory. The local test worker
does not itself constitute an independently operated evaluator. Its
key-derived outcome commitment is **self-authored**, not independently
timestamped, signed or witnessed. The grader's client has no mechanism
for authenticating an independently owned server identity.

A real evaluator must be deployed under separately managed OS or container
permissions with no access from model-running code; it must own the
prospectively sealed tasks and private answer key, issue independently
signed time-bounded receipts, maintain a write-once audit store and
release holdout grades only after the registered experiment closes.

Also required before any G1 scientific claim: backend-reconciled
physical sends and billable limits, real model-session isolation and
parity, separately validated placebo and input token cost, calibration
yield on non-holdout tasks, preregistered independent learner-unit
power, attrition rules and replication. This subprocess prototype
does not promote G1/G2/G3/G4, modify frozen W/H/D results, or change
mechanism/pattern registers.
