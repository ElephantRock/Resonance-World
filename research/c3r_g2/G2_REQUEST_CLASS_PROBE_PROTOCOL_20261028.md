# G2 request-class qualification probe — FROZEN mini-protocol (2026-10-28)

Status: **FROZEN before dispatch** under the owner's limited GO
(2026-10-28 evening). Exactly TWO live sends, independent permanent
cap; NOT the reserved Probe sends. This probe does NOT launch the
scientific campaign and does not prove statistical stability.

## Purpose

Qualify TECHNICALLY the two request classes the G2 campaign needs:

- **C-class** — per-task raw-evidence interpretation: the member reads
  a bounded excerpt of graded evidence records (context and variant
  tags visible) and answers one task.
- **D-class** — compiled-procedure execution: the member reads a short
  compiled procedure (no raw records) and executes it on one task.

## Frozen design

- Fixture: the deterministic S2-class organization from the offline
  qualification harness (20-record noisy-majority corpus, one holdout
  task, one member per class). Corpus, task, compiled procedure and
  prompts are derived deterministically by the runner — no choice
  after the fact.
- Prompts mirror the campaign's registered shapes:
  - C: records list (K=6 deterministic sample) + task → "output only
    the final value";
  - D: procedure text (compiled with support/margin floors) + task →
    "output only the final value".
- Model settings: glm-5.3, coding endpoint, High effort, 4096
  max_tokens, temperature 0, 300 s per-call timeout.
- **Cap: exactly 2 sends, slots 0..1, dedicated O_EXCL ledger
  (`g2-probe-ledger`, files `g2-probe-slot-000/001.json`). No retries.
  No third send is possible in any process sharing the ledger.**
- Recorded per send: request class, latency, prompt/completion token
  usage, finish reason, parseability, correctness vs the fixture
  oracle (informational), failure classification
  (`completed_parseable / empty / length / transport_error`).

## Frozen interpretation rules (owner-fixed)

1. Success of both requests = the request classes are TECHNICALLY
   usable at the registered operating point → permits completing the
   statistical freeze (prereg §4.2/§4.3). It is NOT proof of
   statistical stability and launches NOTHING.
2. Failure of either class (timeout / empty after completion / non-
   parseable / transport) HALTS the campaign path; the operating point
   or design returns to the owner for decision.
3. Correctness of the two answers is INFORMATIONAL only — the probe
   measures request-class viability, not organizational effect.
4. The full scientific campaign remains NO-GO until separately
   authorized by the owner.

## Out of scope

No organizations, no arms, no evidence mixture sampling, no variance
estimation, no Probe-reserve usage, no threshold or protocol changes
after dispatch, no result promotion of any kind.
