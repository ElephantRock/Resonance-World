# G1 feedback-acquired procedural memory v2 — operational rehabilitation — RESULT (2026-10-28)

**Run:** `40705158773` — offline ✓, manifest ✓, **qualification FAILED
(1 send)**, every campaign job skipped by the CI gate (learn, raw,
fresh, learned: `skipped` — zero campaign sends dispatched).
**Owner decision table, applied verbatim:** qualification failure at
300 s → **the operating point CLOSES; no full campaign.**
`scientific_acceptance=false`.

## 1) The qualification evidence

The single qualification draft send (16384-token induction budget,
300 s per-call timeout) ran for **300.2 s** and was killed by the
transport bound (`ProviderTransportRejected`, latency 300206 ms,
slot 88, one send consumed). The model's always-on High-effort
reasoning did not complete an induction draft even at the maximum
documented per-call settings of the transport layer.

## 2) The three operating points now on record (escalating, same wall)

| attempt | budget | timeout | outcome |
|---|---|---|---|
| v1 run A (8 sends) | High/4096 | 180 s | `finish_reason=length`, EMPTY output (~99 s each) |
| v1 run B (4 sends) | High/16384 | 180 s | killed at exactly ~180.2 s |
| v2 qualification (1 send) | High/16384 | **300 s** | killed at exactly ~300.2 s |

Across a 4× generation budget and a 1.67× timeout, procedure
INDUCTION from examples never completed once. By contrast, EXECUTION-
style requests were never the bottleneck (128/128 parseable across the
stepwise and semantic-clarity campaigns at High/4096).

## 3) Conclusion (bounded to what was measured)

At the tested operating points, GLM-5.3 on the coding endpoint cannot
complete induction-from-examples reasoning within any per-call bound
the transport permits. The acquisition question — does stored,
agent-authored knowledge beat re-supplying raw evidence — **remains
unmeasured**: the Learned arm never received a capsule, and the owner's
table closes this path without chained rescues. The single favorable
datum stays v1's anecdote (2/2 completed raw re-derivations exactly
correct at 4096); it is not ITT evidence.

## 4) Final disposition (per the owner's conditional GO)

- **The acquisition line via this protocol is CLOSED** (three
  operating points, one qualification gate, no campaign).
- Physical sends across the whole acquisition program: **45** (v1: 44;
  v2: 1). No Probe sends touched. No threshold was changed after
  seeing results. The frozen gate was never armed.
- Any further attempt requires a NEW owner decision — the recorded
  options are (c) from the previous decision point: redesign the
  induction load itself (e.g., stepwise acquisition, lower reasoning
  effort for drafts, or few-shot scaffolds) — i.e., a different
  scientific apparatus, not a parameter change.

## 5) Evidence

`research/c3r_g2/evidence_feedback_memory2_20261028/`: frozen v2
manifest (new units, qualification plan, 96-slot layout),
`qualification.json` (the 300.2 s transport kill), `feedback2-report.json`
(OPERATING POINT CLOSED). Run `40705158773` (90-day retention).
v1 evidence: `evidence_feedback_memory_20261028/` (runs 40684468956,
40686295703).
