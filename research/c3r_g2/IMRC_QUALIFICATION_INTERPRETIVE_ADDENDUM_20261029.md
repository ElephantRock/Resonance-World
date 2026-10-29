# IMRC qualification — interpretive addendum (2026-10-29; read-only over the committed result)

Status: **addendum only.** The committed qualification report and its
`QUALIFICATION PASSED` verdict under its pre-registered operational
gate are preserved unchanged. This addendum adds the owner's
interpretive corrections (decision 2026-10-29) without modifying any
file.

## 1. What the result does and does NOT establish

The pre-registered gate (evaluator validity + no-forced-sign) passed
operationally. The result does NOT prove net institutional value:

- Across the 135 deterministic chains, **CURATED's per-generation curve
  is IDENTICAL to RESET's in 129/135 chains** (including 45/45 at
  saturation 1×). Mean decision accuracy over stressed generations:
  CURATED 93.43%, RESET 93.33%, UNCURATED 89.72%, FROZEN 70.74%.
- The positive Δ_Resilience values therefore mostly measure
  **recovery to reset-level performance by shedding harmful old
  evidence** — not an institutional capability that exceeds what
  fresh members achieve from current evidence alone.

## 2. Three structural caveats (owner-identified; documented)

1. **Retrieval-engine artifact at high saturation.**
   `admissions_per_generation` emits ~1 / ~5 / ~14 records per context
   per generation at saturation 1× / 4× / 12×. With the 6-record
   recency-first budget, the current generation's records fill the
   window at 4× and dominate it at 12×. The wide saturation ties are
   a CORRECT result for this system — but they do not prove that
   curation is useless for large institutional memories in general.
2. **Eligibility recomputation, not permanent retirement.** The
   CURATED pool is rebuilt from the full `store` at each generation
   start and C1/C2 are re-applied; a previously excluded record can
   re-enter the eligible set when conditions change. This is a
   declared property of the CURRENT design (a re-evaluation policy),
   distinct from permanent institutional retirement; the distinction
   is now explicit and will be a declared design choice in any future
   protocol.
3. **Curation cost is counted, not converted.** The report counts
   policy passes and retirement events, but does not convert them to
   a net utility metric. A positive Δ_Resilience alone does not
   establish economic or organizational feasibility.

## 3. Status of the C1/C2 curation candidate

Per the owner's decision, **C1/C2 is CLOSED as a candidate for direct
confirmatory freeze.** The qualification grid and its results remain
frozen and are NOT re-run. The new independent design is in
`IMRC_BREA_INDEPENDENT_DESIGN_20261029.md`.
