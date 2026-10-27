# G1 procedure representation comparison — RESULT (2026-10-27)

**Run:** GitHub Actions `40514458556` — all 10 jobs succeeded.
**Campaign:** 64/64 sends (8 batches × 8, disjoint slot ledger 0..63 enforced
across processes; over-budget and double-dispatch fail visibly).
**Design (frozen):** same 8 public procedures (4 digits + 4 rotate), same
fresh holdout inputs per (program, wave, half), ONLY the representation
differs: **code** (grammar + `Procedure capsule: <5-bit>`) vs **natural**
(the same procedure as explicit numbered natural-language instructions).
**Classification:** exploratory pilot; `scientific_acceptance=false`.

## 1) Primary result — valid-answer yield (the discriminating measure)

| representation | sends | evaluated | correct | **valid-answer yield (ITT)** | accuracy among evaluated |
|---|---:|---:|---:|---:|---:|
| **code capsule** | 32 | 19 | 16 | **50.0%** | 84.2% |
| **natural instructions** | 32 | 31 | 24 | **75.0%** | 77.4% |

**The code-capsule representation produced 13 unscored (invalid/empty)
responses vs 1 for natural instructions.** Among evaluable responses the
accuracy gap is small (84.2% vs 77.4%, favoring code); the decisive
difference is response VALIDITY. The compressed A/B capsule representation
causes the model to fail-to-answer far more often.

## 2) Paired discordance (same task, both arms)

Of 32 paired comparisons: **16 both-correct, 0 natural-only, 0 code-only,
16 with ≥1 unscored response.** Zero discordance among evaluable pairs —
the representations do not differ in accuracy; they differ in whether the
model produces a parseable answer at all.

## 3) Answer to the registered question

> Is the execution failure caused by the compressed A/B representation, or
> would the model fail to follow the sequence even when clearly explained?

**Answer: the compressed representation is a major cause.** With
natural-language instructions the invalid-response rate drops from 40.6%
(13/32) to 3.1% (1/32), while accuracy among valid responses remains
comparable. The earlier pilot's C3 result (3/16 execution fidelity with
correct capsules) is largely explained by the A/B capsule representation
driving the model into unparseable/empty responses — not by an inability to
follow multi-step procedures per se.

## 4) Implications for procedural memory on this model class

- Procedural memory for GLM-5.3-class models should store procedures in
  **explicit natural-language step form**, not compressed symbolic codes.
- The residual 22.6% invalid+wrong under natural instructions still bounds
  single-shot execution fidelity — multi-round execution with feedback
  remains the reliable path (per the interactive-fidelity result).
- These findings are specific to glm-5.3 on the coding endpoint, High/4096,
  two novel grammar families, and single-shot execution. They do not
  establish multi-day retention, organizational transfer, or weight learning.

## 5) Evidence

Run `40514458556` (90-day artifact retention): 8 batch summaries
(`repr-summary-*.json` with per-send answer/truth/correct/latency) +
`representation-manifest.json`. All sends consumed exactly the 64-slot
campaign ledger (disjoint slot indices 0..63; over-budget and double-
dispatch fail visibly — tested).

## 6) Predeclared reading (from the frozen prospective) — verdict

- natural ≫ code on valid-answer yield → **supports the linguistic-
  executive representation hypothesis** for response validity.
- Accuracy among evaluable responses is comparable (84.2% vs 77.4%) →
  the representations do NOT differ on task competence.
- Net: representation choice is an **execution-reliability lever**, not an
  accuracy lever.
