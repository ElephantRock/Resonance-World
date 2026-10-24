# G1 GLM-5.3 REAL low/high/max — three complete 40-slot cohorts (2026-10-23)

**GitHub Actions:** https://github.com/ElephantRock/Resonance-World/actions/runs/39973501740
**Execution head:** 9f4432d2dfa031a4e2b4c7df318027b825d07a20

**Observed actual model traffic**, not a mock: Z.AI Coding GLM-5.3 with thinking.type=enabled and explicitly selected low/high/max. Three independently executed cohorts, each with the same 8-context public plan, 16 development + 24 holdout logical attempts, and its own private evaluator target seed. All 120 physical attempts were reserved. All 120 got HTTP 200 and a valid A/B completion. No provider errors, not-sent records or invalid formats.

## Frozen denominator and comparative results

| Metric | LOW | HIGH | MAX |
|---|---:|---:|---:|
| Accepted / prescribed | 40/40 | 40/40 | 40/40 |
| Eligible context triplets | 8/8 | 8/8 | 8/8 |
| Learned holdout correctness | **8/8** | **8/8** | **8/8** |
| Fresh holdout correctness | 4/8 | 4/8 | 4/8 |
| Neutral holdout correctness | 4/8 | 4/8 | 4/8 |
| Median request latency | 3.621s | 3.639s | 6.097s |
| Mean request latency | 4.069s | 4.764s | 7.233s |
| Prompt tokens reported | 9,016 | 9,016 | 9,016 |
| Completion tokens reported | 2,403 | 4,816 | 4,096 |
| Reasoning tokens reported | 2,263 | 4,682 | 3,959 |

Low consumed about 52% fewer reported reasoning tokens than High and 43% fewer than Max on this small fixed task fixture, with the same answer completeness and accuracy. The order of reasoning tokens is non-monotonic (High > Max). The low/high median latencies differ by only about 18 milliseconds; Max was clearly slower descriptively. No provider-invoice reconciliation, hardware normalization, or matched private label assignments across cohorts is asserted.

## Family-balanced holdout counts

All three efforts returned identical *aggregate* holdout correctness:
- Arithmetic: Learned 4/4, Fresh 2/4, Neutral 2/4.
- Text: Learned 4/4, Fresh 2/4, Neutral 2/4.
- Each cohort has 16 accepted development and 24 accepted qualification calls.
- Across the 8 context-level paired holdout triplets, Learned beat each control 4 times, tied 4 times, and lost 0 times; two-sided exact sign test for 4 discordant pairs yields p=0.125, not a confirmatory scientific result.

## Explicit scientific limitations

Every cohort REUSED the same frozen public tasks and predeclared fallback-A prompt for Fresh/Neutral. Learned received actual graded source examples reinserted in its prompt. The 8/8 vs 4/8 contrast therefore demonstrates that a model can follow supplied graded prompt evidence against a deterministic A-only no-evidence baseline; it does **not** prove acquired persistent agent expertise, independent generalization, or institutional learning. The three private target assignments were separately randomly seeded and were not pinned as an identical per-unit allocation across efforts. Do not treat the 24 qualification triplets or three model-effort cohorts as 24 independent new contexts.

These are actual API outputs, but all provider token counts come from reported response metadata, not trusted invoice reconciliations. Reasoning effort is the **requested setting**, not an independently measured hardware/compute budget. All three levels retained thinking enabled; low is not thinking disabled.

The most scientifically discriminating next step is a persistent agent experience-store vs fresh/neutral agents on genuinely new tasks and contexts, with within-run token controls and internal prospective causal design. No independent/external auditor or additional approval gate is needed. **scientific_acceptance=false**. PR #310 remains Draft and the Pattern Register must not be promoted on this result alone.

## Immutable source artifact identifiers

- LOW: artifact 12510303205 (g1-glm53-effort-low-real-20261023); ZIP SHA256 704c8642d90565eb4ede0bd9f1829de66eaa0d57350e374aa33ebc414bbafc6c; JSON SHA256 d1df0149831377332c768ac690e03e56cc43e1a5079db8a48cf7b50e5b0da82f.
- HIGH: artifact 12510303246 (g1-glm53-effort-high-real-20261023); ZIP SHA256 0ec84644ba5cf93110975e83a7b8dd0479c041677fbd0d98d61c10c36774352e; JSON SHA256 0133257874c7633b3d9f9d13bce02ba637ccd02ec8cfd57d9bbbaf445c929e96.
- MAX: artifact 12510915375 (g1-glm53-effort-max-real-20261023); ZIP SHA256 19754e09d9feedebfd28a853df148833cbc5fe864ddb0642278f5f6a1a71a5c0; JSON SHA256 c9179ccea984b446c99232a312d4e18aa166dbff4de82f5895384a4dddf9b6b6.
- Frozen plan digest: 00661fe7dd37086f08f8458b13a57cc1e8b2123fd00e31918dedf8d26a3cdf6e.

Postclosure aggregation is implemented at scripts/analyze_c3r_g1_glm53_efforts.py, with tests in tests/test_c3r_g1_glm53_effort_analysis.py. The real original files remain preserved separately from summary report.
