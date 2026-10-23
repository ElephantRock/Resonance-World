# G1 fourth crossed real dispatch — first observed 16-source probe (2026-10-23)

**Live GitHub Actions run:** https://github.com/ElephantRock/Resonance-World/actions/runs/39911219008
**Execution commit:** 1ea1e71bd59e793fac6c40c1649dfb77f9525aa8
**GitHub sanitized artifact:** g1-fourth-real-crossed-20261023, artifact ID 12483201878. ZIP SHA256 c26a61b1fe15eda8d39ace649c6cc8a58655650a612f36f3355b019314439248; inner JSON SHA256 c5a8f619f131337efa49c5db587f71c4c1267ba89e59f4d611302ef350f59960.

**Evidence:** 16 real GLM-5.3 physical request reservations on Z.AI Coding endpoint; eight arithmetic source calls all accepted and five text source calls accepted. Two text source calls were classified provider_error and one text source call returned finish_reason=stop but invalid A/B format. **Total 13/16 source accepted, 1 invalid_format, 2 provider_error.**

The earlier globally rigid source barrier forbade *all* 24 holdout calls; the artifact records all as not_sent_after_source_failure, giving 40/40 logical statuses but zero actual holdout observations. No grade comparison among learned/fresh/neutral can be derived from this incomplete experiment. The fourth pilot's scientific_acceptance remains **false**.

Usage from accepted/invalid API completions where available (not authenticated billing): prompt_tokens_reported=2315, completion_tokens_reported=9684, reasoning_tokens_reported=9606. Arithmetic accepted A=6, B=2, text accepted A=5, B=0. All raw model responses, private evaluator target seed and API credential were excluded from the shared artifact.

**Identified engineering bottleneck:** the 16-of-16 grade rule was a *global* approval barrier despite eight independent context-level learner units; a single source error blocked unrelated holdout arms. For the next separately identified experiment the internal source lock will retain all 16 signed attempts, then launch a holdout triplet for each context with two accepted development grades and mark incomplete contexts' holdout rows not_sent. No prior physical request from this run is silently retried, and this remains exploratory. New run ID, new private assignment seed, and disclosed reuse of the same public task fixture, not independent replicated tasks.

**Distinct preflight failure:** GitHub run 39911077580 had cryptography missing before the provider stage; its model send step was skipped and had **zero sends**, then the dependency was installed. Neither failure is evidence against the acquisition hypothesis by itself.

**Scientific interpretation:** no acquired autonomous agent capability was established. Future successful crossed observations would still measure feedback reinserted into prompts, not independent persistent memory, and would require more contexts/task families, provider token exposure comparison and a powered design for a causal G1 claim. No outside auditor is required by the internal-first operating policy.
