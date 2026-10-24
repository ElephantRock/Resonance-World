# G1 TEXT RELIABILITY REAL-MODEL TECHNICAL TRIAL — 2026-10-23

**Dispatch authority:** project owner explicitly authorized continued, uncapped real-model experimentation and requested removal of unnecessary bottlenecks, with all work internal. No outside auditor/witness/approval step.

Single marker-triggered **new** provider run: `g1-text-reliability-20261023-03` via `.github/workflows/c3r-g1-text-reliability-once.yml`.

- Goal: diagnose text-specific GLM-5.3 failure/response reliability from the first two real crossed trials, **not** to retroactively rescue, rerun or merge earlier observations.
- Real model: Z.AI Coding GLM-5.3, 16,384 output tokens, 180-second timeout, at most 2 concurrent calls, no retries.
- Up to **20 text-family physical request reservations**: 4 text contexts × (2 source development + 3 holdout arms), with per-context qualification only if both source grades are valid.
- Keep original frozen 40 logical attempt schedule for signed/auditable internal records. All 20 arithmetic slots are **not_sent by design**, and any text contexts missing source receive not_sent holdout statuses.
- Journal each physical attempt with exclusive local file before dispatch; no retry of timeout/unknown outcome. Record safe **locally generated HTTP status and exception class** without error messages or raw provider bodies, plus provider-reported usage.
- User's instruction to reduce bottlenecks is implemented by separating source validity per context; no external actor is consulted.
- This is an unpowered technical reliability diagnostic on the **same public text tasks** as before, with a new internal randomized target seed; not independent item replication, not powered G1 evidence.
- All outcome categories and missing attempts remain in the planned denominator. No automatic workflow rerun on ambiguity. Retire one-shot launcher after inspecting results.

Previous real-model calls belong exclusively to runs 39911219008 (16 source requests) and 39912520068 (34 reserved requests). Their evidence remains separate.
