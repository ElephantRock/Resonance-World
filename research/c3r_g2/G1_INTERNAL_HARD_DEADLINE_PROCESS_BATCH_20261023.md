# C3R G1 — Internal Hard-Deadline Process Supervisor (2026-10-23)

**Status:** implemented on research Draft PR #310 as an **offline fixture**. No external auditor, custodian, witness, paid model calls or scientific G1 acceptance. Prefer this bounded process supervisor to the previous thread supervisor when worker cancellation matters.

## Objective

The earlier ThreadPoolExecutor caps admission but cannot terminate a stalled thread. New module: src/resonance_world/c3r_g1_crossed_internal_process_batch.py. Each independently isolated synthetic G1 run uses a new POSIX child process with an independent process group and a controller-enforced deadline.

Within-run science-preserving sequence is unchanged: 16 development actions → local signed source checkpoint (O_EXCL + fsync) → 24 grade-hidden qualification actions → 40-row signed terminal audit. A passing CI run does not constitute a genuine model observation.

## Contract

- **Admission:** 1–64 unique run IDs, constrained by the existing Ed25519 receipt protocol. Workspace is an owned private absolute directory (0700). A per-run exclusive fsynced claim (0600) is created before subprocess admission.
- **Bounded processes:** 1–8 active POSIX children; the controller never queues an unbounded set of worker futures and admits work only when a slot opens.
- **Hard deadlines:** configurable 0.05–600 seconds, default 30. The controller measures elapsed time with its monotonic clock. At the deadline it sends SIGKILL to the child's process group, reaps the child and writes a local failure journal. A hung run does not block unrelated runs.
- **One-shot child start:** each child requires a valid prior run claim, then exclusively creates a mode-0600 started marker. A second invocation for the same run ID fails. A crash or timeout cannot silently replay scientific actions.
- **Reduced process environment:** PATH, LANG, PYTHONDONTWRITEBYTECODE and existing PYTHONPATH only; no inherited provider/API token variables. Stdin, stdout and stderr are discarded. Complete signed terminal evidence stays in private files; public summaries exclude raw receipts, private target maps, feedback and holdout grades.
- **Failure classification:** nonzero exit, spawn failure and exceeded deadline are failed_no_auto_retry; a claimed but unclosed and unjournaled run is unresolved_no_auto_retry. Neither triggers automatic resends or is accepted as a scientific result. A closed terminal is accepted only after full receipt-chain and local source-lock revalidation.
- **Bounded continuation:** --max-new-runs controls how many previously unclaimed IDs may be admitted. Subsequent invocations never rerun an existing claim. --inspect reads existing states without new child processes.

These are same-host local engineering controls. They do not establish immunity from a privileged operator, immutable storage or external timing. POSIX process-group signals are not portable to Windows.

## Example CLI

    mkdir -m 700 -p /private/c3r-g1-process-batch
    python -m resonance_world.c3r_g1_crossed_internal_process_batch \
      --workspace /private/c3r-g1-process-batch \
      --run-id g1-internal-run-0001 \
      --run-id g1-internal-run-0002 \
      --run-id g1-internal-run-0003 \
      --processes 2 \
      --deadline-seconds 30 \
      --max-new-runs 2

Read-only inspection:

    python -m resonance_world.c3r_g1_crossed_internal_process_batch \
      --workspace /private/c3r-g1-process-batch \
      --run-id g1-internal-run-0001 \
      --run-id g1-internal-run-0002 \
      --run-id g1-internal-run-0003 \
      --inspect

With a later max-new-runs=1, only the previously unclaimed third run may be started. Already claimed runs are inspected, never replayed.

## Tests and limitations

Tests: tests/test_c3r_g1_crossed_internal_process_batch.py. They exercise actual isolated children, source-lock and terminal-chain reinspection, the strict concurrency cap, hard kill of a hung worker while other work completes, error isolation, duplicate child admission, claim replay, no-auto-resume, bounded admission, invalid parameters, and CLI inspection.

The current fixture has **zero provider sends**. It is not a production provider adapter: no authentic model outputs, token/compute parity, billing evidence, secure provider idempotency or scientific causal G1 result is asserted. Development authorization does not imply an uncapped spend instruction. The research PR stays Draft; no Pattern Register promotion follows from these tests alone.
