# G1 v9 — Scenario Contract (hardened design; freeze candidate)

Status: **freeze candidate.** This document is the human-readable
companion to `g1_v9/contract.py` and `g1_v9/evaluator.py`. It is **not**
a scientific claim and **does not authorize any provider execution**.
The freeze anchor is the machine-verifiable manifest
(`g1_v9/freeze.py`), which pins this document by content hash.

## Research question (for the later scientific gate)

When a model-mediated agent accumulates per-context experience under
hidden rule epoch 0 and the evaluator switches the hidden tables at a
known tick (flipping exactly half of the contexts), does retained
experience produce measurable post-switch adaptation compared with a
memory-ablated paired agent, a frozen-policy agent, and a canonical
baseline - with the whole world exactly replayable from recorded
events?

## World mechanics (hardened design)

- **Shared acquisition:** one acquisition branch runs ticks 0..499 with
  a single adaptive learner. Arms A and B fork from its recorded head
  at the treatment tick, so their pre-treatment history is the same
  branch - identity is structural, not assumed from matching schedules.
- **Multi-context decisions:** four task contexts, presented publicly
  in seeded shuffled blocks (balanced presentation). Each decision
  names the presented context and one of two orderings; the reducer
  rejects any decision whose context differs from the presented one.
- **Hidden truth is evaluator-held:** per-epoch, per-context rewarded
  orderings are derived by the evaluator from operator-held seed
  material and enter the world only as sealed private `rule_epoch`
  events (keyed HMAC commitments). No ordering constant is importable.
- **Balanced switch:** at the switch the evaluator flips exactly half
  of the contexts and keeps the other half - no-change controls
  against switch-prior memorization.
- **Memory custody:** every save/ablation of the paired agents'
  experience memory is attested by a public `memory_snapshot` event
  (keyed commitment) co-recorded with a sealed `memory_state` payload,
  so agent state survives resume from the world's own ledger.
- **Ablation is an in-branch transaction:** arm B records
  `memory_ablation` plus an `ablated` memory snapshot at the fork;
  arm A keeps the live memory. Shared history, evaluator rules, and
  hidden targets are byte-identical across arms.

## Arms

| Branch | Fork point | Policy | Treatment |
|---|---|---|---|
| `acquisition` | genesis | adaptive learner | shared history; ticks 0..499 |
| `arm-a-adaptive` | tick 500 (acquisition head) | live memory continues | none |
| `arm-b-ablated` | tick 500 (acquisition head) | memory cleared at the fork | `memory_ablation` + `ablated` snapshot |
| `arm-c-frozen` | tick 400 (freeze snapshot) | sealed snapshot restored; never learns | frozen memory |
| `arm-d-canonical` | genesis | per-context alternation, feedback-ignored | independent baseline |

## Timeline

- ticks 0..399: shared acquisition (also common to arm C).
- tick 400: freeze snapshot (memory save + arm C fork).
- ticks 400..499: acquisition continues (common to A and B).
- tick 500: rule switch sealed (balanced); A/B paired fork; arm B
  ablation transaction.
- ticks 501..1000: paired measurement for A and B; C and D run their
  own tails over the same switched rules.

## Measurements

Per arm, from public counters only: `pre_accuracy`, `post_accuracy`,
`adaptation_delta` (post - pre). Per acceptance run (structural):
replay identity for every branch, shared-schedule identity between A
and B, exclusive ablation, custody-chain verification, absence of rule
leakage, zero policy calls during replay, and cross-run determinism.

## Claim ceiling for this gate

The integration gate establishes **apparatus only**. Scripted-arm
numbers demonstrate mechanics, not model behavior. Scientific claims
require the freeze manifest, the frozen budget, and authorized GLM-5.3
execution in a later gate.
