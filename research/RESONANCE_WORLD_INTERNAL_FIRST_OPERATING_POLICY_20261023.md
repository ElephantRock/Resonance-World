# Resonance World — Internal-First Operating Policy (2026-10-23)

**Status: architecture direction.** Work remains wholly within Resonance World-controlled processes and repositories. **No independent/external auditor, third-party witness, external archive authority, or outside approval service is required** for a project workflow. Do not introduce them as prerequisites or implied follow-up work.

This direction applies across the research progression Models → Agents → Agent Organizations → Autonomous Institutions and all scientific gates G1–G4. It describes a desired design policy; it does not imply that every subsystem already implements these controls.

## 1. Critical-path discipline

A step blocks progress only if skipping it would invalidate a necessary dependency, cause a safety or resource authorization violation, corrupt experimental results, or leak private holdout information. Prefer a single automated local validation at the real dependency boundary to multi-party sequential signoffs.

Source-grade ingestion must end before holdout; a durable local fingerprint is therefore a necessary G1 barrier. External archive enrollment, third-party witness signatures and independent review are **not** necessary. The runnable G1 Internal Checkpoint path is documented in research/c3r_g2/G1_INTERNAL_FIRST_FAST_PATH_DECISION_20261023.md.

## 2. Nonblocking by default

- Independent experiments and units may execute concurrently if run IDs, credentials, workspace directories, quota budgets, target assignments and result namespaces are isolated.
- Derivative analysis, visualization, documentation, metrics rollups and optional audits consume closed snapshots **off the critical path**; their downtime does not halt unrelated work.
- Deterministic sequence or ordering is retained **only** for operations where causal interpretation, replay consistency or data integrity requires it.
- Any queue must have explicit capacity limits, backpressure, deadlines and cancellation semantics. Avoid unbounded retries, queues without owners, or permanent global coordination locks.
- Retry only safely idempotent work; use unique run/action keys, attempt accounting and bounded escalation. A timed-out provider call must not be blindly duplicated or counted as a new scientific observation.
- Favor scoped per-unit ownership and event-driven coordination over one globally required arbiter, serial overseer, or central manual approval chain.

These statements are **design goals** for later organizational/institutional phases, not verified latency or performance improvements in deployed systems.

## 3. Internal assurance, not self-certification

Internal data integrity remains mandatory: frozen protocol and identifiers, signed or hashed records where helpful, source/holdout separation, complete denominators including failed attempts, reliable provenance and spending authorization for model calls, session isolation, and comparable token/compute conditions. An internal CI pass is engineering verification only. It is not G1 scientific acceptance or replication.

The project can run its own evaluation methodology without an independent auditor. Scientific claims still require authentic observations, sound causal design and transparent treatment of confounding and uncertainty.

## 4. Failure handling

Stop only the affected run when encountering corruption, missing essential source records, run-ID collisions, revoked permissions, budget exhaustion or private target leakage. Do not stall unrelated runs. Preserve error events and mark missing outcomes rather than reconstructing or silently dropping them.

The internal source checkpoint is exclusive (O_EXCL) and fsynced: it guards against accidental local replay and mutation, **not** privileged host compromise or WORM-level immutability. Run-specific isolation and recovery procedures remain the responsibility of the internal operator.

## 5. Scope and migration

**Current engineering change:** C3R G1's optional local evaluator now supports --internal-checkpoint-dir, with no witness/custodian/archive synchronous dependency and strict validation before holdout and at closure. Older four-UID and external-handoff prototypes are retained as historical/compatibility code **not part of the operational critical path**. The external-witness handoff contract is superseded and must not be interpreted as a mandatory roadmap.

**Next work priorities** should target internal experiment quality (authentic provider/session receipts when authorized, paired/crossed randomization and balance, prompt/token parity, accurate private grading and reproducibility) plus scalable execution architecture, rather than adding signers and approvers.

No new paid model calls, main-branch merge, scientific claim, or Pattern Register promotion is authorized by this policy alone.
