# G1 feedback-acquired natural procedural memory — RESULT (2026-10-28)

**Runs:** A = `40684468956` (first dispatch, registered parameters),
B = `40686295703` (A1 recovery, documented pre-data).
**Registered gate:** Learned ITT ≥ 10/16 AND Learned−Fresh ≥ +8 AND
Learned−Raw ≥ +4 → else the line closes.
**Outcome: GATE FAILED — the primary Learned-vs-Raw comparison was
never established, because the apparatus could not deliver a learnable
capsule under the registered operating point.** Per the frozen rule: no
rescue rounds, no threshold adjustment. Re-parameterization is the
owner's decision, not taken here.
`scientific_acceptance=false`.

## 1) What actually happened (three distinct apparatus failure modes)

1. **Learning at High/4096 (run A):** all 8 first-attempt draft sends
   (2 per program incl. the empty-guard retry) returned
   `finish_reason=length` with EMPTY output (~99 s each) — GLM-5.3's
   always-on reasoning exhausted the generation budget before any
   draft. Zero capsules, zero scientific content (A1, pre-data).
2. **Learning at High/16384 (run B):** all 4 draft sends died at the
   transport timeout — latency exactly ~180.2 s each
   (`ProviderTransportRejected` at the configured 180 s per-call
   bound). At the larger budget the induction reasoning simply
   outgrows the registered per-call timeout.
3. **Raw arm at the frozen High/4096:** 14/16 sends hit
   `finish_reason=length` (empty) — one-shot re-derivation + execution
   starves the SAME budget. The Raw arm as registered measures budget
   starvation, not re-derivation ability.

## 2) The numbers the registered machinery produced

| arm | ITT | evaluated | unparseable | sends |
|---|---:|---:|---:|---:|
| Learned | 0/16 | 0 | 0 | **0** (no capsule for any program → 16 × `no_capsule`) |
| Raw | 2/16 | 2 | 14 | 16 |
| Fresh | 0/16 | 10 | 6 | 16 |

Paired: learned-vs-raw 0/2/0/14, learned-vs-fresh 0/0/0/16.
Learning: validated 0/4, capsule_format_ok 0/4, transport_aborted 4,
sends 4 (run B) + 8 wasted (run A, pre-data A1).

**Physical send accounting: 44 of the frozen 80 cap** (8 + 4 learning,
32 control arms, 0 learned). Slots: learning first attempt 0–1 per
program, recovery 2 per program (offset), controls 48–79 block,
learned 32–47 untouched.

## 3) The one genuine scientific observation (anecdotal, NOT ITT)

Both Raw sends that COMPLETED (both alpha-00 tasks) produced the
EXACT truth (`igxfazjn8`, `lsvsbvam6`) — one-shot re-derivation from 3
evidence pairs succeeded whenever the token budget let it finish.
Combined with Fresh 0/10 evaluated-correct, the information floor
works and the raw evidence IS sufficient for the model in principle.
The bottleneck observed tonight is operating-point (budget/timeout),
not induction capability. 2/2 is anecdote, not evidence — stated as
such.

## 4) Answer to the owner's registered question

**Not answered by this run.** The chain
acquire → self-author → store → fresh-session execution was never
armed: the model did not get to produce a capsule under either
budget, so Learned-vs-Raw remains unmeasured. What IS established:
- the two new unburned families work (frozen evaluator, unambiguous,
  globally unique inputs; hand-verified);
- the information-free Fresh floor behaves (0/16);
- single-shot re-derivation from 3 pairs is feasible when it completes
  (2/2);
- the registered operating point (High effort + 4096 + 180 s) cannot
  carry induction-grade reasoning for this model.

## 5) The owner's decision point (no action taken)

Options, per contract rule 3 (cap on reviews, not safety):
(a) re-parameterize ONCE (e.g., learning + raw arms at 16384 with a
300 s per-call timeout — both within the transport's documented
bounds) and re-run against the SAME frozen gate; the 36 remaining
unused sends of the 80 cap cannot fund a full re-run — a new capped
run would be required;
(b) close the acquisition line at this operating point and record the
bottleneck;
(c) redesign the learning loop toward smaller per-send reasoning loads
(e.g., stepwise induction) — that is new-design territory, not a
parameter fix.

## 6) Evidence

`research/c3r_g2/evidence_feedback_memory_20261028/`: frozen manifest,
`learn-firstattempt-*` (run A: 8 empty sends), `learn-*` (run B: 4
timeout sends), `capsule-*` (all null), `summary-{raw,fresh,learned}`,
`feedback-report.json`. Runs `40684468956`, `40686295703` (90-day
artifact retention). Amendment A1 trail in the prospective. Zero Probe
sends touched.
