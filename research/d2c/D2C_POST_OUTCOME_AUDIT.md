# D2c post-outcome audit note

Status: **post-outcome provenance clarification only**. This file does not amend the frozen D2c preregistration, rerun the campaign, alter the frozen evaluator result, or change the D2c classification.

## Bootstrap seed wording discrepancy

The frozen `research/d2c/PLAN.md` states that the deterministic paired-bootstrap sensitivity uses 50,000 replicates with prospectively fixed seed `2026090101`.

The frozen evaluator implementation instead applies the registered base seed plus the schema enumeration offset:

```text
parity_pair     -> 2026090101 + 0 = 2026090101
interval_pair   -> 2026090101 + 1 = 2026090102
pairwise_order  -> 2026090101 + 2 = 2026090103
```

This follows `scripts/evaluate_d2c_schema_generalization.py`, which enumerates `core.SCHEMA_ORDER` and passes `bootstrap_seed_offset=schema_offset`, and `scripts/d2c_schema_stats.py`, which uses `BOOTSTRAP_SEED + bootstrap_seed_offset`.

The frozen PLAN is intentionally left unchanged after outcome-bearing execution. Its committed SHA-256 remains `463108abee48960fd6e28572a2ff767e00566ad2ac3454bc4a6ff8d404dbd3b3` as recorded in the D2c closeout.

## Scientific effect

This discrepancy does **not** alter the confirmatory decision. The bootstrap was preregistered as deterministic sensitivity analysis only. D2c was classified `D2c-S1` because all three schemas failed the preregistered P0 source-development gate under the primary paired normal analysis before P1/P2 confirmatory entry. No bootstrap quantity was used to rescue or change that gatekeeping decision.

The authoritative evaluator result remains SHA-256 `066b846e7fe9b9dc6abd1210fa297788c27a3161d70090a38a1d155133521489` and is not regenerated here.

No same-stream rerun, threshold change, seed repair, or retrospective preregistration edit is authorized.

Production/default Historical Substrate remains **OFF**.
