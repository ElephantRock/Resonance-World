# G1 feedback-acquired natural procedural memory v2 — operational rehabilitation — PROSPECTIVE (frozen before first send)

Status: **PROSPECTIVE / FROZEN before any provider dispatch.**
Authorization: project owner conditional GO (2026-10-28 evening).
This is an **operational rehabilitation attempt of ONE closed
experiment** — not a silent amendment of it. The v1 campaign (runs
40684468956 / 40686295703, RESULT at `cce4f46`) closed with its gate
failed for apparatus reasons: no capsule was ever produced. Per the
owner's decision table, exactly one re-calibrated attempt is
authorized; if it fails, this line closes with no chained rescues.
`scientific_acceptance=false` (exploratory gate, unchanged).

## What changes vs v1 (ONLY operating point and units)

- Per-call transport timeout: 180 s → **300 s** (the transport's
  documented bound; not a guarantee of completion).
- Generation budget for **induction requests only** — learning-loop
  sends (draft/apply/revise) AND the Raw re-derivation arm:
  4096 → **16384**. The Learned and Fresh arms stay at the frozen
  **4096** (executing a written procedure was never budget-starved:
  96/96 and 32/32 parseable in the stepwise/semantic-clarity
  campaigns).
- **New units**: new program codes and new inputs derived from a NEW
  seed domain (v2) over the SAME two frozen unburned families
  (binary/alpha) and the SAME frozen evaluator. Zero requests are
  re-sent from v1 (structurally: every prompt differs).
- **Independent permanent ledger** (feedback2-ledger, slots 0..95) and
  a fresh 96-send cap. The 44 sends consumed by v1 are not reused and
  not refunded.

## Frozen structure (everything else identical to v1)

4 programs (2 binary + 2 alpha, v2 codes) x [3 evidence pairs + 3
probes + 4 evaluation inputs] — unambiguous, globally unique. The
learning loop: draft → (apply → revise) x ≤3 rounds, distinct probes,
empty-guard re-prompt once per request (a new ledgered send, never
terminates the loop alone), transport failure aborts that program
without retry, per-program learning hard-capped at 10 sends. The
capsule is the model's own text, stored verbatim; the Learned
executor sees ONLY the capsule. Raw sees only the same 3 evidence
pairs; Fresh sees only the input. 16 evaluation tasks per arm, one
send each, ITT keeps every failure in the denominator. The harness
never renders a procedure for the agent.

**Slot plan (96, O_EXCL, independent ledger):**
- qualification 88..95 (see below)
- learning: program p block = 10 slots at p*10 → 0..39
- Learned 40..55, Raw 56..71, Fresh 72..87

## Qualification gate (owner condition 3) — BEFORE the campaign

A dedicated, never-evaluated qualification unit (binary family, v2
seed). Budget ≤ 6 sends, slots 88..95:
1. **Capsule check:** a draft send (16384/300 s) must return a
   non-empty five-step capsule; one empty-guard retry allowed.
2. **Apply check:** an apply send on a qualification probe must
   complete (`finish=stop`, non-empty) — correctness is NOT required
   (it is a scientific outcome, not an operational one).
3. **Raw check:** one Raw-arm send (16384/300 s) on a qualification
   input must complete (`finish=stop`, non-empty).

**Any exhaustion (timeout / empty after guard) → qualification FAILS
→ the full campaign is NOT dispatched.**

## Predeclared progress gate (identical to v1, frozen)

- **G1:** Learned ITT ≥ 10/16 AND Learned − Fresh ≥ +8
- **G2:** paired Learned − Raw ≥ +4
- Both → the chain acquisition → self-authoring → storage →
  fresh-session execution is demonstrated on this apparatus.
- Otherwise → the current acquisition mechanism closes WITH a
  scientific result.

## Owner's final decision table (adopted verbatim)

| outcome | decision |
|---|---|
| qualification fails at 300 s | close the operating point; no full campaign |
| campaign completes, gate fails | close the current acquisition mechanism with a scientific result |
| campaign completes, gate passes | consider C3R-G2 transition per an independent protocol |

## Explicitly out of scope

No Probe sends; no reuse or re-send of any v1 request; no threshold
change after seeing results; no loop redesign (that is option 3,
explicitly not chosen); no platform work; no fourth arm; no
retrospective re-scoring of earlier campaigns.
