# C3R G1 — Cross-UID Deployment and Witnessed Enrollment v0.3

**Status: Engineering fixture verified; independent scientific authority NOT YET established.**
No provider calls, model-learning result, G2 result, main merge or scientific
registry promotion is authorized by this work.

## Verified cross-UID offline deployment test

A PR-310-only GitHub Actions job, c3r-g1-cross-uid, creates disposable,
unprivileged **different Linux user IDs** for evaluator and model-side
client. It stores synthetic target and signing keys in an evaluator-owned
0700 directory, with 0600 key files, and uses a shared-group 0750
Unix socket directory. The agent cannot read either evaluator secret.

Code paths:
- src/resonance_world/c3r_g1_cross_uid_fixture.py
- scripts/run_c3r_g1_cross_uid_fixture.sh
- .github/workflows/ci.yml (job c3r-g1-cross-uid)

The test stages **only runtime source**, not GitHub workspace metadata or
credentials, in a readable test directory for both principals. It pins
the evaluator socket's actual owner UID and validates Linux SO_PEERCRED
peer identity. The full three-arm synthetic fixture then runs through
the signed, grade-sealed evaluator with a publicly pinned signing key.
All keys, users and sockets are removed after the disposable CI run.

**Limitation:** the test harness holds root/sudo on a GitHub-hosted runner
and provisions both accounts. This proves Linux OS separation works
mechanically; it does NOT prove evaluator *institutional* independence,
trusted key custody, write-once storage or confidential provider billing.

## Witnessed prospective enrollment

Implementation: src/resonance_world/c3r_g1_witnessed_lock.py
Tests: tests/test_c3r_g1_witnessed_lock.py

A distinct Ed25519 witness signs a prospective enrollment record with:
- a unique experiment run ID,
- the public task-cohort SHA256 digest,
- the evaluator's *public* Ed25519 signing key,
- the evaluator's commitment to its hidden answer rules,
- a UTC issuance and expiry, limited to a 30-day interval,
- the witness's signature over all listed fields.

The agent must already know the **witness public key out of band**. A
WitnessVerifier rejects modified, expired, wrong-key, wrong-run, wrong-cohort,
or wrong-target data. The admitted WitnessedLock stores immutable scalar
fields. Its WitnessedEvaluatorSession wrapper admits a signed evaluator
readiness message only when the public cohort and private target
commitment exactly match the witness-registered values. A rejected
readiness request blocks the experiment **before the first source call**.

The signature verifies what the pinned witness key signed. It does not
independently prove the key's legitimate owner, genuine timestamp, or
whether the hidden target was fair or correct. Dates checked against a
local UTC clock provide only an operational expiry gate, not trusted
pretrial chronology or non-equivocation.

## Acceptance gate for a real G1 experiment (still NOT met)

1. An independently operated witness must retain its signing seed away
   from the evaluator/model and sign/publish the record before any
   learning request, with a trusted external timestamp.
2. Public cohort, evaluator signing key, hidden-target commitment and
   run ID must be fixed and independently witnessed; no witness public
   key can be silently substituted by the evaluator.
3. The deployment owner must verify evaluator/model identity separation,
   key-directory permissions, socket access policy and no evaluator
   secret mounts in the model/container.
4. A witness-operated append-only receipt store must retain the signed
   enrollment and every completed evaluator-signed transcript.
5. The research owner must preregister the real-provider transport,
   physical-send and monetary caps, matched budgets and placebo validity,
   independent learner units, power/attrition plan, and blind analysis.

This test and enrollment module use synthetic fixture keys, not real
externally controlled credentials. No Z.AI calls, independent witness
attestation, G1/G2/G3/G4 scientific acceptance or pattern/register
changes result from the implementation.
