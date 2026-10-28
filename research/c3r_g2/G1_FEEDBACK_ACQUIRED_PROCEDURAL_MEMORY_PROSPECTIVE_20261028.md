# G1 feedback-acquired natural procedural memory — PROSPECTIVE (frozen before first send)

Status: **PROSPECTIVE / FROZEN before any provider dispatch.**
Authorization: project owner GO (2026-10-28), adopting the Semantic
Clarity diagnostic result. One experiment covering the full chain:
acquisition from real feedback → self-authored natural procedure →
literal storage → execution in independent sessions.
`scientific_acceptance=false` (exploratory gate).

## Research question (owner-registered)

Can the agent acquire a new procedure from real feedback, convert it
itself into precise natural-language instructions, store it, and then
execute it on new inputs in independent sessions — and does the stored,
agent-owned procedure beat re-deriving from the same raw evidence at
execution time?

## Apparatus — new, unburned grammar families

Two NEW five-step families the model has never seen in any campaign
(frozen in `scripts/c3r_g1_feedback_families.py`):

- **binary** — input: 8-bit string. Steps: (1) flip every bit OR
  reverse the string; (2) keep the first 4 bits OR the last 4 bits;
  (3) move the first bit to the end OR the last bit to the front;
  (4) swap the two halves OR leave unchanged; (5) prefix OR append the
  count of 1-bits as one decimal digit.
- **alpha** — input: 8 lowercase letters. Steps: (1) swap the two
  halves OR reverse the whole string; (2) keep the 2nd/4th/6th/8th
  characters OR the 1st/3rd/5th/7th; (3) shift each letter +2 (z→b) OR
  −2 (a→y); (4) sort alphabetically OR reverse-alphabetically;
  (5) prefix OR append the number of DISTINCT letters as one digit.

4 programs (2 per family), codes derived deterministically from a
frozen seed. All task inputs are sampled deterministically, must be
**unambiguous** (all 32 codes give distinct outputs), and are
**globally unique** across the campaign — disjoint across
evidence / probe / evaluation roles AND across programs (a shared
value under two hidden programs would carry two different truths).
Truth = the frozen evaluator only. The harness NEVER renders a
procedure for the agent and never assembles the program into any
prompt.

## Arms (owner-specified)

| arm | information available at execution | what it tests |
|---|---|---|
| **Learned** | the stored capsule — the model's own natural-language procedure, verbatim | does agent-owned knowledge transfer to fresh sessions |
| **Raw** | the SAME 3 evidence pairs; re-derive then apply, one send | does re-supplying raw evidence match owning the procedure |
| **Fresh** | nothing (input only) | information-free floor + format compliance |

## Learning protocol (per program, one sequential session)

Evidence: 3 deterministic unambiguous (input → output) pairs.

1. **Draft:** given the 3 examples, write the exact procedure as five
   numbered steps, each fully explicit about positions, boundaries and
   indexing. Output only the five step lines. (1 send)
2. **Rounds r = 1..3** (each on a DISTINCT probe input, disjoint from
   evidence and evaluation inputs):
   - **Apply:** apply the current draft strictly, in order, to the
     probe; output only the final value. (1 send)
   - If the applied value == truth: **learning ends; capsule = the
     draft just validated** (recorded `validated`, rounds used).
   - Else **Revise:** "applying your procedure to <probe> gives <Y>,
     the correct output is <T>; revise the five-step procedure"
     (context retains the evidence and all prior drafts). (1 send)
3. If no round validates within 3 rounds: the LAST draft becomes the
   capsule, recorded `unvalidated`. No further learning sends.

Empty-output guard (owner-required): an empty/non-`stop` model answer
in the loop does NOT terminate learning — the same request is re-issued
once with an explicit non-empty instruction (a new ledgered send). A
transport-level failure does NOT retry: the program's learning aborts,
capsule = last draft, failure recorded under `transport`.

The capsule is stored **verbatim**. The Learned executor is a fresh
session that sees ONLY the capsule + the new input (never the evidence,
drafts, probes or history).

## Execution (per arm)

16 evaluation tasks per arm (4 programs × 4 fresh unambiguous inputs,
identical across arms). One send per task. glm-5.3, coding endpoint,
High/4096, temperature 0. ITT: a task fails if unparseable/empty or
wrong; all failures stay in the denominator; no retries.

## Failure taxonomy (accounted separately)

Per send: `transport` / `empty_or_unparseable` / `wrong_value` /
`correct`. Acquisition is graded separately from execution:
`validated` (capsule reproduced truth on a held-out probe inside the
learning session), `capsule_format_ok` (five numbered step lines),
rounds and sends used. Learned-arm wrong values on a validated capsule
are reported as residual induction-vs-execution error (not separable
without further arms — stated, not assumed away).

## Predeclared progress gate (frozen)

- **G1 — repeatable value:** Learned ITT ≥ 10/16 (62.5%) AND
  Learned − Fresh ≥ +8 tasks.
- **G2 — beats re-derivation:** paired Learned − Raw ≥ +4 tasks
  (same effect size the Semantic-Clarity wording fix demonstrated).
- **Both G1 and G2 →** the acquisition→storage→execution chain is
  demonstrated on this apparatus; proceed to the next registered step.
- **Otherwise →** the line CLOSES. No rescue redesign, no threshold
  adjustment, no extra learning rounds.

Rationale: Learned must clear the information-free floor by a wide
margin AND beat re-supplying the very evidence it learned from —
otherwise stored procedural knowledge adds nothing over raw re-derivation.

## Hard send cap: 80 (frozen, O_EXCL ledger 0..79)

- Learning: 4 programs × 8 slots each (draft + ≤3 applies + ≤3 revises
  + empty-guard reserve; hard-capped at 8 sends per program) →
  slots 0..31.
- Execution: Learned 32..47, Raw 48..63, Fresh 64..79 (16 each).
Over-budget and double-dispatch fail visibly. Cost is reported per arm
(Owner decision framing: information available vs sends spent).

## Explicitly out of scope

No new platform work, no fourth arm (no harness-authored "true"
procedure arm — the three owner-specified arms only), no re-scoring of
earlier campaigns, no use of the two reserved Probe sends, no G2
transition before this chain passes its gate, no rescue rounds if the
gate fails.
