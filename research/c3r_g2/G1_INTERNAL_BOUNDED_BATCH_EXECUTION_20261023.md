# C3R G1 — Bounded Internal Batch Execution (2026-10-23)

**Status:** implemented **offline fixture** under PR #310 (Draft). **Internal-First**: no independent/external auditor, witness, custodian approval or remote archive. No provider calls, paid budget authorization, scientific acceptance or main merge.

## Why this exists

The internal G1 source barrier is already a single automated local checkpoint after exactly **16 signed development** attempts. Each run then executes **24 closed qualification** attempts and audits all **40 prescribed logical attempts**, retaining unsent attempts within the denominator. The next engineering bottleneck is serializing *independent runs* through one controller, or allowing an unlimited pending queue and unsafe auto-retries.

Module: **src/resonance_world/c3r_g1_crossed_internal_batch.py**. This batch supervisor composes the preexisting CrossedLocalEvaluator and internal source lock. It does not replace either verifier or create a new grader.

## Bounded execution and isolation

- Accept **1–64 unique, safe run IDs**, matching the existing Ed25519 receipt protocol (8–64 ASCII characters, initially alphanumeric, then alphanumeric, underscore, hyphen or dot).
- Use a **pre-created absolute private workspace (mode 0700, current UID owner)**. Each run reserves an independent claim file with O_EXCL and fsync **before** its worker is submitted. The run ID is hashed for file/directory naming; there is no global run-wide lock.
- Bound the ThreadPoolExecutor to **1–8 workers** and maintain a separate **in-flight budget from worker count to twice the worker count**; never feed an unbounded queue.
- Each worker generates **local fixture-only Ed25519 and private-target seeds** and uses its own owner-private checkpoint directory. No generated private target map or holdout grade is returned in batch progress.
- Each worker executes synthetic A/B responses in the exact frozen 16+24 schedule, including **one deliberately not_sent terminal slot**, writes a private closed terminal snapshot only after all 40 logical attempts and source-lock verification succeed, then exits.
- A read-only inspector checks the original claim, full Ed25519 terminal chain, stored audit, and private source checkpoint. Reports statuses: completed_and_verified_internally; not_claimed; unresolved_no_auto_retry; failed_no_auto_retry; integrity_failure.
- Failure in one worker is reported for that run and does not automatically retry it or stop other unrelated runs. Error messages, raw provider output, hidden target mappings and grades are **never included in the public JSON summary**.

All snapshots remain on a *single host* and can be changed by a privileged host operator; they do not establish WORM immutability or independent audit authority.

## Controlled admission, pause and safe continuation

The --max-new-runs option limits how many **new** run IDs a single invocation may claim. A follow-up invocation can operate on **not-claimed** run IDs only, while existing complete runs remain untouched. Set --max-new-runs 0 to claim nothing; this is a useful admission dry run.

An interrupted claim with no closed terminal snapshot is **unresolved**, not a successful or missing-as-success attempt. It may have executed an unknown number of actions. It cannot be automatically resumed or re-sent using the same run ID. Inspection is safe; any further experiment requires internal operator review and a **new run ID** after recording the original as unresolved. Already claimed failed or completed runs are never automatically redriven.

This is **safe admission-level continuation**, not mid-attempt replay or state reconstruction.

## CLI — zero-provider fixture

Use a workspace owned by the runner:

    mkdir -m 700 -p /private/c3r-batches

Submit an intentionally bounded batch (only two new runs):

    python -m resonance_world.c3r_g1_crossed_internal_batch \
      --workspace /private/c3r-batches \
      --run-id g1-internal-trial-001 \
      --run-id g1-internal-trial-002 \
      --run-id g1-internal-trial-003 \
      --workers 2 --in-flight 3 --max-new-runs 2

Inspect *without executing*:

    python -m resonance_world.c3r_g1_crossed_internal_batch \
      --workspace /private/c3r-batches \
      --run-id g1-internal-trial-001 \
      --run-id g1-internal-trial-002 \
      --run-id g1-internal-trial-003 --inspect

A second non-inspection invocation with the same IDs and an admission budget of one claims only the remaining previously unstarted run. The CLI exits nonzero when the requested batch contains unstarted, unresolved, failed or corrupted runs. The inspector never performs a provider send or invokes the evaluator.

**Confidentiality:** private terminal files include per-attempt grade claims and belong strictly to post-qualification auditing. Do not expose them to agents or qualification contexts before closure; console summaries contain no such details.

## Verification and remaining limits

Tests in **tests/test_c3r_g1_crossed_internal_batch.py** cover independent completion, bounded pending work, atomic duplicate-claim exclusion, admission pause and continuation, fail-safe interrupted claims, failure isolation, transcript/source-lock tampering, strict IDs/workspace permissions and subprocess CLI inspection. Regular pytest/CI checks must be validated against the latest exact branch head.

**No claim of production scheduling or performance gains:** The current ThreadPoolExecutor is suitable for the synthetic/offline fixture, but cannot forcibly terminate a stalled thread or provide a hard per-run deadline. A production provider adapter would require process-bound deadlines, cancellation semantics, idempotent dispatch records, budgets and externally sourced provider receipts *inside project control*. No such adapter is activated here.

Scientific G1 prerequisites remain internal: real model observations when separately authorized, correct private grading, matched sessions/tokens/compute, fixed experimental allocation, complete denominators and causal analysis. **scientific_acceptance=false** and Pattern Register promotion remains blocked by scientific evaluation, not by an external auditor.


## POSIX process supervisor supersession (2026-10-23)

The ThreadPoolExecutor scheduler documented above remains a tested,
compatible offline fixture, **not the preferred hard-timeout runner**.
The project now also implements
src/resonance_world/c3r_g1_crossed_internal_process_batch.py, described
in G1_INTERNAL_HARD_DEADLINE_PROCESS_BATCH_20261023.md. It admits only
a bounded number of POSIX child processes, enforces per-process monotonic
deadlines with process-group SIGKILL/reaping, isolates credentials from
the inherited environment, writes an exclusive child-start marker and
never retries a claimed run. Source/holdout separation and scientific
nonacceptance are unchanged. No outside approval is added.
