# G1 novel grammar generalization — RESULT (2026-10-26) — REV1 (redacted + accounting corrections)

**REV1 corrections (2026-10-26, per project-owner review; the pre-execution
preregistration and all sends are unchanged):**
1. **Redaction:** REV0's induction table published the hidden programs and
   induced capsules. REV1 redacts them. Git history retains the original
   values; **these 8 units are burned as secrets for any future test** and
   must not be reused.
2. **Raw-arm accounting:** REV0 reported "11 scored + 4 excluded". The exact
   accounting is **11 evaluated (all correct) + 5 unscored invalid_format
   responses = 16/16 prescribed**, all preserved with attribution below. The
   "100%" applies to evaluable responses only; **11/16 = 68.75% of planned
   raw sends produced a valid evaluable answer**.

Status: run `40357785223` — all 10 jobs succeeded. 72/72 prescribed sends.
Exploratory pilot; `scientific_acceptance=false`.

## 1) Source induction on NOVEL grammars — the bottleneck

| unit | family | status | capsule | true program | source_correct |
|---|---|---|---|---|---|
| novel-digits-00 | digits | accepted | [redacted] | [redacted — burned] | **False** |
| novel-digits-01 | digits | accepted | [redacted] | [redacted — burned] | True |
| novel-digits-02 | digits | accepted | [redacted] | [redacted — burned] | True |
| novel-digits-03 | digits | accepted | [redacted] | [redacted — burned] | True |
| novel-rotate-00 | rotate | invalid_format | — | [redacted — burned] | None |
| novel-rotate-01 | rotate | accepted | [redacted] | [redacted — burned] | **False** |
| novel-rotate-02 | rotate | accepted | [redacted] | [redacted — burned] | **False** |
| novel-rotate-03 | rotate | accepted | [redacted] | [redacted — burned] | True |

**Source-correct: 4/8 = 50% (plus 1 invalid_format).** On the KNOWN families
(arithmetic/text) the factorial measured 87.5–100% correct. The drop to 50%
under family novelty is the generalization gap, measured.

## 2) Holdout execution per arm — corrected accounting

| arm | prescribed | evaluated | correct (of evaluated) | unscored invalid_format | correct / prescribed |
|---|---:|---:|---:|---:|---:|
| **learned** (retained capsule) | 16 | 14 | 5 (**35.7%**) | 2 (rotate-00 ×2: no capsule — induction invalid_format) | 31.3% |
| **raw** (same examples re-given at execution, no capsule) | 16 | 11 | 11 (100% of evaluated) | **5**: wave1/digits-00, wave1/rotate-02, wave2/rotate-00, wave2/rotate-01, wave2/rotate-02 (all `invalid_format`, empty answer after stop) | **68.75%** |
| fresh (random capsule) | 16 | 15 | 0 (0%) | 1 | 0% |
| neutral (random capsule) | 16 | 13 | 2 (15.4%) | 3 | 12.5% |
| **total** | **64** | **53** | **18** | **11** | |

Wave-session sends: 64 (16 per arm). Plus induction: 8. **Total 72/72** — the
campaign cap; the probe ledger (2 reserved) untouched.

Per-unit detail retained in the run artifacts (run `40357785223`, retention
90 days) and local owner-only copies (`%TEMP%\novel-arts`).

## 3) The discriminating answer

**The retained capsule added no value over re-derivation from the same raw
examples — it underperformed it on evaluable responses (5/14 = 35.7% vs
11/11 = 100%), and the raw arm additionally delivered 68.75% valid-answer
yield against the learned arm's 87.5% valid induction but worse final
outcomes.**

- Where the capsule was WRONG (4 units), the learned arm executed a wrong
  procedure; the raw arm re-induced correctly from the identical examples on
  every evaluated occasion (`digits-00`: learned wrong, raw correct in both
  waves).
- Where the capsule was RIGHT (rotate-03), the learned arm still mis-executed
  it on both waves ("s_ilc_9" vs "ws_ilc9"; "ozu_cl9" vs "zu_clj9") —
  retention did not guarantee faithful execution.
- The raw arm's own failure mode is disclosed and preserved: 5 empty
  invalid_format responses concentrated in rotate (4/5) and wave2 (3/5).

## 4) Controls behaved as designed

fresh: 0/15 evaluated (random capsules never reproduce unambiguous outputs);
neutral: 2/13 — both hits are chance coincidences with the true program
(1/32 per draw). No leakage signal.

## 5) Verdict per the predeclared rules

- **Source acquisition under family novelty: FAILED** (4/8 + 1 invalid).
  The C3R-G2 worksheet rule applies: stop at G1.
- **Retained-procedure value over raw re-derivation: NOT supported.**
- Therefore: no C3R-G2 organizational testing on this mechanism.
- `scientific_acceptance=false`; Pattern Register unchanged.

## 6) Evidence and disclosure

Run artifacts (GitHub, 90-day retention): induction manifest/capsules are
owner-only and were uploaded as a private artifact to this repository's
Actions storage — **not** to the public Git tree. Local owner-only copies:
`%TEMP%\novel-arts`. Hidden programs were published in REV0 of this file
(superseded by this redaction); the eight units are burned as future secrets.

## 7) Next-step candidates (registered, not commitments)

1. Interactive-feedback induction on novel families (bounded rounds) —
   does correction close the 50% gap? (owner GO 2026-10-26, second decision)
2. Execution-fidelity measurement with evaluator-supplied correct capsules —
   isolates the rotate-03 failure surface.
3. Reasoning-effort ablation restricted to novel families.
