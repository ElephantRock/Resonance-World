# C3R G1 — Prospective real cross-session agent experience transfer (2026-10-23)

**Status:** internal-only, engineered and tested before real-provider dispatch; scientific_acceptance=false. Owner authorized actual paid experimentation without a spending ceiling, and explicitly rejected external approvers/auditors as bottlenecks. Protocol and executable stored on research/c3r-g2-causal-foundation, PR #310 Draft. One-shot trigger is G1_PERSISTENT_AGENT_REAL_DISPATCH_20261023.md.

## Research question and estimand

Can an **agent experience store**, assembled from its source feedback and persisted to local private storage, carry a compact context-specific action policy into a **new independent process/session** and improve next-item decisions relative to agents receiving no usable remembered experience?

This is a mechanism test for **agent-side external memory**, not a demonstration that GLM model weights change or that the LLM itself internally learns from unseen feedback. The agent-side policy extractor is an explicit deterministic reducer: if two model source actions were valid, reconstruct the context's A/B policy from actual binary action feedback and persist only that one-bit policy. Source true targets stay in evaluator-owned private manifest files, never in the provider prompt. Neither raw source transcript nor feedback grades are reinserted at qualification.

**Three prospective independent runs**, each creating EIGHT new opaque context IDs and THREE newly sampled task operands per context (2 development and 1 unseen qualification). Four contexts each of arithmetic/text; hidden A/B targets balanced within family 2+2 by private random assignment. There are 16 source logical attempts and 24 holdout logical attempts per run: 40/run, **120 prescribed** across three cohorts. All three runs use GLM-5.3 with thinking enabled and reasoning_effort=low, Z.AI Coding route, at most three concurrent provider calls per run and at most two concurrent run jobs.

Primary descriptive contrast: holdout correct/8 prescribed for Learned, Fresh and Neutral and their differences per run; also pooled descriptive counts **with context as unit**, tracking run/family. Holdout missing/invalid or skipped after source failure remains in its prescribed denominator. No affirmative powered causal acceptance is claimed.

## Experimental arms

1. **Learned (agent persisted experience):** source stage makes two actual GLM model A/B decisions under a uniform no-evidence fallback-A instruction; the local agent reducer observes the *post-action grade bits* and saves an inferred A/B policy per context in a private 0600 experience capsule. Qualification runs in a NEW Python interpreter, reading only that one-bit capsule and the new public task. It never receives the original source transcript or grade rows in the model prompt.
2. **Fresh:** no experience policy, same holdout prompt renderer, policy '?' and the uniform declared fallback to A. It is a deterministic default baseline, not an unconstrained fresh learner.
3. **Neutral:** one-bit placebo policy independently hashed from new run/context IDs rather than graded source performance. It has the same capsule interface and valid A/B policy format, but no causal connection to the context target; independence of the placebo and secret target is by separately generated random and hashed inputs, not external attestation.

The difference between Learned and neutral isolates whether passing meaningful stored policy vs non-informative placebo policy helps under this fixed prompting mechanism. Learned-vs-Fresh compares meaningful memory with no memory, but Fresh's A fallback is explicitly weak. Source learning is a **deterministic agent algorithm**, not a learned model update, and the prompt's instruction to obey a memory capsule makes the mechanism deliberately easy.

## Persistence, non-replay and internal assurance

- Each run creates an exclusive private workspace, samples context IDs, tasks and balanced secret targets BEFORE source requests, then writes and fsyncs an owner-private frozen manifest (0600). Input tasks and planned denominators are new for this campaign; probability of operand collision is negligible and should be inspected in evidence.
- Each physical model attempt reserves its unique 00..39 index in a private exclusive fsynced file before sending. No retry after any ambiguous timeout/transport failure.
- After the first **16 source logical outcomes**, persist a standalone experience.json of one-bit policy capsules and a separate source.json digest lock binding both the manifest and capsule. Exit the first Python process. The qualification process re-reads and verifies the stored source/capsule digests and the independently recomputed policy rule; no raw source result rows enter the new model's prompt.
- Before the second process sends any holdout request, it exclusively creates a persisted holdout-start marker. This prevents a second phase invocation from replaying any previously attempted send, including if the previous phase never made it to its first provider call.
- Each context's three qualification requests are attempted only if its two source requests yielded a consistent non-unknown policy. Others are 'not_sent' but remain among 24 prescribed.
- The two processes run in **separate GitHub workflow steps**, each a new Python interpreter, sharing only private files on the same ephemeral CI host. No outside custodian/auditor is used; a privileged CI host process could still rewrite same-host files and no external timestamp or WORM custody is claimed.
- Only redacted aggregate source and holdout reports are uploaded. The private manifest includes hidden target mapping and is NEVER uploaded. Raw provider outputs, development feedback, agent prompts, or API secrets are not uploaded.

## Limits and decision boundary

This directly tests **experience-store persistence and cross-session retrieval**, with independent new task inputs and multiple seeds. It is distinct from prior prompt-reinsertion experiments in which all graded outcomes were included with every Learned holdout request. It still cannot establish emergent learned competence inside the LLM, autonomous agent innovation, or long-run institutional inheritance. The same arithmetic/text *task families* remain simple, agent reducer explicitly infers one bit from external labels, fixed-A Fresh is not a strong adaptive baseline, prompts and actual token budgets may differ by arm, and only 24 context-level units across three runs are prescribed. Outcomes are exploratory, not powered.

Any missing observations, unequal token consumption, or inconsistent target allocations shall be reported, not silently omitted. A convincing G1 acquisition result would require challenging genuinely novel task laws, stronger matched baseline memory controls, persistent identity/experience across many timepoints and a scientifically justified power design.

**No Pattern Register promotion, no merge and no scientific acceptance from operational success alone.**
