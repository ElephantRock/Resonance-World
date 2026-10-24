# G1 real terminal-grade procedural memory: two-session retention (2026-10-23)

**Observed live Z.AI GLM-5.3 trial:** https://github.com/ElephantRock/Resonance-World/actions/runs/40003387403 — all three GitHub cohort jobs **success**. Model parameter request: thinking.type=enabled, reasoning_effort=low, Coding route, generated token maximum 4096, 120-second per-call transport timeout. No external auditor, approver or independently attested billing. **This is a real provider experiment, not an offline simulation.**

**Prospectively frozen protocol:** G1_TERMINAL_GRADE_RETENTION_PROSPECTIVE_20261023.md committed before first send; source code scripts/run_c3r_g1_terminal_retention_live.py and reusable helper scripts/run_c3r_g1_three_step_procedure_live.py. Each cohort had 3 distinct Python interpreter processes, sharing only owner-private files. No retries or duplicate sends were attempted.

## Primary empirical outcomes — ITT denominators preserved

| Arm | Retention 1 correct / 24 prescribed | Retention 2 correct / 24 prescribed |
| --- | ---: | ---: |
| **Learned: grade-derived relevant 3-step capsule** | **20/24 (83.3%)** | **19/24 (79.2%)** |
| Fresh: independently random 3-bit capsule | 4/24 (16.7%) | 2/24 (8.3%) |
| Neutral: second independently random 3-bit capsule | 2/24 (8.3%) | 2/24 (8.3%) |

**Valid model answer counts, not just correct counts:** Retention 1: Learned 21/24, Fresh 22/24, Neutral 22/24. Retention 2: Learned 20/24, Fresh 22/24, Neutral 21/24.

**Cohort breakdown (correct / 8 prescribed):**

| Cohort | Eligible context units | Learned wave1 → wave2 | Fresh wave1 → wave2 | Neutral wave1 → wave2 |
| --- | ---: | ---: | ---: | ---: |
| 01 | 8/8 | **6/8 → 6/8** | 2/8 → 1/8 | 2/8 → 2/8 |
| 02 | 7/8 | **7/8 → 6/8** | 1/8 → 0/8 | 0/8 → 0/8 |
| 03 | 7/8 | **7/8 → 7/8** | 1/8 → 1/8 | 0/8 → 0/8 |
| **Total** | **22/24** | **20/24 → 19/24** | **4/24 → 2/24** | **2/24 → 2/24** |

**Repeated-unit retention transition** in the *same 24 contexts*, not independent new subjects: Learned correct at BOTH waves: **18**. Lost correctness between wave1 and wave2: **2**. Gained correctness in wave2: **1**. Incorrect/missing at BOTH waves: **3**. The wave2 improvement/regression pattern does not prove memory decay (time elapsed was not controlled, measured, or preregistered as a durability interval).

## Source attempts and missingness

- Prescribed: 3 cohorts × 56 terminal full-program source trial slots = **168 source logical slots**, plus 3 × 24 × 2 holdout slots = **144 logical holdout slots**. Fixed campaign denominator **312**.
- **Source sends reserved:** 102. These produced **98 valid output evaluations**, 4 invalid/error outcomes, and **66 not_sent source slots** from early stopping when enough whole-program evidence was acquired. The four nonvalid source responses were not assumed to be negative grades.
- **Eligible procedures:** 22/24 distinct context units inferred their entire 3-bit procedure only from binary success/failure on COMPLETE program executions, without per-step labels. Two incomplete source units had their 3 holdout arms skipped at BOTH waves.
- Retention 1: 66 physical holdout send reservations, 65 valid responses, 1 invalid format, 6 not_sent due to incomplete source contexts.
- Retention 2: 66 physical holdout reservations, 63 valid responses, 3 invalid formats, 6 not_sent.
- **Overall actual physical request reservations: 234**, out of the 312 prescribed logical slots. No retries, no replacement imputations, and no retrospective dropping of invalid/missing observations. As in prior pilots, reservation count is not a separately authenticated vendor invoice.
- Provider-reported holdout completion usage is **not arm-matched**: Learned wave1 6,917 / wave2 6,678; Fresh wave1 2,712 / wave2 2,635; Neutral wave1 2,565 / wave2 3,012. Learned's larger generated token count limits causal claims about equal model compute; the prompt capsule length was matched, not generated reasoning expenditure.

## Scientific interpretation: stronger mechanism test, not autonomous model training

**What advanced:**
1. Source feedback now reveals **ONLY terminal correctness of a complete three-step candidate program**; the earlier trivial one-feedback-bit-per-hidden-step shortcut was removed. The controller can eliminate up to seven complete candidate codes; a perfect seven negatives logically determine the eighth. It is a deterministic, explicitly programmed search, with randomized candidate order and occasional early termination.
2. The previously biased shuffled-donor Neutral control was replaced. Fresh and Neutral now sample independent random policies from exactly the same eight full-program possibilities, each independent of the target with *ex ante* 1/8 exact-match probability. Both controls and Learned receive the same three-character capsule representation and the same holdout prompt renderer. Small realized differences between controls are sampling variability and missingness, not a systematic negative-dependence construction.
3. The source process terminates; retention1 starts in a second interpreter using the stored frozen capsule on a never-seen public operand, then retention2 starts in a third interpreter after retention1 closes, using the SAME original capsule on a distinct new operand. No per-step grades or source transcript entered the holdout prompts.

**What remains unproven:** independent strategic invention or weight adaptation in GLM, agent capacity to learn broad procedures with a rich ambiguous feedback signal, multi-day/month retention, a matched model-compute causal treatment effect, real-world functional autonomy, and institutional regeneration. Both memory and evaluator remained on one trusted GitHub CI host, without external witness, and that is intentional under the user's internal-first policy. The same two simple arithmetic/text *families* were reused across units, while context identifiers, candidate order and source/holdout operands were newly sampled. The two retention waves measure the SAME subjects; pooling them as 48 independent contexts is invalid.

This is real evidence of **external agent-side acquisition, persistence and repeated execution of a three-step procedure under terminal-grade feedback**. It is not powered scientific acceptance for G1; **scientific_acceptance=false**, PR #310 remains Draft, Pattern Register unchanged.

## Evidence identifiers and auditability

Immutable sanitized GitHub workflow artifacts, each containing source, retention1 and retention2 redacted reports:

- Cohort 01 artifact ID **12521899607**: ZIP SHA256 a370f2e692f8aa243f8becfd1d63b3b349cf462cb4783e5dd8ff5da78042f59b.
- Cohort 02 artifact ID **12523665956**: ZIP SHA256 275561b39876d025807726df8434a78a1a06476efc60effdd65c2716462e5605.
- Cohort 03 artifact ID **12522853260**: ZIP SHA256 38e8d18991d00e06211fe88a48bd2f6afc412acd16ba0144e07314871713a5b0.

Local audited descriptive JSON derived solely from those three immutable archives: SHA256 **26be36a02fbe62009212a7c20d2cb2cfbd64bdb5059347b48e52b5f87c74478b** (g1_terminal_two_retention_real_results_20261023.json).

Offline audit script scripts/analyze_c3r_g1_terminal_retention.py plus negative tests tests/test_c3r_g1_terminal_retention_analysis.py check all 312 prescribed slots, physical-send reconciliation, paired context IDs across waves, valid and missing arm rows, and explicit false scientific acceptance. The next meaningful experiment should increase procedure complexity/uncertainty and preregister **a real measurable delay** or turnover of the agent, with matched model-compute controls. Do not introduce outside auditors or serial approval gates.
