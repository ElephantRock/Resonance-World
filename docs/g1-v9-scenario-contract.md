# G1 v9 — World-Time Adaptation: Scenario Contract (draft, pre-freeze)

Status: **protocol draft for the integration gate.** This document is the
human-readable companion to the machine-checkable contract in
`src/resonance_world/experimental_runtime/g1_v9/contract.py`. It is **not** a
preregistration for scientific claims and **does not authorize any provider
execution**. The protocol and budget must be reviewed and frozen separately
before any GLM-5.3 call is allowed.

## Research question (for the later scientific gate)

When a model-mediated agent accumulates experience under world rule P0 and the
hidden rule switches to P1 at a known tick, does accumulated experience
produce measurable adaptation compared with memory-ablated, frozen-policy,
and canonical-baseline controls - with the whole world remaining exactly
replayable from recorded events?

## World mechanics

- One agent per experimental branch; each decision picks one of two orderings
  (`AB` or `BA`) for the current epoch.
- The hidden rule of an epoch is the ordering the environment rewards. Rule
  content is **sealed**: it enters the world only as a private `rule_epoch`
  event whose payload is committed with a keyed HMAC commitment and stored in
  the sealed ledger. The public log never sees the ordering value.
- Epoch 0 (ticks 0..499) runs under P0; epoch 1 (ticks 500..999) runs under
  P1. The **switch tick is public**; the rule content is secret. Epoch
  boundaries and rule sealings are identical across arms.
- Decision feedback (success/failure of the chosen ordering) is public and is
  the agent's only lawful information channel: agents observe outcomes, never
  evaluator truth.
- Ablation (arm B only) is an explicit public `memory_ablation` experimental
  transaction recorded in the branch at the switch tick. Shared history,
  evaluator rules, and hidden targets are byte-identical across arms; only
  the agent's private experience memory is cleared in arm B.

## Arms

| Arm | Branch id | Policy | Treatment |
|---|---|---|---|
| A adaptive | `arm-a-adaptive` | experience-memory policy, learns throughout | none |
| B memory-ablated | `arm-b-ablated` | same as A until the switch | ablation transaction + experience memory cleared at tick 500 |
| C frozen | `arm-c-frozen` | stops learning at tick 400 (P0 snapshot semantics) | frozen after snapshot |
| D canonical | `arm-d-canonical` | fixed alternation, ignores feedback | baseline |

For the **integration gate** all four policies are offline scripted stand-ins
implementing the kernel `ModelDecisionPort` contract. No model, SDK, or
credential exists on this code path.

## Measurements

Per arm, from public counters only:

- `pre_accuracy` = successes / attempts over ticks < 500
- `post_accuracy` = successes / attempts over ticks >= 500
- `adaptation_delta` = post_accuracy - pre_accuracy

Per acceptance run (structural, non-scientific):

- every branch replays with an identical state commitment and all checkpoints
  matched; replay performs zero policy calls
- all non-decision events are byte-identical across arms (shared schedule,
  shared sealed-rule commitments under the same store key)
- the ablation transaction exists exactly in arm B
- no public event or public state key exposes rule content
- two independent runs produce identical reports (determinism)

## Claim ceiling for this gate

The integration gate establishes **apparatus only**: that the contract, arms,
and replay machinery behave as specified without a model. It establishes
nothing about model learning, adaptation, or regeneration. Scientific claims
require the frozen protocol, budget, and authorized GLM-5.3 execution in a
later gate.

## Freeze and budget gates (unchanged)

1. This contract is reviewed, then frozen with a contract digest in an issue.
2. The model phase requires explicit human authorization naming the exact
   candidate commit, the provider/model, and a maximum physical-send budget
   with per-run attempt-1 semantics, per the repository operating charter.
3. Commitment keys are custodied outside any published evidence file; the
   store supports external keys (`commitment_key=`, `persist_commitment_key=False`).
4. `rules_version` and external dependencies are pinned through the machine
   fingerprint; replay under different rules is rejected by construction.
