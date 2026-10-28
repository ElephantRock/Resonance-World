# G2 interaction — final statistical audit — RESULT (2026-10-29; zero sends)

Status: **ONE offline correction executed under the owner's audit
mandate (2026-10-29).** Live sends: ZERO (G2 live total remains 386).
Confirmatory freeze NO-GO; campaign NO-GO; Pattern Register and G3
untouched. Canonical output:
`evidence_g2_qualification_20261028/statistical-audit.json`; tests
`tests/test_g2_statistical_audit.py` (7/7).

## 1) All mandated corrections implemented

1. **C-failure sign fixed with explicit semantics:** scenario
   probabilities are DECISION-level; C output failures are applied
   ONCE at the cell level (an exhausted cell scores 0), which RAISES
   observed ITT NV by ≈ fail × p_C (≈ +7.2pp at p_C=0.80). Direction
   asserted by a real test (`test_c_failures_raise_observed_nv`);
   the vacuous `or True` line is gone.
2. **Joint stratified simulation:** each simulated organization draws
   a band cell uniformly, then an ENVIRONMENT draw from that cell's
   MEASURED cross-seed G/NV distributions (restoring the
   environment-draw variance that fixed-probability scenarios omit),
   then a logit-scale organization effect (shared vs independent-arm
   cases), then 16 bounded Bernoulli cells per arm. Outcomes respect
   [0,1] by construction; repeated tasks are never independent units.
3. **Full hierarchical gate per replicate:** NV = D_VAR−C (ITT) must
   pass (positive ∧ one-sided-significant ∧ estimate ≥ SESOI) BEFORE
   G is tested with the same joint gate. G-alone power is never used
   to justify N (test: G-pass without NV-pass closes the gate).
4. **Time/cost corrected:** at the 52-org cap: **7.70 summed
   execution hours** (6.12 C + 1.57 D), ≈ **2.0 wall-clock hours at 4
   parallel jobs**, ≈ **1.06M expected completion tokens** (ceiling
   10.24M). The draft's erroneous "43 hours" is corrected.
5. **Verdict rule declared before running:** eligible iff min-N ≤ 52
   at both correlations and all σ under NV decision offsets
   {+10pp, +20pp} — with hypothesis and distribution UNCHANGED (no
   favorable narrowing, no SESOI reduction).

## 2) Result: the design is NOT fundable under the frozen rules

Measured band environment distributions (from the passed
no-forced-sign check, 20 α×band strata): G means **−0.05 … +0.725**
(pooled ≈ +0.33) with cross-seed SDs up to ~0.58; idealized
D_VAR−C means ≈ **0.03 average with several non-positive cells**.

Under the full hierarchical gate at the 2,500-send cap
(≤ 52 organizations):

| NV decision offset | min-N (80% power, any σ/correlation) |
|---:|---|
| −10pp / 0pp / +10pp / **+20pp** | **none achievable** (even the most favorable case: σ=0.5, shared effect) |

The blocking structure is honest and two-fold: (a) the FIRST gate
(net value D_VAR−C) cannot be powered within the cap because the
live NV is unmeasured and the idealized band NV averages ≈ 0 with
negative cells — offsets large enough to fix it would be assuming
the answer; (b) the pooled band G variance (environment draws) keeps
the second gate under-powered at N ≤ 52.

## 3) Verdict (the owner's binary, applied verbatim)

> **CLOSE LIVE LINE.**

Per the pre-declared rule: no narrowing to favorable cells, no SESOI
reduction, no distribution change to rescue fundability. The audit
prevented spending 2,500 live sends on a design that could not
deliver a confirmatory answer under its own frozen rules.

## 4) Prepared (NOT executed): the pivot decision

As mandated, the pivot decision document is prepared for the owner's
review — the institutional-continuity test of the RAW structured
history channel, grounded in H1–H4 (the program's strongest
confirmatory thread: raw accumulating history improved fresh
successors' decisions through complete turnover, live model,
Holm-corrected): `G2_PIVOT_RAW_HISTORY_CONTINUITY_DECISION_DRAFT_20261029.md`.
Nothing in it dispatches; it is a decision draft only.

## 5) Ledger

Zero new sends. The interaction design's live line is closed; its
offline apparatus (qualification, no-forced-sign check, audits)
remains committed and reusable. Reserved Probe sends untouched. All
historical results unmodified.
