# G1 natural stepwise execution fidelity — PROSPECTIVE (frozen before first send)

Status: **PROSPECTIVE / FROZEN before any provider dispatch.**
Authorization: project owner GO (2026-10-27) — GO for the stepwise execution
test with the natural-language representation, following the representation
comparison result (natural instructions cut invalid responses 40.6% → 3.1%
vs code capsule, but overall ITT success remained 75%).

## Research question

Can step-by-step execution with explicit intermediate states raise the
final-task success of a CORRECT natural-language procedure from 75% (ITT)
to a reliable level, WITHOUT adding any information about the hidden truth?

The intermediate states are fully determined by (input, procedure) — no
hidden information is added. The only variable is execution granularity:
single-shot holistic vs incremental step-by-step with visible state.

## Design

- 8 public programs (4 digits + 4 rotate), 16 tasks (8 programs × 2 waves,
  1 fresh unambiguous input per (program, wave)).
- **Arm A (single-shot):** 1 send per task — the full NL procedure + the
  input → final value. **16 sends.**
- **Arm B (stepwise):** 5 sends per task — one send per step: current state
  + "apply Step N: <the step's instruction>" → intermediate state. After
  step 5, the final state is the answer. **80 sends.**
- Both arms use the SAME correct NL procedure and the SAME inputs.
- Correctness: final state == deterministic truth (evaluator-side).
- **ITT:** a task fails if any step's output is unparseable or the final
  value is wrong. All failures preserved in the denominator.
- **Hard send cap:** 96 (16 A + 80 B), enforced by a shared cross-process
  campaign ledger (O_EXCL slot files 0..95; over-budget and double-dispatch
  fail visibly).

## Predeclared success criterion

**B ITT final-task success ≥ 14/16 (87.5%) AND paired B−A ≥ +3 tasks**
→ stepwise decomposition closes the reliability gap; proceed to natural-
procedure acquisition with feedback (after apparatus fixes).

**B ITT < 14/16 or A ≥ B** → the stepwise limit is documented and the
mechanism's line stops; no threshold adjustment, no rescue redesign.

## Cost disclosure (predeclared)

Arm B costs 5× Arm A per task (80 vs 16 sends). The comparison attributes
the outcome to the composite stepwise execution system, not to the natural
representation alone. This cost asymmetry is part of the registered design.

## Explicitly out of scope

No induction, no retention, no feedback-based learning, no organizational
test, no changes to the frozen G1 v9 protocol, no new platform work.
