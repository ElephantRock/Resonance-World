# G1 procedure representation comparison — PROSPECTIVE (frozen 2026-10-26; NOT dispatched — awaiting explicit owner GO)

Status: **PROSPECTIVE / FROZEN design; dispatch requires a separate explicit
owner GO.** Registered at the project owner's direction after the C3R-G1
novel-grammar pilot and its send reconciliation (REV2, run `40357785223`).

## Research question (the precise discrimination)

Is GLM-5.3's execution failure on explicit procedures caused by the
COMPRESSED A/B code representation, or would it fail to follow the sequence
even when explained in clear executable natural language?

Same correct procedure, same NEW random holdout inputs, same uniform budget —
the ONLY variable is the representation of the procedure in the prompt.

## Design

- Families: `digits` and `rotate` (their true programs are now public — no
  secrecy requirement for an execution-only test; burned induction units are
  irrelevant because there is NO induction in this experiment).
- Programs: 8 fixed 5-bit programs (the published ones may be reused — they
  are public).
- Holdout inputs: freshly sampled per (program, representation, wave),
  unambiguity-checked.
- Arms (paired per program × wave):
  1. **code** — prompt discloses the grammar + "Procedure capsule: <5-bit>"
     + new task → final value.
  2. **natural** — prompt discloses the grammar + the same procedure written
     as explicit numbered natural-language instructions (e.g., "Step 1:
     swap the two middle digits...") + the SAME new task → final value.
- 2 waves per arm (fresh inputs), uniform High/4096, coding route,
  temperature 0, no retries, every send in the denominator, ITT accounting.
- Deterministic control: the true executed output (offline) defines
  correctness.

## Budget (fixed)

8 programs × 2 families... precisely: 4 programs per family × 2 families ×
2 representations × 2 waves = **64 sends** (8 per CI process, mirroring the
established ≤8-per-process discipline). Independent durable ledger
(PhysicalSendLedger per process ≤ 8; campaign total recorded in the summary).

## Predeclared readings

- Primary: paired holdout success difference natural − code.
- If natural ≫ code: the compressed representation is the bottleneck →
  procedural memory for this model class should use natural-language
  procedures (testable in an organizational design).
- If both fail: a deeper instruction-following limit on multi-step explicit
  procedures is documented → organizational procedural-memory designs on
  GLM-5.3-class models are not supported by this evidence.
- If both succeed: execution fidelity is budget/attention-dependent, not
  representational — report the boundary.

## Explicitly out of scope

No induction, no retention, no feedback rounds, no organizational test, no
changes to the frozen G1 v9 protocol, no new platform work beyond the
dispatch script + prompts.
