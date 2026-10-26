# G1 novel grammar generalization — RESULT (2026-10-26)

**Run:** GitHub Actions `40357785223` — all 10 jobs succeeded.
**Campaign:** 72/72 prescribed sends (8 induction + 32 wave1 + 32 wave2), High/4096,
glm-5.3, coding route, two NOVEL grammar families (`digits`, `rotate`),
separate Python sessions, no retries, every send in the denominator.
**Preregistration:** `G1_NOVEL_GRAMMAR_GENERALIZATION_PROSPECTIVE_20261026.md`
(amendment A1 pre-dispatch: rotate step3 window 7→6, zero sends preceded it).

## 1) Source induction on NOVEL grammars — the bottleneck

| unit | family | status | capsule | true program | source_correct |
|---|---|---|---|---|---|
| novel-digits-00 | digits | accepted | ABBAB | ABABB | **False** |
| novel-digits-01 | digits | accepted | BBAAB | BBAAB | True |
| novel-digits-02 | digits | accepted | ABAAA | ABAAA | True |
| novel-digits-03 | digits | accepted | BAAAB | BAAAB | True |
| novel-rotate-00 | rotate | invalid_format | — | ABBBB | None |
| novel-rotate-01 | rotate | accepted | ABAAA | ABAAB | **False** |
| novel-rotate-02 | rotate | accepted | BABAA | BABAB | **False** |
| novel-rotate-03 | rotate | accepted | BBBBA | BBBBA | True |

**Source-correct: 4/8 = 50% (plus 1 invalid_format).** On the KNOWN families
(arithmetic/text) the factorial measured 87.5–100% correct. Novel-grammar
induction is therefore the capacity bottleneck: the drop from ~90% to ~50%
under family novelty is the generalization gap, measured.

## 2) Holdout execution per arm (the discriminating comparison)

| arm | scored | correct | rate | excluded (invalid/no-capsule) |
|---|---:|---:|---:|---:|
| **learned** (retained capsule) | 14 | 5 | **35.7%** | 2 (induction invalid_format) |
| **raw** (same examples re-given at execution, no capsule) | 11 | 11 | **100%** | 4 rotate-wave2 invalid responses |
| fresh (random capsule) | 15 | 0 | 0% | 1 |
| neutral (random capsule) | 13 | 2 | 15.4% | 3 |

Per-unit detail (kept in the run artifacts and locally at
`%TEMP%\novel-arts`): the learned arm failed EVERY rotate holdout — including
`novel-rotate-03` whose capsule was source-CORRECT (execution errors: "s_ilc_9"
vs truth "ws_ilc9") — and failed `digits-00` (wrong capsule) plus one correct-
capsule execution slip (`digits-03` wave2: 102 vs 602).

## 3) The discriminating answer

**The retained capsule added no value over re-derivation from the same raw
examples — it underperformed it (5/14 vs 11/11 on scored units).**

- Where the capsule was WRONG (induction failure), the learned arm executed a
  wrong procedure; the raw arm re-induced correctly from the identical
  examples (`digits-00`: learned wrong, raw correct in both waves).
- Where the capsule was RIGHT (rotate-03), the learned arm still mis-executed
  it on both waves — retention did not even guarantee faithful execution.
- The raw arm's own weakness is disclosed: 4 rotate-wave2 responses were
  invalid (excluded per protocol, counted, never hidden) — 11/11 scored.

## 4) Controls behaved as designed

fresh: 0/15 (random capsules never reproduce unambiguous task outputs);
neutral: 2/13 — both hits are chance coincidences where the random capsule
equaled the true program (1/32 per draw, observed 2/13 consistent with
expectation). No control signal suggests any leakage.

## 5) Verdict per the predeclared rules

- **Source acquisition under family novelty: FAILED** (4/8 correct + 1
  invalid; the C3R-G2 worksheet rule applies: "if a source agent fails to
  acquire the prerequisite ability under the new schema, stop at G1").
- **Retained-procedure value over raw-evidence re-derivation: NOT supported**
  (point estimate negative at pilot scale).
- Therefore: **do NOT proceed to C3R-G2 organizational testing** on this
  mechanism; the organizational question ("does the organization extract
  value its members' evidence does not already give directly?") is answered
  NO at the individual-source level for novel grammars.
- `scientific_acceptance=false`; Pattern Register unchanged.

## 6) Preserved failures and evidence

- Run: `40357785223` (10/10 jobs success); artifacts retained 90 days on
  GitHub (induction manifest + capsules are owner-only and deliberately NOT
  uploaded: manifest carries hidden programs).
- Local owner-only copies: `%TEMP%\novel-arts` (manifest, capsules, all wave
  summaries).
- This repo holds the aggregate RESULT only; hidden programs are not
  committed, per track discipline.

## 7) What would make the next attempt scientific (registered candidates,
not commitments)

1. Reasoning effort ablation ON the novel families (the factorial's High/4096
   advantage was measured on KNOWN families; novel-family induction may need
   a different profile).
2. Induction-with-feedback loops (the G1 v9 lawful feedback channel) instead
   of two-shot blind induction — testing whether interactive correction closes
   the 50% gap.
3. Retention robustness: even correct capsules were mis-executed (rotate-03)
   — execution fidelity is an independent failure surface from induction.
