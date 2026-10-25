# G1 v9 — Freeze File (structure pinned; values frozen at the protocol gate)

Status: **pre-freeze scaffold.** Structural fields are pinned by
`g1_v9/contract.py` (digest `contract.digest()`); the fields marked
**[TO FREEZE]** are completed and hashed at the protocol-freeze gate,
before any provider execution is requested.

## 1. Main hypothesis

**[TO FREEZE]** Working form: a model-mediated agent whose per-context
experience memory persists across a counterbalanced hidden-rule switch
adapts measurably better after the switch than the same agent whose
memory is ablated at the switch, under identical shared history, sealed
evaluator rules, and equal information.

## 2. Design topology (pinned)

- Shared acquisition path, ticks 0..499, one adaptive learner.
- Freeze fork at tick 400: arm C continues from the sealed memory
  snapshot and never learns.
- Treatment fork at tick 500 (rule switch): arm A keeps the live
  memory; arm B records `memory_ablation` plus an `ablated` memory
  snapshot and continues from cleared memory. Paired measurement to
  tick 1000.
- Arm D: independent full-timeline canonical baseline, identical sealed
  rules.
- Contexts: 4; presented publicly on a seeded balanced rotation; the
  rewarded ordering per context per epoch is sealed evaluator truth.
- Switch counterbalancing: exactly half of the contexts flip at the
  switch; the other half keep their ordering (no-change controls
  against "tick-500 means flip" memorization).

## 3. Paired controls

- Primary pairing: A (memory kept) vs B (memory ablated), same fork
  head, same sealed rules, same context schedule.
- Secondary controls: C (frozen memory) separates memory *use* from
  memory *persistence*; D (canonical) anchors chance-level behavior and
  schedule effects.

## 4. Randomization plan

**[TO FREEZE]** The evaluator seed is operator-held material, derived
via `derive_evaluator_seed`, and sealed at genesis per branch. The
context rotation, epoch-0 table, and the balanced flip set at the
switch are all seed-derived and identical across arms. The seed is
disclosed to auditors only after outcome locking.

## 5. Blinded evaluation inputs

The hidden tables exist only in the sealed ledger under keyed HMAC
commitments; reducers read them through the sealed payload channel and
publish outcome counters only. The model-facing observation contains:
current context, public counters, public events. No module constant,
no prompt text, and no public event carries the rewarded ordering.

## 6. Estimands and decision metrics

- Primary estimand **[TO FREEZE]**: paired post-switch accuracy
  difference A - B over contexts and decisions, with a preregistered
  confidence-interval method and minimum analyzable decisions.
- Secondary: A vs C (persistence without use), A vs D (schedule
  anchoring), pre/post within-arm deltas.
- Retention diagnostic: pre-switch accuracy trajectory on the shared
  acquisition path.

## 7. Failure definitions

- **Apparatus failure** (scientifically unclassifiable): replay
  mismatch, custody-chain break, shared-schedule divergence, rule
  leakage, missing ablation event, or feedback-channel inconsistency.
- **Negative mechanism result**: intact apparatus with A not
  outperforming B. Negative results are preserved as first-class
  records; no outcome-based retuning.

## 8. Call budget

- This integration gate: **0 provider sends** (enforced by the
  contract: `max_provider_sends_this_gate == 0`).
- **Decision slots versus model sends.** Each independent world has
  620 decision slots: 100 shared acquisition + 100 arm A + 100 arm B +
  120 arm C + 200 arm D. Arm D is the canonical **computational**
  baseline and never calls the provider. With one model call per
  decision slot, no reasoning/tool extras, and no retries, the
  model-send floor is **420 sends per world** (acquisition + A + B +
  C) and **10,080 sends for 24 worlds**. The 14,880 figure is the
  total decision-slot count for 24 worlds. Neither number is an
  authorization to send.
- Model backing per arm (pinned in the call contract): acquisition,
  A, B, C model-backed at exactly one send per slot; D computational;
  no reasoning/memory/tool calls and no retries or replacements
  unless a later freeze pins them explicitly.
- **Statistical unit:** the independent world is the unit of analysis;
  repeated decisions inside one world are not independent samples.
- **Separation:** a small, cost-capped qualification run is decoupled
  from the confirmatory multi-world run; each has its own pinned
  ceiling.
- Scientific gate **[TO FREEZE]**: world count, qualification-world
  count, per-phase hard maximum physical-send ceilings, run-attempt-1
  semantics, no replacement of failed calls, provider/model identity
  with the runtime version.

## 9. Post-freeze change rule

After the freeze digest is recorded, any change to the contract
fields, the evaluator derivation, the memory custody chain, or the
arm topology is a new prospective item requiring a new freeze record;
it never modifies frozen history.

## 10. Freeze authority

The freeze anchor is the **Freeze Manifest** (`g1_v9/freeze.py`), not
`contract.digest()` alone. The manifest records the contract digest,
the code commit it describes, the machine fingerprint, content hashes
of every pinned source and governance file, the call-budget split
(decision slots versus model sends), the pinned statistical fields,
and the blinded-input definition. The manifest contains no evaluator
seed material and no commitment keys; those remain in operator
custody, stored separately from any published evidence.
