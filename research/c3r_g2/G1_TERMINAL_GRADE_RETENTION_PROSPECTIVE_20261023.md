# Prospective G1 terminal-only procedural evidence + two independent retention sessions — 2026-10-23

**Frozen before any live model sends.** Internal-first; project owner authorized real paid experiments with no spending ceiling and rejected external auditors and approval bottlenecks. PR #310 stays Draft, scientific_acceptance=false.

## Improvements over the preceding three-step G1 pilot

The previous agent received one binary grade per hidden step and reconstructed all three bits through a trivial correctness-bit flip. Its Neutral control used another context's code from the same balanced group, inducing negative dependence: each bit agreed with the target with probability 1/3 instead of the independent prior 1/2. The earlier placebo was systematically disadvantaged.

**Terminal-only learning:** The new agent tests a complete three-bit program, asks GLM-5.3 to execute the entire sequence on a fresh source input, and receives only a single internally generated success/failure bit for the FULL output. The reducer sees no individual step labels. It explores up to 7 of the 8 candidate full programs, in randomized private order, excluding candidates only after a VALID failed trial. If it finds success it stops early; if seven valid distinct failures occur it infers the eighth. Missing/provider failures never count as incorrect program evidence. Contexts lacking a definitive policy have all holdout attempts marked not_sent.

**Independent, equal-capacity controls:** Learned receives the feedback-inferred three-bit policy of its own context. Fresh and Neutral each receive an independent uniform random three-bit policy, drawn from the same eight possibilities BEFORE source. Both have independent ex ante exact-match chance 1/8 and the identical capsule length/prompt schema as Learned, despite balance among hidden per-step targets. These independently randomized placebos are not unrelated learned agents, and make no claim about inter-agent memory exchange.

**Two subsequent independent process sessions:** The source interpreter terminates, retention1 rehydrates the persisted capsule in a separate Python interpreter and executes one previously unseen input per context. After retention1's immutable phase closure, retention2 starts in yet another interpreter and executes a SECOND different private holdout input, using the identical unchanged capsule, with no new feedback. This proves multiple session restarts and sequence ordering, NOT elapsed-hours, days or calendar-time retention.

## Frozen design and resource bounds

- THREE independently seeded GLM-5.3 Coding cohorts (01, 02, 03). Each has 8 new opaque context IDs (4 arithmetic + 4 text), with private hidden three-step procedures independently balanced 2A/2B per family per step. Twenty-four distinct contexts in campaign.
- Per cohort **56 prescribed source slots** = 7 whole-program probes x 8 contexts, plus **24 prescribed slots per retention wave** = 8 x 3 arms. Exactly **104 logical attempts per cohort, 312 across three**. Actual model send reservations can be fewer because identified contexts stop probing early; all remaining source slots stay not_sent. Holdout rows for an incompletely identified unit remain not_sent with fixed denominators.
- Model: GLM-5.3, thinking.type=enabled, reasoning_effort=low, Z.AI Coding endpoint, max_tokens=4096 including reasoning, timeout 120 seconds, 3 concurrent sends/cohort and at most 2 cohort jobs in parallel. Each physical request has a unique exclusive fsynced journal reservation, **zero automatic retries**. Phase start markers exclude replay even after a crash.
- Source manifest created privately (0600) before any send; includes secret code, 7 distinct random source operands, two different unseen holdout operands, two independent random policy controls and prospective candidate order. Capsule and source ledger are SHA256-bound; retention phases check integrity and source policy consistency. Same trusted CI runner retains private data; no external witness, external time authority or vendor-billing attestation is claimed.
- Uploaded results are **redacted phase summaries and per-context grade/status metadata**, with no private target, raw model output, source grade ledger, capsule, task operand or API key.

## Planned analysis and limitations

Primary endpoint is complete three-step output correctness for Learned/Fresh/Neutral, each out of **eight prescribed context attempts per wave and per cohort**, including missingness. Compare both retention waves within the same context (these are repeated measures, not independent contexts). Report within-cohort and overall descriptive paired outcome counts, status invalidity, early stopping, local request latency and vendor-reported token usage. Controls have identical ex ante 1/8 chance of exact program match; observed proportions may depart from that in a tiny sample.

Even under perfect outcomes, the policy search is explicitly programmed deterministic finite elimination, not emergent GLM strategic learning. These results assess agent-side acquisition and external experience-store stability over two independent sessions, not model weight adaptation, long-duration retention, real-world procedural expertise, causal scientific acceptance or Autonomous Institutions. No Pattern Register promotion or PR merge.

## Implementation

- scripts/run_c3r_g1_terminal_retention_live.py
- scripts/run_c3r_g1_three_step_procedure_live.py (journal + deterministic execution helpers)
- tests/test_c3r_g1_terminal_retention_live.py
