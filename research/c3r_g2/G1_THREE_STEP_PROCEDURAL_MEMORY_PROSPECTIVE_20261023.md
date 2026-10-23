# Prospective G1 real 3-step procedural agent memory trial — 2026-10-23

**Status:** new experimental protocol frozen BEFORE provider dispatch on the draft research branch. User has authorized paid experimentation without a spending ceiling, internal execution, and reduction of operational bottlenecks. No external auditor, approval chain or custodian.

## Research question

Can an agent preserve a **three-step executable procedure** inferred from feedback, terminate the acquisition process, and accurately apply it to a **new task input in a new interpreter**, beyond both a capacity-matched untrained policy and an unrelated agent's learned policy?

**G1 distinction:** This is an internal mechanism test of deterministic agent-side **feedback-to-memory compilation** plus new-process retrieval. The GLM-5.3 model has NOT necessarily modified its weights or independently inferred policy bits. The explicit reducer receives the correctness of source actions and can logically identify each of three hidden A/B steps. Results are not evidence of emergent model learning or institutional regeneration.

## Fixed design

- Three independently randomized real provider cohorts; **8 contexts per cohort**, 4 arithmetic and 4 text; **24 context-level units** total. Context IDs, public holdout task IDs and operands are sampled afresh *before source calls*. Public task families are known; within each family the three binary hidden steps are individually counterbalanced 2A/2B across four contexts.
- **24 model source actions per cohort**: one A/B probe action for each of three hidden steps in each of eight contexts. The model has no target rule; it is directed to make a blind A probe. The internal agent controller receives post-action correct/incorrect grade bits, then infers the hidden three-bit code (AAA, AAB, ... BBB) deterministically.
- At source closure, save a private owned fsynced manifest, source grade log, and a **three-character experience capsule** per context, all bound by SHA256 digests. End source Python process.
- **24 holdout calls per cohort** from a **new separate Python interpreter** (3 arms × 8 contexts). All arms get the same holdout task, instruction structure and **exactly three capsule bits**:
  - **Learned:** the three-step policy actually inferred from this context's graded source actions.
  - **Fresh:** three-bit random cold-start policy sampled before source and independent of graded outcomes; **not** a fixed A guess.
  - **Neutral:** capacity-matched policy compiled from another context in the **same task family**, rotated without access to the current target. If that donor failed, use its precommitted cold-start random policy; report failures separately. This is an unrelated-experience control, not an independent source-run model.
- The model applies the capsule's three steps **in order**, on a NEW numeric operand or new text input, and returns **only the executed result**. Arithmetic operations involve add/subtract, multiply by one of two factors, then add/subtract; text operations involve prefix choice, case choice, and suffix choice. Arithmetic inputs are resampled until the eight possible programs yield distinct results. This avoids scoring ambiguous outputs as correct by chance.
- **48 prescribed logical attempts per cohort; 144 campaign total** (72 source + 72 holdout). Any provider errors, invalid formats or not_sent holdout rows remain in intention-to-treat denominators. Partial source failures skip only their corresponding three holdout slots.
- GLM-5.3 Coding route; **thinking enabled, reasoning_effort=low**; 3 concurrent model calls per cohort, at most 2 cohort jobs in parallel, 120s request timeout, max_tokens=4096 including reasoning; no retries. Distinct fsynced reserved slot files before every request, phase-level exclusive holdout-start marker, no second run of an ambiguous physical attempt.
- Same ephemeral host stores private target/manifests, but no external audit or WORM claim is made. GitHub public artifacts contain **redacted source/holdout summaries and per-unit paired validity/grade indicators only**. No private targets, capsule content, raw provider answers, task operands or credential.

## Prospective endpoints

Primary exploratory comparison per run and pooled across independent context units:
1. **Full three-step correct outputs**: Learned vs Fresh and Learned vs Neutral, among all 8 prescribed holdout contexts per arm per cohort (24 per arm across campaign). Keep invalid/not-sent in the denominator.
2. Exact context-level **paired discordance** and descriptive paired differences; report confidence intervals if justified by complete data, without pretending the data were a powered confirmatory study.
3. Complete valid-format responses and per-attempt provider usage/latency by arm/family; report outliers and timeouts without excluding them.
4. Capsule reproducibility: all complete source feedback grades map to an internally consistent three-bit policy before a new interpreter reads and uses it; frozen digest and no replay checks enforced.
5. Inter-cohort variance; no pooling of rows as independent individual model generations when units share a context.

**Limitations:** all three instruction bits are recovered by a simple explicit reducer from one binary feedback per bit. GLM may merely follow clear capsule instructions; this is an engineering proof of agent memory persistence, NOT a discovery of novel autonomous procedural learning. Fresh/Neutral controls have equal capsule representation but may differ in actual token/compute use. Three code bits do not constitute complex real-world expertise, tasks remain in two simple families, same host cannot independently attest trust or provider billing. **scientific_acceptance=false**. No Pattern Register update or PR merge from this alone.
