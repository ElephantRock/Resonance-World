# Send reconciliation — interactive fidelity campaign (run 40391144622)

Reconciled 2026-10-26 against the nine published summary files in this
directory, at the project owner's request. No experiment was re-run; this is
a bookkeeping pass over already-committed evidence.

| session file | sends | evaluated | correct | unscored invalid |
|---|---:|---:|---:|---:|
| c1-summary.json (C1 static induction) | 8 | 7 accepted | 5 source-correct | 1 invalid_format |
| c2-summary-group0.json | 2 | — | — | — |
| c2-summary-group1.json | 3 | — | — | — |
| c2-summary-group2.json | 3 | — | — | — |
| c2-summary-group3.json | 4 | — | — | — |
| C3-wave1-summary.json | 8 | 8 | 1 | 0 |
| C3-wave2-summary.json | 8 | 8 | 2 | 0 |
| C4-wave1-summary.json | 8 | 6 | 6 | 2 |
| C4-wave2-summary.json | 8 | 5 | 4 | 3 |
| **total** | **52** | **38 evaluated + 7 source-attempts** | | **6 invalid responses** |

## Findings

1. **The campaign consumed 52 physical sends**, not 72 as REV1/REV2 of the
   result document claimed. The 72 figure was a drafting error in the result
   document's header (and its "C2: 17" line); the authoritative per-session
   `sends` values above sum to **52** = C1 8 + C2 12 + C3 16 + C4 16, under
   the preregistered cap of 64. The C2 session under-ran its 24-send budget
   (12 used) because early-pass units legitimately exited after round 1 and
   the campaign's vacuous-break defect ended two malformed rounds after one
   send each.
2. Per-process discipline held: no session exceeded 8 sends
   (max PhysicalSendLedger cap), and the write-once slot journals prevented
   double-fill (the O_EXCL evidence files are in the run artifacts).
3. **Correction chain:** RESULT REV1 said "72 / C2: 17" — withdrawn here.
   REV2 carries the corrected accounting; this file is the matching pass the
   owner requested. No sends were hidden, no run violated the cap.

## Related disclosure (same review round)

The committed `c1-summary.json` has been redacted: the `capsule` values,
combined with `policy_correct`, revealed the hidden programs of 5 units.
Git history retains the originals; **all 8 units are burned as secrets for
any future induction test** (they remain usable for execution-fidelity
tests, where programs are given openly).
