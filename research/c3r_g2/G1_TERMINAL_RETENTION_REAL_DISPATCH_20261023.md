# ONE-SHOT AUTHORIZED REAL G1 TERMINAL-FEEDBACK TWO-RETENTION STUDY — 2026-10-23

**Authorization:** the project owner has approved continued real paid GLM experiments without a spending ceiling, all internal, without an external auditor or approval bottlenecks. This is a genuinely NEW campaign, not a replay of prior physical requests.

**Frozen protocol, CI-tested before this marker:** research/c3r_g2/G1_TERMINAL_GRADE_RETENTION_PROSPECTIVE_20261023.md.
**Code:** scripts/run_c3r_g1_terminal_retention_live.py
**Offline tests:** tests/test_c3r_g1_terminal_retention_live.py
**Unique push trigger:** .github/workflows/c3r-g1-terminal-retention-real-once.yml on research/c3r-g2-causal-foundation.

Three independent real GLM-5.3 (thinking.enabled, reasoning_effort=low) cohorts have unique run IDs: g1-terminal-retention-20261023-01, -02 and -03. For each cohort: up to 7 terminal whole-program trials on 8 fresh contexts (56 logical source slots), then one new Python interpreter rehydrates stored policy and runs 8 x 3 holdout comparisons (24 slots) on fresh operands, then a third independent interpreter performs a second never-seen task per context using the SAME original policy (24 further slots). Exactly **104 logical slots per cohort**, **312 across campaign**, with early stopping causing fewer physical source attempts; every unattempted slot explicitly not_sent. GLM output generation cap 4096 including reasoning, per-request timeout 120 seconds, 3 parallel calls/cohort, at most 2 cohort jobs in parallel, no retries.

Learned policy uses ONLY final correct/incorrect grades for a complete three-step candidate; it does not receive individual hidden-step feedback. Fresh and Neutral are separately sampled uniform random full three-bit policies, each with independent 1/8 exact-match chance; they are capacity-matched and uninformative. All prompts share identical schema and no prior source grades or raw source transcript are fed to the holdout models.

All private target mapping, raw tasks and persistent capsule data remain in a private ephemeral CI workspace, not uploaded. Public artifacts show ONLY redacted per-arm/per-unit correctness/status/latency/usage and phase counts. Session separation is proven by distinct Python interpreters and immutable local phase closure, **not elapsed wall-clock days**. Source search is explicitly deterministic finite elimination, not spontaneous model adaptation.

Do NOT rerun ambiguous requests or retrigger this marker. Retire workflow after artifacts close. G1 scientific_acceptance remains false; PR #310 remains Draft; no Pattern Register update.
