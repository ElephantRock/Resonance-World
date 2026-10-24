# Prospective internal G1 GLM-5.3 low/high/max REAL experiment — 2026-10-23

**Status:** frozen before the three real cohort dispatches. Explicit project-owner authorization to continue paid experiments and remove unnecessary bottlenecks; internal-only execution without auditor, outside custodian or human approval queue. Trigger: one-time marker G1_GLM53_THREE_EFFORT_REAL_DISPATCH_20261023.md. Execution workflow: .github/workflows/c3r-g1-glm53-effort-real-once.yml.

## Hypothesis and design

GLM-5.3 does **not** support thinking disabled. Three **distinct real-model cohorts** will request thinking.type=enabled with reasoning_effort **low**, **high**, or **max**, respectively. Official documentation supports these three levels; requesting any one does not guarantee an exact thinking-token budget. The experiment measures the operational tradeoff among rate of valid completions, response latency, reasoning/completion tokens, error/missingness, and descriptive correctness.

Each effort cohort uses the **same existing frozen public crossed G1 plan**: four arithmetic + four text context-level units, eight contexts total; two development requests per context (16 total), and three qualification arms per context (24 total). Each cohort uses a **fresh evaluator-private seeded A/B allocation balanced 2+2 per family**, and its own run ID. The target allocations are not guaranteed identical across effort cohorts, so cross-effort observations are NOT paired by target; task fixtures are REUSED and are not independent novel items.

Every prompt contains the previously declared uniform fallback instruction: if no actual graded outcomes exist, choose A promptly; otherwise use two graded source outcomes. Learned receives real graded evidence in its qualification prompt; Fresh receives none; Neutral receives masked task IDs/actions/grades only. Consequently, the no-grade controls implement a deliberately trivial fixed-A baseline and the study **cannot establish autonomous memory learning**. It can measure how reasoning-effort affects delivery and grade-use under the same operational prompt protocol.

## Operational contract

- **Three independently tracked prospective cohorts:** g1-glm53-effort-low-20261023-07; g1-glm53-effort-high-20261023-07; g1-glm53-effort-max-20261023-07. Each is a distinct 40-logical-slot denominator, i.e. 120 planned logical slots across the campaign. An attempt missing/invalid still remains in its denominator.
- **No external bottlenecks.** Each cohort advances qualified contexts independently; source signatures/checkpoint are local and automatic, before holdout. Other cohort jobs need not wait for the first one's scientific result.
- **Concurrence:** maximum 3 simultaneously active physical sends per cohort and maximum **2 concurrent cohort jobs** via CI matrix. Separate per-run private workspace and exclusive fsynced request reservations, no retries. Maximum 120 request reservations, potentially fewer if development errors prevent holdout for some contexts.
- **Transport and latency:** Z.AI Coding route; per-request 120-second timeout; max_tokens 8192, including reasoning; local monotonic per-attempt response latency stored in milliseconds. Report HTTP class where safely available, never raw response text or secret credentials. Graph/analysis after closure only.
- **Readiness:** repository CI must pass before the one-shot marker is added. Runner checks credential presence and frozen plan locally without provider sends. A failure in one cohort does not abort the other matrix cohorts (fail-fast=false).
- **Artifact names:** g1-glm53-effort-low-real-20261023, -high-real-20261023, -max-real-20261023. Each contains redacted 40-row observed grades and token/latency/error evidence and identifies which effort was *requested*. The GitHub Action is single-use and should be removed after results are inspected to avoid accidental reruns.

## Planned analysis, without post-hoc reinterpretation

For each effort cohort independently:
1. Report 16 development + 24 qualification logical attempts, physical reservations, accepted counts, invalid_format, provider_error, not_sent, and how many of eight context triplets completed.
2. Report learned/fresh/neutral qualification **correct / 8 prescribed**, **accepted / 8 prescribed**, with 4+4 arithmetic/text family breakdown; never discard missing arms in denominators.
3. For valid attempts, report median and distribution of local per-request latency and provider-reported prompt/completion/reasoning tokens by stage/family/arm. Transport failures can consume billable tokens unreported by the API, so sums are observational lower bounds, not reconciled invoices.
4. Compare effort levels **descriptively**, considering different target allocations, repeated task fixtures, possible rate-limit and time-of-day effects, and unequal reasoning budgets. Do not pool cohorts as independent new tasks or claim proof of G1 from a small repeated benchmark.
5. Do not infer that low means "no thinking"; all 3 explicitly have thinking enabled. Do not assert provider-enforced reasoning mode based solely on submitted API parameters.

G1 scientific_acceptance remains **false**. The proper next causal experiment remains genuinely persistent experience-store agents on new holdout items, matched fresh and neutral agents, multiple contexts/seeds, and internal methodological rigor, without any independent auditor or outside approval chain.
